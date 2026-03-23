# Notes & Docs AI — FastAPI Backend

FastAPI proxy backend para la aplicación de notas y documentos con IA.
Usa **Supabase** (DB + Storage) y **Gemini 2.5 Flash Lite** como motor de IA.

---

## Estructura

```
backend/
├── main.py           # App FastAPI + middlewares
├── config.py         # Variables de entorno
├── database.py       # Cliente Supabase (service role)
├── models.py         # Pydantic models
├── routes/
│   ├── auth.py       # POST /api/auth/verify
│   ├── notes.py      # CRUD /api/notes
│   ├── documents.py  # CRUD /api/documents
│   ├── files.py      # Upload/delete /api/files
│   └── chat.py       # POST /api/chat (Gemini proxy)
├── schema.sql        # SQL para crear las tablas en Supabase
├── requirements.txt
└── .env.example
```

---

## Instalación

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuración

1. Copia `.env.example` a `.env` y rellena los valores:

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
GEMINI_API_KEY=AIza...
SECRET_KEY=una-clave-secreta-aleatoria
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

> **Importante:** usa la `service_role` key (no la `anon`). Está en
> Supabase Dashboard → Project Settings → API → Service role secret.

2. Ejecuta el SQL en el **SQL Editor** de Supabase:

```bash
# o pégalo directamente en el dashboard
cat schema.sql
```

3. Crea el bucket **`app-files`** en Supabase Storage (privado).

---

## Ejecutar

```bash
uvicorn main:app --reload --port 8000
```

Swagger UI disponible en [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/auth/verify` | Verificar token Supabase |
| `GET` | `/api/notes` | Listar notas del usuario |
| `POST` | `/api/notes` | Crear nota |
| `DELETE` | `/api/notes/{note_id}` | Eliminar nota |
| `GET` | `/api/documents` | Listar documentos |
| `POST` | `/api/documents` | Crear documento |
| `DELETE` | `/api/documents/{doc_id}` | Eliminar documento |
| `POST` | `/api/files/upload` | Subir archivo (multipart) |
| `DELETE` | `/api/files/{file_id}` | Eliminar archivo |
| `POST` | `/api/chat` | Chat con IA / comandos |

Todos los endpoints (excepto `/health` y `/api/auth/verify`) requieren:

```
Authorization: Bearer <supabase-access-token>
```

---

## Chat — comandos especiales

| Prompt | Acción |
|--------|--------|
| `/note <texto>` | Crea una nota con ese texto |
| `/doc <título> \| <cuerpo>` | Crea un documento |
| cualquier otro texto | Consulta a Gemini 2.5 Flash Lite |

---

## Seguridad

- El backend usa la `service_role` key para operaciones DB, pero **valida el `user_id`** en cada operación para garantizar que los usuarios solo acceden a sus propios datos.
- Las tablas tienen **RLS habilitado** en Supabase como segunda capa de protección frente a accesos directos.
- Los tokens de Supabase se verifican con `supabase.auth.get_user()` en cada request protegido.
- La Gemini API key nunca se expone al cliente.
