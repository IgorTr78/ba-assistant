-- ══════════════════════════════════════════
-- BA Assistant — схема базы данных
-- Выполнить в Supabase → SQL Editor
-- ══════════════════════════════════════════

-- Расширения
create extension if not exists "uuid-ossp";
create extension if not exists "vector";       -- для pgvector (RAG)

-- ─────────────────────────────────────────
-- КОМАНДЫ И ПОЛЬЗОВАТЕЛИ
-- ─────────────────────────────────────────

create table if not exists teams (
  id          uuid primary key default uuid_generate_v4(),
  name        text not null,
  created_at  timestamptz default now()
);

create table if not exists team_members (
  team_id  uuid references teams(id) on delete cascade,
  user_id  uuid not null,   -- ссылается на auth.users
  role     text default 'analyst',
  primary key (team_id, user_id)
);

-- ─────────────────────────────────────────
-- ПРОЕКТЫ
-- ─────────────────────────────────────────

create table if not exists projects (
  id           uuid primary key default uuid_generate_v4(),
  name         text not null,
  description  text,
  color        text default '#005BFF',
  status       text default 'active' check (status in ('draft','active','archived')),
  team_id      uuid references teams(id) on delete set null,
  created_by   uuid not null,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- Автообновление updated_at
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger projects_updated_at
  before update on projects
  for each row execute function update_updated_at();

-- ─────────────────────────────────────────
-- СЕССИИ ЧАТА
-- ─────────────────────────────────────────

create table if not exists sessions (
  id          uuid primary key default uuid_generate_v4(),
  project_id  uuid references projects(id) on delete cascade,
  user_id     uuid not null,
  title       text default 'Новая сессия',
  messages    jsonb default '[]'::jsonb,  -- массив сообщений чата
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

create trigger sessions_updated_at
  before update on sessions
  for each row execute function update_updated_at();

create index if not exists idx_sessions_project on sessions(project_id);

-- ─────────────────────────────────────────
-- ЗАГРУЖЕННЫЕ ФАЙЛЫ
-- ─────────────────────────────────────────

create table if not exists uploaded_files (
  id             uuid primary key default uuid_generate_v4(),
  project_id     uuid references projects(id) on delete cascade,
  session_id     uuid references sessions(id) on delete set null,
  filename       text not null,
  file_type      text not null,    -- pdf | docx | bpmn | image
  storage_path   text not null,    -- путь в Supabase Storage
  extracted_text text,             -- извлечённый текст для RAG
  file_size      integer,          -- байты
  created_at     timestamptz default now()
);

create index if not exists idx_files_project on uploaded_files(project_id);
create index if not exists idx_files_session on uploaded_files(session_id);

-- ─────────────────────────────────────────
-- ТРЕБОВАНИЯ
-- ─────────────────────────────────────────

create table if not exists requirements (
  id              uuid primary key default uuid_generate_v4(),
  project_id      uuid references projects(id) on delete cascade,
  session_id      uuid references sessions(id) on delete set null,
  code            text not null,    -- FR-001, NFR-002 и т.д.
  type            text not null check (type in ('fr','nfr','br','oq')),
  content         text not null,
  version         integer default 1,
  source_message  text,             -- исходное сообщение пользователя
  created_by      uuid not null,
  created_at      timestamptz default now()
);

create index if not exists idx_req_project on requirements(project_id);
create index if not exists idx_req_type    on requirements(project_id, type);

-- ─────────────────────────────────────────
-- BPMN-СХЕМЫ
-- ─────────────────────────────────────────

create table if not exists bpmn_diagrams (
  id               uuid primary key default uuid_generate_v4(),
  project_id       uuid references projects(id) on delete cascade,
  requirement_ids  uuid[] default '{}',
  version          integer default 1,
  xml_content      text not null,
  edited_by        uuid,
  updated_at       timestamptz default now()
);

create index if not exists idx_bpmn_project on bpmn_diagrams(project_id);

-- ─────────────────────────────────────────
-- ЭКСПОРТИРОВАННЫЕ АРТЕФАКТЫ
-- ─────────────────────────────────────────

create table if not exists artifacts (
  id              uuid primary key default uuid_generate_v4(),
  project_id      uuid references projects(id) on delete cascade,
  requirement_id  uuid references requirements(id) on delete set null,
  bpmn_id         uuid references bpmn_diagrams(id) on delete set null,
  type            text not null check (type in ('word','pdf','bpmn')),
  storage_path    text not null,
  created_at      timestamptz default now()
);

-- ─────────────────────────────────────────
-- ВЕКТОРНЫЕ ЭМБЕДДИНГИ (для RAG)
-- ─────────────────────────────────────────

create table if not exists document_chunks (
  id          uuid primary key default uuid_generate_v4(),
  file_id     uuid references uploaded_files(id) on delete cascade,
  project_id  uuid references projects(id) on delete cascade,
  content     text not null,
  embedding   vector(1536),   -- OpenAI text-embedding-3-small размерность
  chunk_index integer,
  created_at  timestamptz default now()
);

create index if not exists idx_chunks_project on document_chunks(project_id);

-- Индекс для векторного поиска (IVFFlat)
create index if not exists idx_chunks_embedding
  on document_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- ─────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ─────────────────────────────────────────

alter table projects        enable row level security;
alter table sessions        enable row level security;
alter table uploaded_files  enable row level security;
alter table requirements    enable row level security;
alter table bpmn_diagrams   enable row level security;
alter table artifacts       enable row level security;

-- Политика: пользователь видит только свои проекты
-- (упрощённый вариант — без команд; доработать под team_members)
create policy "projects_owner" on projects
  for all using (auth.uid() = created_by);

create policy "sessions_owner" on sessions
  for all using (auth.uid() = user_id);

-- Файлы — через проект
create policy "files_via_project" on uploaded_files
  for all using (
    project_id in (
      select id from projects where created_by = auth.uid()
    )
  );

create policy "requirements_via_project" on requirements
  for all using (
    project_id in (
      select id from projects where created_by = auth.uid()
    )
  );

create policy "bpmn_via_project" on bpmn_diagrams
  for all using (
    project_id in (
      select id from projects where created_by = auth.uid()
    )
  );

-- ─────────────────────────────────────────
-- STORAGE BUCKETS
-- (выполнить отдельно в Supabase → Storage)
-- ─────────────────────────────────────────

-- insert into storage.buckets (id, name, public) values ('project-files', 'project-files', false);
-- insert into storage.buckets (id, name, public) values ('exports', 'exports', false);
