import logging
import requests
from fastapi import APIRouter, HTTPException, Header
from database import supabase
from config import GEMINI_API_KEY
from models import ChatRequest, ChatResponse
from routes.auth import get_user_id_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-lite:generateContent"
)


def _call_gemini(prompt: str) -> str:
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return (
            data["candidates"][0]["content"]["parts"][0]["text"]
        )
    except requests.HTTPError as exc:
        logger.error("Gemini HTTP error: %s — %s", exc, exc.response.text if exc.response else "")
        raise HTTPException(status_code=502, detail="Gemini API error")
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected Gemini response shape: %s", exc)
        raise HTTPException(status_code=502, detail="Unexpected Gemini response format")
    except Exception as exc:
        logger.error("Gemini call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to reach Gemini API")


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, authorization: str = Header(...)):
    """
    Smart chat endpoint:
      - '/note <text>'          → create a note and confirm
      - '/doc <title> | <body>' → create a document and confirm
      - anything else           → proxy to Gemini
    """
    user_id = get_user_id_from_token(authorization)
    prompt = body.prompt.strip()

    # ── /note command ──────────────────────────────────────────────────────────
    if prompt.lower().startswith("/note "):
        content = prompt[6:].strip()
        if not content:
            raise HTTPException(status_code=400, detail="Note content cannot be empty")
        try:
            result = (
                supabase.table("notes")
                .insert({"user_id": user_id, "content": content})
                .execute()
            )
            note = result.data[0] if result.data else {}
        except Exception as exc:
            logger.error("chat /note insert failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to create note")

        return ChatResponse(
            reply=f"Note saved: \"{content}\"",
            action="note_created",
            data=note,
        )

    # ── /doc command ───────────────────────────────────────────────────────────
    if prompt.lower().startswith("/doc "):
        rest = prompt[5:].strip()
        if "|" not in rest:
            raise HTTPException(
                status_code=400,
                detail="Document format: /doc <title> | <body>",
            )
        title, body_text = rest.split("|", 1)
        title, body_text = title.strip(), body_text.strip()
        if not title or not body_text:
            raise HTTPException(status_code=400, detail="Title and body cannot be empty")
        try:
            result = (
                supabase.table("documents")
                .insert({"user_id": user_id, "title": title, "body": body_text})
                .execute()
            )
            doc = result.data[0] if result.data else {}
        except Exception as exc:
            logger.error("chat /doc insert failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to create document")

        return ChatResponse(
            reply=f"Document \"{title}\" saved.",
            action="doc_created",
            data=doc,
        )

    # ── Gemini proxy ───────────────────────────────────────────────────────────
    reply = _call_gemini(prompt)
    return ChatResponse(reply=reply, action="ai_reply")
