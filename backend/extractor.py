"""
extractor.py — Extrae texto de PDFs y documentos DOCX.
Usado por routes/files.py al momento de subir un archivo.
"""
import io
import logging

logger = logging.getLogger(__name__)

# Límite de caracteres para no saturar el contexto de la IA (~40k tokens aprox)
MAX_CHARS = 120_000


def extract_text(content: bytes, content_type: str, filename: str) -> str | None:
    """
    Intenta extraer texto plano del archivo.
    Devuelve el texto (truncado si es muy largo) o None si no aplica.
    """
    ct = content_type.lower()
    name = filename.lower()

    # ── PDF ───────────────────────────────────────────────────────────────────
    if ct == "application/pdf" or name.endswith(".pdf"):
        return _extract_pdf(content)

    # ── DOCX ──────────────────────────────────────────────────────────────────
    if ct in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or name.endswith((".docx", ".doc")):
        return _extract_docx(content)

    return None


def _extract_pdf(content: bytes) -> str | None:
    try:
        import fitz  # pymupdf

        doc = fitz.open(stream=content, filetype="pdf")
        parts = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                parts.append(text)
        doc.close()

        full = "\n\n".join(parts).strip()
        if not full:
            return None
        return _truncate(full)
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return None


def _extract_docx(content: bytes) -> str | None:
    try:
        from docx import Document

        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full = "\n".join(paragraphs).strip()
        if not full:
            return None
        return _truncate(full)
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        return None


def _truncate(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text
    logger.info("Extracted text truncated from %d to %d chars", len(text), MAX_CHARS)
    return text[:MAX_CHARS] + "\n\n[... texto truncado por longitud máxima ...]"
