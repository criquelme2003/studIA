#!/usr/bin/env bash
# test_login.sh — Prueba el endpoint POST /auth/login
#
# Uso:
#   bash test_login.sh
#   bash test_login.sh carlos@studia.dev Test1234!

set -euo pipefail

EMAIL="${1:-carlos@studia.dev}"
PASSWORD="${2:-Test1234!}"
BASE_URL="${BACKEND_URL:-https://presenciasur.com/studia/api}"

echo "POST ${BASE_URL}/auth/login"
echo "Email: $EMAIL"
echo ""

curl -s -X POST "${BASE_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
  | jq .
