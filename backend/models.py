from pydantic import BaseModel
from typing import Optional, List


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: Optional[str] = None


class TokenPayload(BaseModel):
    access_token: str


class UserResponse(BaseModel):
    user_id: str
    email: Optional[str] = None


# ── Subjects (Asignaturas) ────────────────────────────────────────────────────

class SubjectCreate(BaseModel):
    name: str
    color: str = "#6366f1"


class SubjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    color: str
    created_at: str


# ── Notes ─────────────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str
    subject_id: Optional[str] = None


class NoteResponse(BaseModel):
    id: str
    user_id: str
    subject_id: Optional[str] = None
    content: str
    created_at: str


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: str
    body: str
    subject_id: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    subject_id: Optional[str] = None
    title: str
    body: str
    created_at: str


# ── Files ─────────────────────────────────────────────────────────────────────

class FileClassificationResult(BaseModel):
    """Resultado de clasificación devuelto al cliente tras subir o re-clasificar un archivo."""
    subject_scores: Optional[dict] = None        # {subject_id: float}
    suggested_subject_id: Optional[str] = None  # asignado automáticamente si score >= umbral
    needs_confirmation: bool = False             # True → el cliente debe preguntar al usuario


class FileResponse(BaseModel):
    id: str
    user_id: str
    subject_id: Optional[str] = None
    filename: str
    storage_path: str
    content_type: str
    size: int
    feature: str
    summary: Optional[str] = None
    keywords: Optional[list] = None
    extracted_text: Optional[str] = None
    extracted_at: Optional[str] = None
    classified_at: Optional[str] = None
    item_id: Optional[str] = None
    created_at: str
    classification: Optional[FileClassificationResult] = None  # solo en la respuesta de upload


# ── Chat (Gemini — existente) ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None
    data: Optional[dict] = None


# ── Chat DeepSeek ─────────────────────────────────────────────────────────────

class CalendarEvent(BaseModel):
    """Evento de calendario tal como lo maneja Expo Calendar en el cliente."""
    id: Optional[str] = None        # ID local de Expo Calendar (solo en eventos existentes)
    title: str
    start: str                      # ISO 8601 — "2026-04-02T10:00:00"
    end: str
    location: Optional[str] = None
    notes: Optional[str] = None


class ChatDeepSeekRequest(BaseModel):
    prompt: str
    subject_id: Optional[str] = None       # filtro de búsqueda de archivos (opcional)
    current_date: Optional[str] = None     # ISO 8601 — lo manda el cliente para contexto temporal
    events: Optional[List[CalendarEvent]] = None  # eventos actuales del calendario (ventana ±30 días)


class SourceRef(BaseModel):
    """Archivo del que se extrajo información para responder."""
    file_id: str
    filename: str
    subject_name: Optional[str] = None


class SuggestedSubject(BaseModel):
    id: str
    name: str


class ChatDeepSeekResponse(BaseModel):
    reply: str
    # Estudio
    sources: Optional[List[SourceRef]] = None
    subject_id: Optional[str] = None
    suggested_subject: Optional[SuggestedSubject] = None
    # Calendario
    action: Optional[str] = None           # "create" | "update" | "delete" | "ai_reply"
    event: Optional[CalendarEvent] = None  # evento a crear/actualizar
    event_id: Optional[str] = None         # ID Expo del evento a actualizar/eliminar
