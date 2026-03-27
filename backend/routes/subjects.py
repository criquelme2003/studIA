import logging
from typing import List
from fastapi import APIRouter, HTTPException, Header
from database import supabase
from models import SubjectCreate, SubjectResponse
from routes.auth import get_user_id_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=List[SubjectResponse])
async def list_subjects(authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("subjects")
            .select("*")
            .eq("user_id", user_id)
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("list_subjects error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch subjects")


@router.post("", response_model=SubjectResponse, status_code=201)
async def create_subject(body: SubjectCreate, authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("subjects")
            .insert({"user_id": user_id, "name": body.name, "color": body.color})
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_subject error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create subject")


@router.delete("/{subject_id}", status_code=204)
async def delete_subject(subject_id: str, authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("subjects")
            .delete()
            .eq("id", subject_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Subject not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_subject error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to delete subject")


@router.get("/{subject_id}/files")
async def list_subject_files(subject_id: str, authorization: str = Header(...)):
    """Lista los archivos de una asignatura (sin extracted_text para no sobrecargar)."""
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("user_files")
            .select("id, filename, content_type, size, created_at, extracted_at")
            .eq("user_id", user_id)
            .eq("subject_id", subject_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("list_subject_files error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch files")
