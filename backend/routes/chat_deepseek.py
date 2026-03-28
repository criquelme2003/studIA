"""
chat_deepseek.py — Chat unificado con DeepSeek.

Un solo endpoint maneja dos dominios:
  - ESTUDIO: recupera archivos relevantes del usuario y responde con citas
  - CALENDARIO: parsea lenguaje natural y devuelve acción estructurada (create/update/delete)

El agente detecta el intent automáticamente. El cliente siempre recibe `reply` (texto
para el chat) y opcionalmente `action` + `event` / `event_id` para el calendario.

Flujo:
  1. Si hay eventos en el request → detectar si es query de calendario
  2. Cargar catálogo de archivos del usuario (summary + keywords)
  3. Paso 1: seleccionar archivos relevantes para el prompt
  4. Cargar extracted_text de los archivos seleccionados
  5. Llamada principal: respuesta unificada en JSON { reply, calendar_action, event, event_id }
  6. Parsear y devolver ChatDeepSeekResponse
"""

import json
import logging
import requests
from fastapi import APIRouter, HTTPException, Header
from database import supabase
from config import DEEPSEEK_API_KEY
from models import (
    ChatDeepSeekRequest, ChatDeepSeekResponse,
    CalendarEvent, SourceRef, SuggestedSubject,
)
from routes.auth import get_user_id_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat-deepseek"])

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
MAX_FILES_IN_CONTEXT = 3
MAX_TEXT_PER_FILE = 6000


# ── Helper DeepSeek ───────────────────────────────────────────────────────────

def _call_deepseek(messages: list, max_tokens: int = 1024, temperature: float = 0.3) -> str:
    resp = requests.post(
        DEEPSEEK_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
        timeout=40,
    )
    try:
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.HTTPError as exc:
        logger.error("DeepSeek HTTP error: %s — %s", exc, resp.text[:300])
        raise HTTPException(status_code=502, detail="DeepSeek API error")
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected DeepSeek response: %s", exc)
        raise HTTPException(status_code=502, detail="Unexpected DeepSeek response")


