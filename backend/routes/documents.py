import logging
from typing import List
from fastapi import APIRouter, HTTPException, Header
from database import supabase
from models import DocumentCreate, DocumentResponse
from routes.auth import get_user_id_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=List[DocumentResponse])
async def list_documents(authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("list_documents error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch documents")


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(body: DocumentCreate, authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("documents")
            .insert({"user_id": user_id, "title": body.title, "body": body.body})
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_document error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create document")


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, authorization: str = Header(...)):
    user_id = get_user_id_from_token(authorization)
    try:
        result = (
            supabase.table("documents")
            .delete()
            .eq("id", doc_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_document error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to delete document")
