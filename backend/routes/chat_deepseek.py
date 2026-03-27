import logging
import requests
from fastapi import APIRouter, HTTPException, Header
from database import supabase
from config import DEEPSEEK_API_KEY
from models import ChatDeepSeekRequest, ChatDeepSeekResponse, SuggestedSubject
from routes.auth import get_user_id_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat/deepseek", tags=["chat-deepseek"])

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
MAX_TOKENS = 1024


def _call_deepseek(messages: list) -> str:
    resp = requests.post(
        DEEPSEEK_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": MODEL, "messages": messages, "max_tokens": MAX_TOKENS},
        timeout=30,
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


def _build_system_prompt(subject_name: str | None, file_blocks: list[dict]) -> str:
    lines = [
        "Eres un asistente de estudio para estudiantes universitarios.",
        "Responde en el mismo idioma en que el estudiante escribe.",
        "Sé claro, preciso y pedagógico.",
    ]

    if file_blocks:
        subject_label = f"Asignatura: {subject_name}" if subject_name else "Material de estudio"
        lines.append(f"\n=== MATERIAL DE ESTUDIO ({subject_label}) ===")
        for block in file_blocks:
            lines.append(f"\n[Fuente: {block['filename']}]")
            lines.append(block["text"])
        lines.append("\n=== FIN DEL MATERIAL ===")
        lines.append(
            "\nResponde basándote en el material cuando sea relevante. "
            "Si la respuesta no está en el material, indícalo claramente antes de responder."
        )

    return "\n".join(lines)


@router.post("", response_model=ChatDeepSeekResponse)
async def chat_deepseek(body: ChatDeepSeekRequest, authorization: str = Header(...)):
    """
    Chat con DeepSeek con contexto de archivos de una asignatura.

    - Si viene subject_id se usa directamente.
    - Si NO viene, DeepSeek sugiere a qué asignatura pertenece la pregunta
      y devuelve suggested_subject para que el cliente confirme.
    - file_refs: lista de file_ids cuyos extracted_text se incluyen como contexto.
    """
    user_id = get_user_id_from_token(authorization)

    # ── Resolver asignatura ───────────────────────────────────────────────────
    subject_name: str | None = None
    suggested_subject: SuggestedSubject | None = None

    if body.subject_id:
        # Obtener nombre para el system prompt
        try:
            res = (
                supabase.table("subjects")
                .select("id, name")
                .eq("id", body.subject_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            subject_name = res.data["name"] if res.data else None
        except Exception:
            pass
    else:
        # Sugerir asignatura automáticamente
        suggested_subject = await _suggest_subject(user_id, body.prompt)

    # ── Cargar texto de archivos referenciados ────────────────────────────────
    file_blocks: list[dict] = []
    if body.file_refs:
        file_ids = [ref.file_id for ref in body.file_refs]
        try:
            res = (
                supabase.table("user_files")
                .select("id, filename, extracted_text")
                .in_("id", file_ids)
                .eq("user_id", user_id)
                .execute()
            )
            for row in res.data or []:
                if row.get("extracted_text"):
                    file_blocks.append({
                        "filename": row["filename"],
                        "text": row["extracted_text"],
                    })
        except Exception as exc:
            logger.warning("Could not load file refs: %s", exc)

    # ── Construir mensajes y llamar a DeepSeek ────────────────────────────────
    system_prompt = _build_system_prompt(subject_name, file_blocks)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body.prompt},
    ]

    reply = _call_deepseek(messages)

    return ChatDeepSeekResponse(
        reply=reply,
        subject_id=body.subject_id,
        suggested_subject=suggested_subject,
        action="ai_reply",
    )


async def _suggest_subject(user_id: str, prompt: str) -> SuggestedSubject | None:
    """
    Pide a DeepSeek que clasifique la pregunta entre las asignaturas del usuario.
    Devuelve la sugerencia o None si el usuario no tiene asignaturas.
    """
    try:
        res = (
            supabase.table("subjects")
            .select("id, name")
            .eq("user_id", user_id)
            .execute()
        )
        subjects = res.data or []
    except Exception:
        return None

    if not subjects:
        return None

    subject_list = "\n".join(f"- id:{s['id']} nombre:{s['name']}" for s in subjects)

    classification_messages = [
        {
            "role": "system",
            "content": (
                "Eres un clasificador de preguntas académicas. "
                "Dado un listado de asignaturas y una pregunta, responde ÚNICAMENTE "
                "con el id de la asignatura más probable. "
                "Si ninguna encaja, responde con la palabra: ninguna"
            ),
        },
        {
            "role": "user",
            "content": f"Asignaturas:\n{subject_list}\n\nPregunta: {prompt}",
        },
    ]

    try:
        raw = _call_deepseek(classification_messages)
        raw = raw.strip().lower()

        if raw == "ninguna":
            return None

        # Buscar el id en la respuesta
        for s in subjects:
            if s["id"] in raw or s["name"].lower() in raw:
                return SuggestedSubject(id=s["id"], name=s["name"])
    except Exception as exc:
        logger.warning("Subject classification failed: %s", exc)

    return None
