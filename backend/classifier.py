"""
classifier.py — Clasificación de archivos por asignatura y generación de metadatos.

Al subir un archivo, DeepSeek:
  1. Genera un resumen (summary) y palabras clave (keywords)
  2. Puntúa la probabilidad de que el archivo pertenezca a cada asignatura del usuario
  3. El texto se pre-divide en chunks para búsqueda futura

Si la probabilidad máxima >= THRESHOLD, se asigna la asignatura automáticamente.
Si no, el archivo se guarda sin asignatura y el cliente recibe needs_confirmation=True.
"""

import json
import logging
import requests

from config import DEEPSEEK_API_KEY

logger = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
CLASSIFICATION_THRESHOLD = 0.65   # probabilidad mínima para asignación automática
SAMPLE_CHARS = 4000                # chars del texto usados para clasificar
CHUNK_SIZE = 800                   # chars por chunk
CHUNK_OVERLAP = 100                # overlap entre chunks


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """Divide el texto en chunks con overlap."""
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Clasificación + enriquecimiento ───────────────────────────────────────────

def classify_and_enrich(text: str, filename: str, subjects: list[dict]) -> dict:
    """
    Llama a DeepSeek para analizar el documento y devuelve:
      {
        summary: str,
        keywords: list[str],
        chunks: list[str],
        subject_scores: {subject_id: float},
        suggested_subject_id: str | None,
        needs_confirmation: bool,
      }

    subjects: lista de {id, name} del usuario.
    """
    chunks = chunk_text(text)
    sample = text[:SAMPLE_CHARS]

    if subjects:
        subjects_str = "\n".join(f"- id:{s['id']} nombre:{s['name']}" for s in subjects)
    else:
        subjects_str = "(sin asignaturas registradas)"

    prompt = f"""Analiza este documento académico. Responde ÚNICAMENTE con un JSON válido, sin texto adicional, con este formato exacto:
{{
  "summary": "<resumen del documento en 3-5 oraciones>",
  "keywords": ["<keyword1>", "<keyword2>", "..."],
  "subject_scores": {{
    "<subject_id>": <probabilidad entre 0.0 y 1.0>
  }}
}}

Reglas:
- summary: describe el tema principal, nivel académico y conceptos clave.
- keywords: máximo 10 palabras clave relevantes.
- subject_scores: puntúa cada asignatura según qué tan probable es que el documento pertenezca a ella. Si no hay asignaturas, devuelve {{}}.

Asignaturas del usuario:
{subjects_str}

Archivo: {filename}
Contenido (primeros {SAMPLE_CHARS} caracteres):
{sample}"""

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 600,
                "temperature": 0.1,
            },
            timeout=40,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Limpiar bloques markdown si DeepSeek los incluye
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:].strip()

        data = json.loads(raw)
        summary = data.get("summary", "")
        keywords = [str(k) for k in data.get("keywords", [])][:10]
        subject_scores = {
            str(k): float(v)
            for k, v in data.get("subject_scores", {}).items()
        }

    except Exception as exc:
        logger.warning("classify_and_enrich failed for %s: %s", filename, exc)
        summary = ""
        keywords = []
        subject_scores = {}

    # Determinar si se asigna automáticamente
    suggested_subject_id: str | None = None
    needs_confirmation = bool(subjects)

    if subject_scores and subjects:
        best_id = max(subject_scores, key=subject_scores.get)
        best_score = subject_scores[best_id]
        logger.info(
            "Classification for %s: best=%s score=%.2f threshold=%.2f",
            filename, best_id, best_score, CLASSIFICATION_THRESHOLD,
        )
        if best_score >= CLASSIFICATION_THRESHOLD:
            suggested_subject_id = best_id
            needs_confirmation = False

    return {
        "summary": summary,
        "keywords": keywords,
        "chunks": chunks,
        "subject_scores": subject_scores,
        "suggested_subject_id": suggested_subject_id,
        "needs_confirmation": needs_confirmation,
    }
