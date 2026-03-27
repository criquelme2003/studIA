# studIA — FastAPI Backend

Backend para una aplicación de estudio orientada a estudiantes universitarios.
Usa **Supabase** (DB + Storage), **DeepSeek** como motor de IA principal y **Gemini 2.5 Flash Lite** como alternativa.

---

## Estructura

```
backend/
├── main.py                # App FastAPI + middlewares
├── config.py              # Variables de entorno
├── database.py            # Cliente Supabase (service role)
├── models.py              # Pydantic models
├── extractor.py           # Extracción de texto de PDF/DOCX
├── routes/
│   ├── auth.py            # POST /auth/login, POST /auth/verify
│   ├── subjects.py        # CRUD /subjects (asignaturas)
│   ├── notes.py           # CRUD /notes
│   ├── documents.py       # CRUD /documents
│   ├── files.py           # Upload/delete /files (con extracción de texto)
│   ├── chat.py            # POST /chat (Gemini + comandos)
│   └── chat_deepseek.py   # POST /chat/deepseek (DeepSeek + contexto de archivos)
├── schema.sql             # Schema completo para Supabase
├── migrate.py             # Script de migración para bases existentes
├── seed_users.sh          # Crea usuarios de prueba
├── test_login.sh          # Prueba el endpoint de login
├── test_api.sh            # Prueba todos los endpoints
├── requirements.txt
└── .env.example
```

---

## Instalación

### Docker (recomendado)

```bash
cd /root/studIA
docker compose up -d --build
```

### Local

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## Configuración

Copia `.env.example` a `.env` y rellena los valores:

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
GEMINI_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
SECRET_KEY=una-clave-secreta-aleatoria
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

> Usa la `service_role` key (no la `anon`).
> Supabase Dashboard → Project Settings → API → Service role secret.

### Base de datos

**Primera vez** — ejecuta `schema.sql` completo en el SQL Editor de Supabase.

**Migración desde schema anterior** — ejecuta solo la sección de migración al final de `schema.sql`, o usa el script:

```bash
python migrate.py
```

Luego crea el bucket **`app-files`** en Supabase Storage (privado).

---

## Endpoints

Todos los endpoints (excepto `/health` y `/auth/login`) requieren:
```
Authorization: Bearer <supabase-access-token>
```

### Auth

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/auth/login` | Login con email y contraseña → devuelve `access_token` |
| `POST` | `/auth/verify` | Verificar token Supabase existente |

### Asignaturas

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/subjects` | Listar asignaturas del usuario |
| `POST` | `/subjects` | Crear asignatura (`name`, `color`) |
| `DELETE` | `/subjects/{id}` | Eliminar asignatura |
| `GET` | `/subjects/{id}/files` | Listar archivos de una asignatura |

### Notas

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/notes` | Listar notas |
| `POST` | `/notes` | Crear nota (`content`, `subject_id?`) |
| `DELETE` | `/notes/{id}` | Eliminar nota |

### Documentos

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/documents` | Listar documentos |
| `POST` | `/documents` | Crear documento (`title`, `body`, `subject_id?`) |
| `DELETE` | `/documents/{id}` | Eliminar documento |

### Archivos

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/files/upload` | Subir archivo multipart — extrae texto automáticamente de PDF/DOCX |
| `DELETE` | `/files/{id}` | Eliminar archivo |

**Campos de `/files/upload`:**
```
file        — archivo (PDF, DOCX)
subject_id  — (opcional) UUID de la asignatura
feature     — (opcional, default: "subject")
item_id     — (opcional) referencia a nota/documento
```

### Chat

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/chat` | Chat con Gemini 2.5 Flash Lite + comandos `/note` y `/doc` |
| `POST` | `/chat/deepseek` | Chat con DeepSeek con contexto de archivos y clasificación automática |

---

## Chat DeepSeek — flujo de estudio

El endpoint `/chat/deepseek` está diseñado para el flujo principal de la app:

```json
POST /chat/deepseek
{
  "prompt": "¿Cuál es la diferencia entre mitosis y meiosis?",
  "subject_id": "uuid-opcional",
  "file_refs": [
    { "file_id": "uuid-de-archivo-subido" }
  ]
}
```

**Comportamiento:**

- Si se envía `subject_id` → se usa directamente como contexto.
- Si **no** se envía `subject_id` → DeepSeek clasifica la pregunta entre las asignaturas del usuario y devuelve `suggested_subject` para que la app confirme con el usuario.
- Si se envían `file_refs` → el backend recupera el `extracted_text` de esos archivos y lo incluye en el prompt como material de estudio.

**Respuesta:**
```json
{
  "reply": "Según el material...",
  "subject_id": "uuid",
  "suggested_subject": { "id": "uuid", "name": "Biología Celular" },
  "action": "ai_reply"
}
```

---

## Chat Gemini — comandos especiales

| Prompt | Acción |
|--------|--------|
| `/note <texto>` | Crea una nota |
| `/doc <título> \| <cuerpo>` | Crea un documento |
| cualquier otro texto | Consulta a Gemini 2.5 Flash Lite |

---

## Extracción de texto

El módulo `extractor.py` procesa archivos automáticamente al subirlos:

| Tipo | Librería | Soporta escaneados |
|------|----------|--------------------|
| PDF con texto embebido | `pymupdf` | No |
| PDF escaneado | `pymupdf` (parcial) | Parcial |
| DOCX | `python-docx` | N/A |

El texto extraído se guarda en `user_files.extracted_text` (máx. 120.000 caracteres).

---

## Despliegue

El backend corre en Docker detrás de Nginx:

```
https://presenciasur.com/studia/api/ → http://127.0.0.1:7780/
```

Para actualizar tras cambios en el código:

```bash
cd /root/studIA
docker compose up -d --build
```

---

## Seguridad

- El backend valida el `user_id` en cada operación — los usuarios solo acceden a sus propios datos.
- RLS habilitado en Supabase como segunda capa de protección.
- Los tokens se verifican con `supabase.auth.get_user()` en cada request.
- Las API keys (DeepSeek, Gemini) nunca se exponen al cliente.
