#!/usr/bin/env bash
# test_api.sh — Prueba todos los endpoints del backend studIA.
#
# Uso:
#   bash test_api.sh
#   bash test_api.sh javier@studia.dev Test1234!

set -euo pipefail

EMAIL="${1:-carlos@studia.dev}"
PASSWORD="${2:-Test1234!}"
BASE="${BACKEND_URL:-https://presenciasur.com/studia/api}"

G='\033[0;32m'; R='\033[0;31m'; B='\033[0;34m'; Y='\033[0;33m'; N='\033[0m'

ok()   { echo -e "${G}  ✓ $*${N}"; }
fail() { echo -e "${R}  ✗ $*${N}"; }
hdr()  { echo -e "\n${B}══ $* ${N}"; }

check() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    ok "$label → HTTP $actual"
  else
    fail "$label → esperado $expected, got $actual"
  fi
}

# Ejecuta curl, imprime la respuesta y guarda el código HTTP en $CODE
req() {
  local method="$1"; shift
  local url="$1";    shift
  # resto de args son flags extra de curl
  CODE=$(curl -s -o /tmp/_r.json -w "%{http_code}" -X "$method" "$@" "$url")
  jq . /tmp/_r.json 2>/dev/null || cat /tmp/_r.json
  echo
}

AUTH=()  # se rellena tras el login

# ── 0. Health ─────────────────────────────────────────────────────────────────
hdr "0. Health"
req GET "$BASE/health"
check "GET /health" "200" "$CODE"

# ── 1. Login ──────────────────────────────────────────────────────────────────
hdr "1. Login  ($EMAIL)"
req POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
check "POST /auth/login" "200" "$CODE"

TOKEN=$(jq -r '.access_token' /tmp/_r.json)
if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  fail "No se obtuvo token — abortando"; exit 1
fi
echo -e "${Y}  token: ${TOKEN:0:40}...${N}"
AUTH=(-H "Authorization: Bearer $TOKEN")

# ── 2. Notes ──────────────────────────────────────────────────────────────────
hdr "2. Notes"

echo "  → GET /notes"
req GET "$BASE/notes" "${AUTH[@]}"
check "GET /notes" "200" "$CODE"

echo "  → POST /notes"
req POST "$BASE/notes" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"content":"Nota de prueba desde test_api.sh"}'
check "POST /notes" "201" "$CODE"
NOTE_ID=$(jq -r '.id' /tmp/_r.json)
ok "note_id: $NOTE_ID"

echo "  → DELETE /notes/$NOTE_ID"
req DELETE "$BASE/notes/$NOTE_ID" "${AUTH[@]}"
check "DELETE /notes/:id" "204" "$CODE"

# ── 3. Documents ──────────────────────────────────────────────────────────────
hdr "3. Documents"

echo "  → GET /documents"
req GET "$BASE/documents" "${AUTH[@]}"
check "GET /documents" "200" "$CODE"

echo "  → POST /documents"
req POST "$BASE/documents" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Doc de prueba","body":"Cuerpo del documento de prueba."}'
check "POST /documents" "201" "$CODE"
DOC_ID=$(jq -r '.id' /tmp/_r.json)
ok "doc_id: $DOC_ID"

echo "  → DELETE /documents/$DOC_ID"
req DELETE "$BASE/documents/$DOC_ID" "${AUTH[@]}"
check "DELETE /documents/:id" "204" "$CODE"

# ── 4. Chat ───────────────────────────────────────────────────────────────────
hdr "4. Chat"

echo "  → POST /chat (texto libre → Gemini)"
req POST "$BASE/chat" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Responde solo: ok"}'
check "POST /chat (ai_reply)" "200" "$CODE"

echo "  → POST /chat (/note comando)"
req POST "$BASE/chat" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"/note Nota creada por chat de prueba"}'
check "POST /chat (/note)" "200" "$CODE"
CHAT_NOTE_ID=$(jq -r '.data.id // empty' /tmp/_r.json)
if [[ -n "$CHAT_NOTE_ID" ]]; then
  curl -s -o /dev/null -X DELETE "${AUTH[@]}" "$BASE/notes/$CHAT_NOTE_ID"
  ok "nota de chat eliminada ($CHAT_NOTE_ID)"
fi

echo "  → POST /chat (/doc comando)"
req POST "$BASE/chat" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"/doc Título prueba | Cuerpo de prueba desde chat"}'
check "POST /chat (/doc)" "200" "$CODE"
CHAT_DOC_ID=$(jq -r '.data.id // empty' /tmp/_r.json)
if [[ -n "$CHAT_DOC_ID" ]]; then
  curl -s -o /dev/null -X DELETE "${AUTH[@]}" "$BASE/documents/$CHAT_DOC_ID"
  ok "doc de chat eliminado ($CHAT_DOC_ID)"
fi

# ── 5. Files ──────────────────────────────────────────────────────────────────
hdr "5. Files"

echo "  → POST /files/upload"
echo "archivo de prueba" > /tmp/test_upload.txt
req POST "$BASE/files/upload" "${AUTH[@]}" \
  -F "file=@/tmp/test_upload.txt;type=text/plain" \
  -F "feature=test"
check "POST /files/upload" "201" "$CODE"
FILE_ID=$(jq -r '.id' /tmp/_r.json)
ok "file_id: $FILE_ID"

echo "  → DELETE /files/$FILE_ID"
req DELETE "$BASE/files/$FILE_ID" "${AUTH[@]}"
check "DELETE /files/:id" "204" "$CODE"

# ── Resumen ───────────────────────────────────────────────────────────────────
echo -e "\n${G}══ Todos los endpoints probados ══${N}\n"
