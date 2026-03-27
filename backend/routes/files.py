import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from database import supabase
from models import FileResponse
from routes.auth import get_user_id_from_token
from extractor import extract_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])

BUCKET = "app-files"


@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    subject_id: str = Form(None),
    feature: str = Form("subject"),
    item_id: str = Form(None),
    authorization: str = Header(...),
):
    """
    Sube un archivo a Supabase Storage, extrae su texto si es PDF/DOCX,
    y guarda los metadatos en user_files.
    """
    user_id = get_user_id_from_token(authorization)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    file_uuid = str(uuid.uuid4())
    folder = item_id if item_id else (subject_id if subject_id else "general")
    storage_path = f"{user_id}/{feature}/{folder}/{file_uuid}.{ext}"

    content = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # ── Extracción de texto ───────────────────────────────────────────────────
    extracted_text = extract_text(content, content_type, file.filename)
    extracted_at = datetime.now(timezone.utc).isoformat() if extracted_text else None
    if extracted_text:
        logger.info("Extracted %d chars from %s", len(extracted_text), file.filename)
    else:
        logger.info("No text extracted from %s (type: %s)", file.filename, content_type)

    # ── Upload a Supabase Storage ─────────────────────────────────────────────
    try:
        supabase.storage.from_(BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type},
        )
    except Exception as exc:
        logger.error("Storage upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {exc}")

    # ── Guardar metadatos en DB ───────────────────────────────────────────────
    try:
        row = {
            "user_id": user_id,
            "filename": file.filename,
            "storage_path": storage_path,
            "content_type": content_type,
            "size": len(content),
            "feature": feature,
            "extracted_text": extracted_text,
            "extracted_at": extracted_at,
            "item_id": item_id,
        }
        if subject_id:
            row["subject_id"] = subject_id

        result = supabase.table("user_files").insert(row).execute()
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
    """Elimina el archivo de Storage y su registro en DB."""
    user_id = get_user_id_from_token(authorization)

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

    try:
        supabase.storage.from_(BUCKET).remove([storage_path])
    except Exception as exc:
        logger.warning("Storage delete warning (continuing): %s", exc)

    try:
        supabase.table("user_files").delete().eq("id", file_id).execute()
    except Exception as exc:
        logger.error("user_files delete failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to delete file record")
