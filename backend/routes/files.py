import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from database import supabase
from models import FileResponse, FileClassificationResult
from routes.auth import get_user_id_from_token
from extractor import extract_text
from classifier import classify_and_enrich

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])

BUCKET = "app-files"


def _get_user_subjects(user_id: str) -> list[dict]:
    try:
        res = (
            supabase.table("subjects")
            .select("id, name")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.warning("Could not fetch subjects for user %s: %s", user_id, exc)
        return []


@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    subject_id: str = Form(None),
    feature: str = Form("subject"),
    item_id: str = Form(None),
    authorization: str = Header(...),
):
    """
    Sube un archivo, extrae su texto y ejecuta clasificación + enriquecimiento automático.

    Respuesta incluye:
    - classification: {subject_scores, suggested_subject_id, needs_confirmation}
    - summary, keywords ya guardados en DB
    """
    user_id = get_user_id_from_token(authorization)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    file_uuid = str(uuid.uuid4())
    folder = item_id or subject_id or "general"
    storage_path = f"{user_id}/{feature}/{folder}/{file_uuid}.{ext}"

    content = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # ── Extracción de texto ───────────────────────────────────────────────────
    extracted_text = extract_text(content, content_type, file.filename)
    extracted_at = datetime.now(timezone.utc).isoformat() if extracted_text else None
    if extracted_text:
        logger.info("Extracted %d chars from %s", len(extracted_text), file.filename)

    # ── Clasificación + metadatos (siempre, independiente de si viene subject_id) ─
    classification: dict = {
        "summary": "",
        "keywords": [],
        "chunks": [],
        "subject_scores": {},
        "suggested_subject_id": None,
        "needs_confirmation": False,
    }
    if extracted_text:
        subjects = _get_user_subjects(user_id)
        classification = classify_and_enrich(extracted_text, file.filename, subjects)
        logger.info(
            "Classification for %s: suggested=%s needs_confirmation=%s",
            file.filename,
            classification["suggested_subject_id"],
            classification["needs_confirmation"],
        )

    # Si el cliente mandó subject_id explícito, tiene prioridad
    final_subject_id = subject_id or classification.get("suggested_subject_id")

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
        now = datetime.now(timezone.utc).isoformat()
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
            "summary": classification["summary"] or None,
            "keywords": classification["keywords"] or None,
            "classification_scores": classification["subject_scores"] or None,
            "chunks": classification["chunks"] or None,
            "classified_at": now if extracted_text else None,
        }
        if final_subject_id:
            row["subject_id"] = final_subject_id

        result = supabase.table("user_files").insert(row).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="DB insert returned no data")

        data = result.data[0]
        data["classification"] = FileClassificationResult(
            subject_scores=classification["subject_scores"],
            suggested_subject_id=classification["suggested_subject_id"],
            needs_confirmation=classification["needs_confirmation"],
        )
        return data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("user_files insert failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save file metadata")


@router.patch("/{file_id}/subject", response_model=FileResponse)
async def assign_subject(
    file_id: str,
    body: dict,
    authorization: str = Header(...),
):
    """
    El usuario confirma manualmente a qué asignatura pertenece el archivo.
    Body: { "subject_id": "uuid" }
    """
    user_id = get_user_id_from_token(authorization)
    subject_id = body.get("subject_id")
    if not subject_id:
        raise HTTPException(status_code=400, detail="subject_id is required")

    try:
        result = (
            supabase.table("user_files")
            .update({"subject_id": subject_id})
            .eq("id", file_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="File not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("assign_subject error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to update subject")


@router.post("/{file_id}/classify", response_model=FileClassificationResult)
async def reclassify_file(
    file_id: str,
    authorization: str = Header(...),
):
    """
    Re-ejecuta clasificación y enriquecimiento para un archivo ya subido.
    Útil si el usuario agrega asignaturas nuevas después de subir el archivo.
    """
    user_id = get_user_id_from_token(authorization)

    try:
        res = (
            supabase.table("user_files")
            .select("id, filename, extracted_text, content_type")
            .eq("id", file_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.error("reclassify fetch error: %s", exc)
        raise HTTPException(status_code=404, detail="File not found")

    if not res.data:
        raise HTTPException(status_code=404, detail="File not found")

    extracted_text = res.data.get("extracted_text")
    if not extracted_text:
        raise HTTPException(status_code=422, detail="File has no extracted text to classify")

    subjects = _get_user_subjects(user_id)
    classification = classify_and_enrich(extracted_text, res.data["filename"], subjects)

    now = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("user_files").update({
            "summary": classification["summary"] or None,
            "keywords": classification["keywords"] or None,
            "classification_scores": classification["subject_scores"] or None,
            "chunks": classification["chunks"] or None,
            "classified_at": now,
        }).eq("id", file_id).execute()
    except Exception as exc:
        logger.error("reclassify update error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save classification")

    return FileClassificationResult(
        subject_scores=classification["subject_scores"],
        suggested_subject_id=classification["suggested_subject_id"],
        needs_confirmation=classification["needs_confirmation"],
    )


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
