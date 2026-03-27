#!/usr/bin/env python3
"""
seed_users.py — Crea usuarios de prueba en Supabase y verifica el backend.

Uso:
  python seed_users.py                        # crea los usuarios por defecto
  python seed_users.py --url http://...:8000  # apunta a otro host
  python seed_users.py --clean                # borra los usuarios de prueba antes de crearlos

Requiere: pip install python-dotenv requests
"""

import argparse
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Configuración ─────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

TEST_USERS = [
    {"email": "carlos@studia.dev", "password": "Test1234!", "name": "Carlos Riquelme"},
    {"email": "javier@studia.dev", "password": "Test1234!", "name": "Javier curipan"},
    {"email": "tomas@studia.dev", "password": "Test1234!", "name": "Tomás Curihual"},
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def supabase_admin_headers() -> dict:
    return {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def create_user(email: str, password: str, name: str) -> dict | None:
    """Crea un usuario vía Supabase Admin API."""
    url = f"{SUPABASE_URL}/auth/v1/admin/users"
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": name},
    }
    r = requests.post(url, json=payload, headers=supabase_admin_headers(), timeout=10)
    if r.status_code in (200, 201):
        data = r.json()
        print(f"  ✓ Creado: {email}  (id: {data['id']})")
        return data
    elif r.status_code == 422 and "already" in r.text.lower():
        print(f"  · Ya existe: {email}")
        return get_user_by_email(email)
    else:
        print(f"  ✗ Error creando {email}: {r.status_code} — {r.text[:200]}")
        return None


def get_user_by_email(email: str) -> dict | None:
    """Busca un usuario por email en la Admin API."""
    url = f"{SUPABASE_URL}/auth/v1/admin/users"
    r = requests.get(url, headers=supabase_admin_headers(), timeout=10)
    if r.status_code != 200:
        return None
    users = r.json().get("users", [])
    for u in users:
        if u.get("email") == email:
            return u
    return None


def delete_user(user_id: str, email: str) -> None:
    """Elimina un usuario por su UUID."""
    url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"
    r = requests.delete(url, headers=supabase_admin_headers(), timeout=10)
    if r.status_code in (200, 204):
        print(f"  ✓ Eliminado: {email}")
    else:
        print(f"  ✗ No se pudo eliminar {email}: {r.status_code}")


def sign_in(email: str, password: str) -> str | None:
    """Obtiene un access_token mediante email/password."""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }
    r = requests.post(url, json={"email": email, "password": password}, headers=headers, timeout=10)
    if r.status_code == 200:
        return r.json().get("access_token")
    print(f"  ✗ Login fallido para {email}: {r.status_code} — {r.text[:200]}")
    return None


def verify_backend(backend_url: str, token: str, email: str) -> None:
    """Verifica el token contra el endpoint /api/auth/verify del backend."""
    url = f"{backend_url}/api/auth/verify"
    r = requests.post(url, json={"access_token": token}, timeout=10)
    if r.status_code == 200:
        data = r.json()
        print(f"  ✓ Backend OK — user_id: {data['user_id']}  email: {data['email']}")
    else:
        print(f"  ✗ Backend rechazó el token de {email}: {r.status_code} — {r.text[:200]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de usuarios de prueba para studIA")
    parser.add_argument("--url", default=DEFAULT_BACKEND_URL, help="URL base del backend (default: %(default)s)")
    parser.add_argument("--clean", action="store_true", help="Eliminar los usuarios de prueba antes de crearlos")
    parser.add_argument("--only-clean", action="store_true", help="Solo eliminar los usuarios de prueba y salir")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar en el .env")
        sys.exit(1)

    print(f"\nSupabase: {SUPABASE_URL}")
    print(f"Backend:  {args.url}\n")

    # ── Limpieza opcional ──────────────────────────────────────────────────────
    if args.clean or args.only_clean:
        print("=== Eliminando usuarios de prueba ===")
        for u in TEST_USERS:
            existing = get_user_by_email(u["email"])
            if existing:
                delete_user(existing["id"], u["email"])
            else:
                print(f"  · No encontrado: {u['email']}")
        if args.only_clean:
            print("\nListo.\n")
            return

    # ── Creación ───────────────────────────────────────────────────────────────
    print("=== Creando usuarios de prueba ===")
    created = []
    for u in TEST_USERS:
        user_data = create_user(u["email"], u["password"], u["name"])
        if user_data:
            created.append((u["email"], u["password"]))

    # ── Verificación contra el backend ─────────────────────────────────────────
    print(f"\n=== Verificando tokens contra {args.url} ===")
    for email, password in created:
        token = sign_in(email, password)
        if token:
            verify_backend(args.url, token, email)

    # ── Resumen ────────────────────────────────────────────────────────────────
    print("\n=== Credenciales de prueba ===")
    for u in TEST_USERS:
        print(f"  {u['email']}  /  {u['password']}")
    print()


if __name__ == "__main__":
    main()
