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

class FileResponse(BaseModel):
    id: str
    user_id: str
    subject_id: Optional[str] = None
    filename: str
    storage_path: str
    content_type: str
    size: int
    feature: str
    extracted_text: Optional[str] = None
    extracted_at: Optional[str] = None
    item_id: Optional[str] = None
    created_at: str


# ── Chat (Gemini — existente) ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None   # "note_created" | "doc_created" | "ai_reply"
    data: Optional[dict] = None


# ── Chat DeepSeek ─────────────────────────────────────────────────────────────

class FileRef(BaseModel):
    file_id: str                        # uuid del archivo ya subido
    # el texto ya está en la BD — no hace falta mandarlo desde el cliente


class ChatDeepSeekRequest(BaseModel):
    prompt: str
    subject_id: Optional[str] = None   # si viene, se usa directo
    file_refs: Optional[List[FileRef]] = None  # archivos a incluir como contexto


class SuggestedSubject(BaseModel):
    id: str
    name: str


class ChatDeepSeekResponse(BaseModel):
    reply: str
    subject_id: Optional[str] = None           # el usado finalmente
    suggested_subject: Optional[SuggestedSubject] = None  # si el usuario debe confirmar
    action: Optional[str] = None
    data: Optional[dict] = None
