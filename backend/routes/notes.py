import logging
from typing import List
from fastapi import APIRouter, HTTPException, Header
from database import supabase
from models import NoteCreate, NoteResponse
from routes.auth import get_user_id_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=List[NoteResponse])
async def list_notes(authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("notes")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("list_notes error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch notes")


@router.post("", response_model=NoteResponse, status_code=201)
async def create_note(body: NoteCreate, authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("notes")
            .insert({"user_id": user_id, "content": body.content})
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_note error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create note")


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: str, authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("notes")
            .delete()
            .eq("id", note_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Note not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_note error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to delete note")
