import logging
import uuid
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from database import supabase
from models import FileResponse
from routes.auth import get_user_id_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])

BUCKET = "app-files"


@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    feature: str = Form(...),
    item_id: str = Form(None),
    authorization: str = Header(...),
):
    """
    Upload a file to Supabase Storage and record metadata in user_files table.
    Storage path: {user_id}/{feature}/{item_id or 'general'}/{uuid}.{ext}
    """
    user_id = get_user_id_from_token(authorization)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    file_uuid = str(uuid.uuid4())
    folder = item_id if item_id else "general"
    storage_path = f"{user_id}/{feature}/{folder}/{file_uuid}.{ext}"

    content = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # Upload to Supabase Storage
    try:
        supabase.storage.from_(BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type},
        )
    except Exception as exc:
        logger.error("Storage upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {exc}")

    # Save metadata to DB
    try:
        result = (
            supabase.table("user_files")
            .insert(
                {
                    "user_id": user_id,
                    "filename": file.filename,
                    "storage_path": storage_path,
                    "content_type": content_type,
                    "size": len(content),
                    "feature": feature,
                    "item_id": item_id,
                }
            )
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=500, detail="DB insert returned no data")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("user_files insert failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save file metadata")


@router.delete("/{file_id}", status_code=204)
async def delete_file(file_id: str, authorization: str = Header(...)):
    """Delete a file from Storage and remove its DB record."""
    user_id = get_user_id_from_token(authorization)

    # Fetch metadata to get storage path (and confirm ownership)
    try:
        result = (
            supabase.table("user_files")
            .select("storage_path")
            .eq("id", file_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.error("user_files fetch failed: %s", exc)
        raise HTTPException(status_code=404, detail="File not found")

    if not result.data:
        raise HTTPException(status_code=404, detail="File not found")

    storage_path = result.data["storage_path"]

    # Delete from Storage
    try:
        supabase.storage.from_(BUCKET).remove([storage_path])
    except Exception as exc:
        logger.warning("Storage delete warning (continuing): %s", exc)

    # Delete DB record
    try:
        supabase.table("user_files").delete().eq("id", file_id).execute()
    except Exception as exc:
        logger.error("user_files delete failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to delete file record")
