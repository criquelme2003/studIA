#!/usr/bin/env bash
# seed_users.sh — Crea usuarios de prueba en Supabase y verifica el backend.
#
# Uso:
#   bash seed_users.sh                         # crear usuarios
#   bash seed_users.sh --clean                 # borrar y recrear
#   bash seed_users.sh --only-clean            # solo borrar
#   bash seed_users.sh --url http://host:8000  # backend alternativo
#
# Requiere: curl, jq

set -euo pipefail

# ── Cargar .env ───────────────────────────────────────────────────────────────
ENV_FILE="$(dirname "$0")/.env"
if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r key val; do
    [[ "$key" =~ ^[[:space:]]*# ]] && continue   # comentarios
    [[ -z "$key" ]] && continue                  # líneas vacías
    val="${val%%#*}"                              # quitar comentarios inline
    val="${val%"${val##*[![:space:]]}"}"          # trim trailing spaces
    export "$key=$val"
  done < "$ENV_FILE"
fi

SUPABASE_URL="${SUPABASE_URL%/}"
SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-}"
BACKEND_URL="${BACKEND_URL:-https://presenciasur.com/studia/api}"

# ── Usuarios de prueba ────────────────────────────────────────────────────────
# Formato: "email|password|nombre"
USERS=(
  "carlos@studia.dev|Test1234!|Carlos Riquelme"
  "javier@studia.dev|Test1234!|Javier Curipan"
  "tomas@studia.dev|Test1234!|Tomás Curihual"
)

# ── Argumentos ────────────────────────────────────────────────────────────────
CLEAN=false
ONLY_CLEAN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean)      CLEAN=true ;;
    --only-clean) ONLY_CLEAN=true ;;
    --url)        BACKEND_URL="$2"; shift ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
  shift
done

# ── Validaciones ──────────────────────────────────────────────────────────────
if [[ -z "$SUPABASE_URL" || -z "$SERVICE_ROLE_KEY" ]]; then
  echo "ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar en el .env"
  exit 1
fi
command -v curl &>/dev/null || { echo "ERROR: curl no está instalado"; exit 1; }
command -v jq   &>/dev/null || { echo "ERROR: jq no está instalado";   exit 1; }

echo ""
echo "Supabase: $SUPABASE_URL"
echo "Backend:  $BACKEND_URL"
echo ""

# ── Helpers ───────────────────────────────────────────────────────────────────
# Headers de admin como array de bash para evitar problemas de quoting con JWTs
ADMIN_HEADERS=(
  -H "apikey: $SERVICE_ROLE_KEY"
  -H "Authorization: Bearer $SERVICE_ROLE_KEY"
  -H "Content-Type: application/json"
)

get_user_id_by_email() {
  local email="$1"
  curl -sf "${ADMIN_HEADERS[@]}" \
    "${SUPABASE_URL}/auth/v1/admin/users?per_page=1000" \
    | jq -r --arg email "$email" \
        '.users[] | select(.email == $email) | .id' 2>/dev/null || true
}

create_user() {
  local email="$1" password="$2" name="$3"
  local body
  body=$(jq -n \
    --arg e "$email" --arg p "$password" --arg n "$name" \
    '{email:$e, password:$p, email_confirm:true, user_metadata:{full_name:$n}}')

  local http_code body_resp
  body_resp=$(curl -s -o /tmp/_sb_resp.json -w "%{http_code}" \
    -X POST "${ADMIN_HEADERS[@]}" -d "$body" \
    "${SUPABASE_URL}/auth/v1/admin/users")
  http_code="$body_resp"
  body_resp=$(cat /tmp/_sb_resp.json)

  if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
    local uid
    uid=$(echo "$body_resp" | jq -r '.id')
    echo "  ✓ Creado: $email  (id: $uid)"
  elif echo "$body_resp" | grep -qi "already"; then
    echo "  · Ya existe: $email"
  else
    echo "  ✗ Error creando $email: HTTP $http_code"
    echo "    $(echo "$body_resp" | head -c 200)"
  fi
}

delete_user() {
  local user_id="$1" email="$2"
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X DELETE "${ADMIN_HEADERS[@]}" \
    "${SUPABASE_URL}/auth/v1/admin/users/${user_id}")

  if [[ "$http_code" == "200" || "$http_code" == "204" ]]; then
    echo "  ✓ Eliminado: $email"
  else
    echo "  ✗ No se pudo eliminar $email: HTTP $http_code"
  fi
}

sign_in() {
  local email="$1" password="$2"
  local body
  body=$(jq -n --arg e "$email" --arg p "$password" '{email:$e,password:$p}')

  curl -sf -X POST \
    -H "apikey: $SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -d "$body" \
    "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
    | jq -r '.access_token' 2>/dev/null || true
}

verify_backend() {
  local token="$1" email="$2"
  local body http_code body_resp
  body=$(jq -n --arg t "$token" '{access_token:$t}')

  body_resp=$(curl -s -o /tmp/_be_resp.json -w "%{http_code}" \
    -X POST -H "Content-Type: application/json" \
    -d "$body" "${BACKEND_URL}/api/auth/verify")
  http_code="$body_resp"
  body_resp=$(cat /tmp/_be_resp.json)

  if [[ "$http_code" == "200" ]]; then
    local uid
    uid=$(echo "$body_resp" | jq -r '.user_id')
    echo "  ✓ Backend OK — user_id: $uid  email: $email"
  else
    echo "  ✗ Backend rechazó el token de $email: HTTP $http_code"
    echo "    $(echo "$body_resp" | head -c 200)"
  fi
}

# ── Limpieza ──────────────────────────────────────────────────────────────────
if $CLEAN || $ONLY_CLEAN; then
  echo "=== Eliminando usuarios de prueba ==="
  for entry in "${USERS[@]}"; do
    IFS='|' read -r email _ _ <<< "$entry"
    uid=$(get_user_id_by_email "$email")
    if [[ -n "$uid" ]]; then
      delete_user "$uid" "$email"
    else
      echo "  · No encontrado: $email"
    fi
  done
  $ONLY_CLEAN && echo -e "\nListo.\n" && exit 0
  echo ""
fi

# ── Creación ──────────────────────────────────────────────────────────────────
echo "=== Creando usuarios de prueba ==="
for entry in "${USERS[@]}"; do
  IFS='|' read -r email password name <<< "$entry"
  create_user "$email" "$password" "$name"
done

# ── Verificación ──────────────────────────────────────────────────────────────
echo ""
echo "=== Verificando tokens contra $BACKEND_URL ==="
for entry in "${USERS[@]}"; do
  IFS='|' read -r email password _ <<< "$entry"
  token=$(sign_in "$email" "$password")
  if [[ -n "$token" && "$token" != "null" ]]; then
    verify_backend "$token" "$email"
  else
    echo "  ✗ Login fallido para $email"
  fi
done

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Credenciales de prueba ==="
for entry in "${USERS[@]}"; do
  IFS='|' read -r email password _ <<< "$entry"
  echo "  $email  /  $password"
done
echo ""
