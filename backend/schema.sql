-- Run this in your Supabase SQL editor to create the required tables.

-- Notes
create table if not exists notes (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  content     text not null,
  created_at  timestamptz not null default now()
);

alter table notes enable row level security;

create policy "users can manage their own notes"
  on notes for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- Documents
create table if not exists documents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  title       text not null,
  body        text not null default '',
  created_at  timestamptz not null default now()
);

alter table documents enable row level security;

create policy "users can manage their own documents"
  on documents for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- File metadata
create table if not exists user_files (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  filename      text not null,
  storage_path  text not null unique,
  content_type  text not null default 'application/octet-stream',
  size          bigint not null default 0,
  feature       text not null,          -- e.g. 'notes', 'documents', 'avatar'
  item_id       uuid,                   -- optional reference to note/document id
  created_at    timestamptz not null default now()
);

alter table user_files enable row level security;

create policy "users can manage their own files"
  on user_files for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- Storage bucket (run once via Supabase dashboard or API)
-- Bucket name: app-files  (set to private)
