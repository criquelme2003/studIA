import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from routes import auth, notes, documents, files, chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Notes & Docs AI Backend",
    description="FastAPI proxy for notes, documents, file storage and Gemini AI chat.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(documents.router)
app.include_router(files.router)
app.include_router(chat.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
