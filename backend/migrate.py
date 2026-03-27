#!/usr/bin/env python3
"""
migrate.py — Aplica la migración de base de datos en Supabase.
Crea la tabla subjects y agrega columnas nuevas a las tablas existentes.

Uso:
  python migrate.py
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

MIGRATION_SQL = """
-- Tabla subjects (asignaturas)
create table if not exists subjects (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  name       text not null,
  color      text not null default '#6366f1',
  created_at timestamptz not null default now()
);
alter table subjects enable row level security;
do $$ begin
  if not exists (
    select 1 from pg_policies where tablename='subjects' and policyname='users can manage their own subjects'
  ) then
    execute 'create policy "users can manage their own subjects" on subjects for all using (auth.uid() = user_id) with check (auth.uid() = user_id)';
  end if;
end $$;

-- Agregar subject_id a notas, documentos y archivos
alter table notes     add column if not exists subject_id uuid references subjects(id) on delete set null;
alter table documents add column if not exists subject_id uuid references subjects(id) on delete set null;

-- Agregar columnas nuevas a user_files
alter table user_files add column if not exists subject_id     uuid references subjects(id) on delete set null;
alter table user_files add column if not exists extracted_text text;
alter table user_files add column if not exists extracted_at   timestamptz;
"""


def run():
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar en el .env")
        sys.exit(1)

    # Supabase expone un endpoint SQL vía el rol postgres a través de postgrest
    # Solo funciona con la service_role key en modo administrador
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"

    # Intentar via RPC (requiere que exista la función exec_sql)
    r = requests.post(
        url,
        headers={
            "apikey": SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
        json={"sql": MIGRATION_SQL},
        timeout=15,
    )

    if r.status_code == 200:
        print("✓ Migración aplicada correctamente.")
        return

    # Si no existe exec_sql, mostrar instrucciones manuales
    print("─" * 60)
    print("No se puede aplicar la migración automáticamente.")
    print("Ejecuta el siguiente SQL en el Editor SQL de Supabase:")
    print(f"  {SUPABASE_URL.replace('https://', 'https://supabase.com/dashboard/project/').split('.')[0]}")
    print("─" * 60)
    print(MIGRATION_SQL)
    print("─" * 60)


if __name__ == "__main__":
    run()