def _parse_json_response(raw: str) -> dict:
    """Extrae JSON de la respuesta de DeepSeek (maneja bloques markdown)."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:].strip()
    return json.loads(raw)


# ── Selección de archivos relevantes ─────────────────────────────────────────

def _select_relevant_files(prompt: str, files: list[dict]) -> list[str]:
    if not files:
        return []

    catalog = "\n\n".join(
        f'file_id: {f["id"]}\n'
        f'  archivo: {f["filename"]} | asignatura: {f.get("subject_name") or "Sin asignatura"}\n'
        f'  resumen: {f.get("summary") or "(sin resumen)"}\n'
        f'  keywords: {", ".join(f.get("keywords") or [])}'
        for f in files
    )

    msg = (
        f"Dado este catálogo de documentos de un estudiante, indica cuáles son relevantes "
        f"para la consulta. Responde ÚNICAMENTE con un JSON array de file_ids (máx {MAX_FILES_IN_CONTEXT}). "
        f"Si ninguno es relevante, responde [].\n\n"
        f"Consulta: {prompt}\n\nCatálogo:\n{catalog}"
    )

    try:
        raw = _call_deepseek([{"role": "user", "content": msg}], max_tokens=200, temperature=0.0).strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1][4:].strip() if len(parts) > 1 else raw
        return [str(fid) for fid in json.loads(raw) if isinstance(json.loads(raw), list)]
    except Exception as exc:
        logger.warning("File selection failed: %s", exc)
        return []


# ── System prompt unificado ───────────────────────────────────────────────────

def _build_system_prompt(
    current_date: str | None,
    events: list[dict],
    file_blocks: list[dict],
) -> str:
    date_line = f"Hoy es {current_date}." if current_date else ""

    lines = [
        "Eres un asistente personal para estudiantes universitarios.",
        date_line,
        "Responde en el mismo idioma en que el estudiante escribe.",
        "",
        "Tienes dos capacidades:",
        "1. ESTUDIO — responder preguntas académicas usando el material del estudiante.",
        "2. CALENDARIO — gestionar eventos del calendario con lenguaje natural.",
        "",
        "IMPORTANTE: responde SIEMPRE con un JSON válido con esta estructura exacta:",
        '{ "reply": "<texto para mostrar en el chat>", "calendar_action": null | "create" | "update" | "delete", "event_id": null | "<id del evento>", "event": null | { "title": "...", "start": "YYYY-MM-DDTHH:MM:SS", "end": "YYYY-MM-DDTHH:MM:SS", "location": "...", "notes": "..." } }',
        "",
        "Reglas de calendario:",
        "- Consulta (¿qué tengo?, ¿cuándo es?): calendar_action=null, responde en reply.",
        "- Crear evento: calendar_action='create', incluye event completo. Si no se da hora de fin, asume 1 hora después.",
        "- Editar evento: calendar_action='update', incluye event_id del evento a modificar y event con los nuevos datos.",
        "- Eliminar evento: calendar_action='delete', incluye solo event_id.",
        "",
        "Reglas de estudio:",
        "- calendar_action=null.",
        "- Si usas información de un documento, menciónalo en el reply entre paréntesis.",
        "- Si la respuesta no está en el material, respóndela con tu conocimiento general e indícalo.",
    ]

    if events:
        events_json = json.dumps(events, ensure_ascii=False, indent=2)
        lines += ["", "=== CALENDARIO DEL ESTUDIANTE ===", events_json, "=== FIN CALENDARIO ==="]

    if file_blocks:
        lines += ["", "=== MATERIAL DE ESTUDIO ==="]
        for block in file_blocks:
            subj = f" ({block['subject_name']})" if block.get("subject_name") else ""
            lines.append(f"\n[{block['filename']}{subj}]")
            lines.append(block["text"][:MAX_TEXT_PER_FILE])
        lines.append("=== FIN MATERIAL ===")

    return "\n".join(lines)


# ── Clasificación de asignatura sugerida ──────────────────────────────────────

async def _suggest_subject(user_id: str, prompt: str) -> SuggestedSubject | None:
    try:
        subjects = (
            supabase.table("subjects").select("id, name").eq("user_id", user_id).execute()
        ).data or []
    except Exception:
        return None

    if not subjects:
        return None

    subject_list = "\n".join(f"- id:{s['id']} nombre:{s['name']}" for s in subjects)
    messages = [
        {
            "role": "system",
            "content": (
                "Clasificador de preguntas académicas. "
                "Responde ÚNICAMENTE con el id de la asignatura más probable. "
                "Si ninguna encaja, responde: ninguna"
            ),
        },
        {"role": "user", "content": f"Asignaturas:\n{subject_list}\n\nPregunta: {prompt}"},
    ]
    try:
        raw = _call_deepseek(messages, max_tokens=100, temperature=0.0).strip().lower()
        if raw == "ninguna":
            return None
        for s in subjects:
            if s["id"] in raw or s["name"].lower() in raw:
                return SuggestedSubject(id=s["id"], name=s["name"])
    except Exception as exc:
        logger.warning("Subject suggestion failed: %s", exc)
    return None


# ── Endpoint principal ────────────────────────────────────────────────────────

@router.post("/deepseek", response_model=ChatDeepSeekResponse)
async def chat_deepseek(body: ChatDeepSeekRequest, authorization: str = Header(...)):
    """
    Chat unificado — maneja estudio y calendario en el mismo endpoint.

    El cliente envía:
    - prompt: mensaje del usuario
    - current_date: fecha/hora actual ISO 8601 (para contexto temporal)
    - events: lista de eventos del calendario (ventana ±30 días recomendada)
    - subject_id: filtro opcional para búsqueda de archivos
    """
    user_id = get_user_id_from_token(authorization)

    # ── Cargar catálogo de archivos ───────────────────────────────────────────
    all_files: list[dict] = []
    try:
        query = (
            supabase.table("user_files")
            .select("id, filename, summary, keywords, subject_id, subjects(name)")
            .eq("user_id", user_id)
            .not_.is_("extracted_text", "null")
        )
        if body.subject_id:
            query = query.eq("subject_id", body.subject_id)

        res = query.execute()
        for f in res.data or []:
            subj = f.pop("subjects", None)
            f["subject_name"] = subj["name"] if isinstance(subj, dict) else None
            all_files.append(f)
    except Exception as exc:
        logger.error("Failed to load file catalog: %s", exc)

    # ── Seleccionar archivos relevantes ───────────────────────────────────────
    file_blocks: list[dict] = []
    sources: list[SourceRef] = []

    if all_files:
        relevant_ids = _select_relevant_files(body.prompt, all_files)
        if relevant_ids:
            try:
                rows = (
                    supabase.table("user_files")
                    .select("id, filename, extracted_text, subjects(name)")
                    .in_("id", relevant_ids)
                    .eq("user_id", user_id)
                    .execute()
                ).data or []

                for row in rows:
                    if not row.get("extracted_text"):
                        continue
                    subj = row.pop("subjects", None)
                    subject_name = subj["name"] if isinstance(subj, dict) else None
                    file_blocks.append({
                        "filename": row["filename"],
                        "text": row["extracted_text"],
                        "subject_name": subject_name,
                    })
                    sources.append(SourceRef(
                        file_id=row["id"],
                        filename=row["filename"],
                        subject_name=subject_name,
                    ))
            except Exception as exc:
                logger.warning("Failed to load file texts: %s", exc)

    # ── Llamada principal unificada ───────────────────────────────────────────
    events_dicts = [e.model_dump(exclude_none=True) for e in body.events] if body.events else []
    system_prompt = _build_system_prompt(body.current_date, events_dicts, file_blocks)

    raw = _call_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": body.prompt},
        ],
        max_tokens=1024,
    )

    # ── Parsear respuesta JSON ────────────────────────────────────────────────
    calendar_action: str | None = None
    event: CalendarEvent | None = None
    event_id: str | None = None
    reply: str = raw  # fallback si el parseo falla

    try:
        data = _parse_json_response(raw)
        reply = data.get("reply", raw)
        calendar_action = data.get("calendar_action") or None

        if calendar_action in ("create", "update") and data.get("event"):
            ev = data["event"]
            event = CalendarEvent(
                title=ev.get("title", ""),
                start=ev.get("start", ""),
                end=ev.get("end", ""),
                location=ev.get("location"),
                notes=ev.get("notes"),
            )

        if calendar_action in ("update", "delete"):
            event_id = data.get("event_id")

    except Exception as exc:
        logger.warning("Could not parse DeepSeek JSON response: %s — raw: %s", exc, raw[:200])

    # ── Sugerir asignatura si es query de estudio sin subject_id ─────────────
    suggested_subject: SuggestedSubject | None = None
    if not calendar_action and not body.subject_id:
        suggested_subject = await _suggest_subject(user_id, body.prompt)

    return ChatDeepSeekResponse(
        reply=reply,
        sources=sources or None,
        subject_id=body.subject_id,
        suggested_subject=suggested_subject,
        action=calendar_action or "ai_reply",
        event=event,
        event_id=event_id,
    )
