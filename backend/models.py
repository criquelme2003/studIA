from pydantic import BaseModel
from typing import Optional


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    access_token: str


class UserResponse(BaseModel):
    user_id: str
    email: Optional[str] = None


# ── Notes ─────────────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id: str
    user_id: str
    content: str
    created_at: str


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: str
    body: str


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    created_at: str


# ── Files ─────────────────────────────────────────────────────────────────────

class FileResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    storage_path: str
    content_type: str
    size: int
    feature: str
    item_id: Optional[str] = None
    created_at: str


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None   # "note_created" | "doc_created" | "ai_reply"
    data: Optional[dict] = None
