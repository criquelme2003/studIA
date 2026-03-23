# API Reference — Notes & Docs AI Backend

Base URL: `http://localhost:8000`
Todos los endpoints protegidos requieren el header:
```
Authorization: Bearer <supabase_access_token>
```

---

## Auth

### Verificar token
```
POST /api/auth/verify
```
Verifica un access token de Supabase y devuelve el usuario.

**Body**
```json
{ "access_token": "eyJ..." }
```

**Response 200**
```json
{
  "user_id": "34e3278c-5534-4bb5-b683-875f0fde8c37",
  "email": "user@example.com"
}
```

**Errors:** `401` token inválido o expirado.

---

## Notes

### Listar notas
```
GET /api/notes
```
Devuelve las notas del usuario autenticado, ordenadas de más reciente a más antigua.

**Response 200**
```json
[
  {
    "id": "05b11343-2596-4a28-b582-8c0015911b91",
    "user_id": "34e3278c-...",
    "content": "Texto de la nota",
    "created_at": "2026-03-23T17:31:27.458089+00:00"
  }
]
```

---

### Crear nota
```
POST /api/notes
```

**Body**
```json
{ "content": "Texto de la nota" }
```

**Response 201**
```json
{
  "id": "05b11343-2596-4a28-b582-8c0015911b91",
  "user_id": "34e3278c-...",
  "content": "Texto de la nota",
  "created_at": "2026-03-23T17:31:27.458089+00:00"
}
```

---

### Eliminar nota
```
DELETE /api/notes/{note_id}
```

**Response 204** — sin cuerpo.
**Errors:** `404` nota no encontrada o no pertenece al usuario.

---

## Documents

### Listar documentos
```
GET /api/documents
```
Devuelve los documentos del usuario, ordenados de más reciente a más antiguo.

**Response 200**
```json
[
  {
    "id": "d1a943be-3785-4ae5-bc47-448c22562d21",
    "user_id": "34e3278c-...",
    "title": "Título del documento",
    "body": "Cuerpo del documento",
    "created_at": "2026-03-23T17:31:38.939416+00:00"
  }
]
```

---

### Crear documento
```
POST /api/documents
```

**Body**
```json
{
  "title": "Título del documento",
  "body": "Cuerpo del documento"
}
```

**Response 201**
```json
{
  "id": "d1a943be-3785-4ae5-bc47-448c22562d21",
  "user_id": "34e3278c-...",
  "title": "Título del documento",
  "body": "Cuerpo del documento",
  "created_at": "2026-03-23T17:31:38.939416+00:00"
}
```

---

### Eliminar documento
```
DELETE /api/documents/{doc_id}
```

**Response 204** — sin cuerpo.
**Errors:** `404` documento no encontrado o no pertenece al usuario.

---

## Files

### Subir archivo
```
POST /api/files/upload
```
`Content-Type: multipart/form-data`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file` | File | ✅ | Archivo a subir |
| `feature` | string | ✅ | Contexto del archivo: `notes`, `documents`, `avatar`, etc. |
| `item_id` | string | ❌ | UUID del recurso relacionado (nota o documento) |

El archivo se guarda en Supabase Storage con el path:
`{user_id}/{feature}/{item_id o "general"}/{uuid}.{ext}`

**Response 201**
```json
{
  "id": "5996b10d-9960-470a-9ddc-f9714f24cd0d",
  "user_id": "34e3278c-...",
  "filename": "foto.png",
  "storage_path": "34e3278c-.../notes/abc123/uuid.png",
  "content_type": "image/png",
  "size": 204800,
  "feature": "notes",
  "item_id": "abc123",
  "created_at": "2026-03-23T17:33:02.979029+00:00"
}
```

**Errors:** `500` fallo en Storage o en DB.

---

### Eliminar archivo
```
DELETE /api/files/{file_id}
```
Elimina el archivo de Supabase Storage y su registro en la base de datos.

**Response 204** — sin cuerpo.
**Errors:** `404` archivo no encontrado o no pertenece al usuario.

---

## Chat / IA

### Enviar mensaje
```
POST /api/chat
```

**Body**
```json
{ "prompt": "..." }
```

El endpoint interpreta el prompt y ejecuta una de tres acciones:

| Prompt | Acción | `action` en respuesta |
|--------|--------|-----------------------|
| `/note <texto>` | Crea una nota | `note_created` |
| `/doc <título> \| <cuerpo>` | Crea un documento | `doc_created` |
| Cualquier otro texto | Consulta a Gemini 2.5 Flash Lite | `ai_reply` |

**Response 200 — respuesta de Gemini**
```json
{
  "reply": "Python es un lenguaje de programación...",
  "action": "ai_reply",
  "data": null
}
```

**Response 200 — /note**
```json
{
  "reply": "Note saved: \"Recordar revisar el esquema\"",
  "action": "note_created",
  "data": {
    "id": "503bcf34-...",
    "user_id": "34e3278c-...",
    "content": "Recordar revisar el esquema",
    "created_at": "2026-03-23T17:32:35.802988+00:00"
  }
}
```

**Response 200 — /doc**
```json
{
  "reply": "Document \"Arquitectura\" saved.",
  "action": "doc_created",
  "data": {
    "id": "8326e492-...",
    "user_id": "34e3278c-...",
    "title": "Arquitectura",
    "body": "El backend usa FastAPI...",
    "created_at": "2026-03-23T17:32:36.677103+00:00"
  }
}
```

**Errors:** `400` formato de comando inválido · `502` fallo al contactar Gemini.

---

## Códigos de error comunes

| Código | Significado |
|--------|-------------|
| `401` | Token ausente, inválido o expirado |
| `404` | Recurso no encontrado o no pertenece al usuario |
| `400` | Datos del request incorrectos |
| `502` | Error al contactar la API de Gemini |
| `500` | Error interno del servidor |

---

## Notas de integración

- El token se obtiene con el SDK de Supabase en el cliente (`supabase.auth.signInWithPassword()`). El campo a enviar al backend es `session.access_token`.
- Los tokens de Supabase expiran en 1 hora. Usar `session.refresh_token` para renovarlos.
- Todos los campos `id` y `user_id` son UUIDs en formato string.
- Los campos `created_at` están en formato ISO 8601 UTC.
