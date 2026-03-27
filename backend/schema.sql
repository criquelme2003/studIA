-- Run this in your Supabase SQL editor to create the required tables.
-- For existing databases, run the migration section at the bottom.

-- ── Subjects (Asignaturas) ────────────────────────────────────────────────────
create table if not exists subjects (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null,
  color       text not null default '#6366f1',  -- color hex para UI
  created_at  timestamptz not null default now()
);

alter table subjects enable row level security;

create policy "users can manage their own subjects"
  on subjects for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- ── Notes ─────────────────────────────────────────────────────────────────────
create table if not exists notes (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  subject_id  uuid references subjects(id) on delete set null,
  content     text not null,
  created_at  timestamptz not null default now()
);

alter table notes enable row level security;

create policy "users can manage their own notes"
  on notes for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- ── Documents ─────────────────────────────────────────────────────────────────
create table if not exists documents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  subject_id  uuid references subjects(id) on delete set null,
  title       text not null,
  body        text not null default '',
  created_at  timestamptz not null default now()
);

alter table documents enable row level security;

create policy "users can manage their own documents"
  on documents for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- ── File metadata ─────────────────────────────────────────────────────────────
create table if not exists user_files (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  subject_id      uuid references subjects(id) on delete set null,
  filename        text not null,
  storage_path    text not null unique,
  content_type    text not null default 'application/octet-stream',
  size            bigint not null default 0,
  feature         text not null default 'subject',
  extracted_text  text,                          -- texto extraído del archivo
  extracted_at    timestamptz,                   -- cuándo se extrajo
  item_id         uuid,                          -- referencia opcional a nota/doc
  created_at      timestamptz not null default now()
);

alter table user_files enable row level security;

create policy "users can manage their own files"
  on user_files for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- ── Storage bucket (crear una vez en Supabase dashboard) ──────────────────────
-- Bucket name: app-files  (privado)


-- ── MIGRACIÓN para bases de datos existentes ──────────────────────────────────
-- Ejecutar solo si las tablas ya existen:
--
-- create table if not exists subjects (
--   id uuid primary key default gen_random_uuid(),
--   user_id uuid not null references auth.users(id) on delete cascade,
--   name text not null,
--   color text not null default '#6366f1',
--   created_at timestamptz not null default now()
-- );
-- alter table subjects enable row level security;
-- create policy "users can manage their own subjects"
--   on subjects for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
--
-- alter table notes      add column if not exists subject_id uuid references subjects(id) on delete set null;
-- alter table documents  add column if not exists subject_id uuid references subjects(id) on delete set null;
-- alter table user_files add column if not exists subject_id uuid references subjects(id) on delete set null;
-- alter table user_files add column if not exists extracted_text text;
-- alter table user_files add column if not exists extracted_at timestamptz;
-- alter table user_files alter column feature set default 'subject';
