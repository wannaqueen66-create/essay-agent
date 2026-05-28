create extension if not exists vector;

create table if not exists public.essay_agent_papers (
  id text primary key,
  source text not null,
  source_paper_id text,
  doi text,
  version text,
  title text not null,
  abstract text,
  authors jsonb not null default '[]'::jsonb,
  primary_category text,
  categories jsonb not null default '[]'::jsonb,
  published timestamptz,
  link text,
  analysis jsonb not null default '{}'::jsonb,
  chinese_summary text,
  domain_query text,
  domain_relevance_score int not null default 0,
  analysis_status text,
  meets_threshold boolean not null default false,
  eligible_for_pending boolean not null default false,
  displayed_at timestamptz,
  reported_at timestamptz,
  content_hash text,
  essay_agent_meta jsonb not null default '{}'::jsonb,
  embedding vector(384),
  embedding_model text,
  embedding_dim int,
  embedding_updated_at timestamptz,
  updated_at timestamptz not null default now()
);

create index if not exists essay_agent_papers_source_published_idx
  on public.essay_agent_papers (source, published desc);

create index if not exists essay_agent_papers_published_idx
  on public.essay_agent_papers (published desc);

create index if not exists essay_agent_papers_domain_score_idx
  on public.essay_agent_papers (domain_relevance_score desc, published desc);

create index if not exists essay_agent_papers_title_abstract_fts_idx
  on public.essay_agent_papers
  using gin (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, '') || ' ' || coalesce(chinese_summary, '')));

create index if not exists essay_agent_papers_embedding_hnsw_idx
  on public.essay_agent_papers
  using hnsw (embedding vector_cosine_ops);

create table if not exists public.essay_agent_daily_runs (
  id text primary key,
  run_date date not null,
  paper_count int not null default 0,
  stats jsonb not null default '{}'::jsonb,
  backup_path text,
  updated_at timestamptz not null default now()
);

create table if not exists public.scholarlens_users (
  email text primary key,
  role text not null default 'member',
  is_active boolean not null default true,
  source text not null default 'manual',
  quota_policy jsonb not null default '{}'::jsonb,
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint scholarlens_users_email_lowercase check (email = lower(email)),
  constraint scholarlens_users_role_check check (role in ('admin', 'member'))
);

create table if not exists public.user_paper_states (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  paper_id text not null,
  source_table text not null default 'essay_agent_papers',
  is_favorite boolean not null default false,
  is_read boolean not null default false,
  note text,
  preference_tags jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, paper_id, source_table)
);

alter table public.user_paper_states alter column user_id set default auth.uid();

alter table public.essay_agent_papers enable row level security;
alter table public.essay_agent_daily_runs enable row level security;
alter table public.scholarlens_users enable row level security;
alter table public.user_paper_states enable row level security;

create or replace function public.is_scholarlens_user()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.scholarlens_users u
    where u.email = lower(coalesce(auth.jwt() ->> 'email', ''))
      and u.is_active = true
  );
$$;

grant execute on function public.is_scholarlens_user() to anon, authenticated;

drop policy if exists "Public read essay-agent papers" on public.essay_agent_papers;
create policy "Public read essay-agent papers"
  on public.essay_agent_papers for select
  using (true);

drop policy if exists "Public read essay-agent daily runs" on public.essay_agent_daily_runs;
create policy "Public read essay-agent daily runs"
  on public.essay_agent_daily_runs for select
  using (true);

drop policy if exists "Users read own ScholarLens membership" on public.scholarlens_users;
create policy "Users read own ScholarLens membership"
  on public.scholarlens_users for select
  using (email = lower(coalesce(auth.jwt() ->> 'email', '')));

drop policy if exists "Users read own paper states" on public.user_paper_states;
create policy "Users read own paper states"
  on public.user_paper_states for select
  using (auth.uid() = user_id and public.is_scholarlens_user());

drop policy if exists "Users insert own paper states" on public.user_paper_states;
create policy "Users insert own paper states"
  on public.user_paper_states for insert
  with check (auth.uid() = user_id and public.is_scholarlens_user());

drop policy if exists "Users update own paper states" on public.user_paper_states;
create policy "Users update own paper states"
  on public.user_paper_states for update
  using (auth.uid() = user_id and public.is_scholarlens_user())
  with check (auth.uid() = user_id and public.is_scholarlens_user());

create or replace function public.match_essay_agent_papers(
  query_embedding vector(384),
  match_count int default 20,
  min_similarity float default 0
)
returns table (
  id text,
  title text,
  abstract text,
  chinese_summary text,
  source text,
  link text,
  published timestamptz,
  domain_query text,
  domain_relevance_score int,
  similarity float
)
language sql stable
as $$
  select
    p.id,
    p.title,
    p.abstract,
    p.chinese_summary,
    p.source,
    p.link,
    p.published,
    p.domain_query,
    p.domain_relevance_score,
    1 - (p.embedding <=> query_embedding) as similarity
  from public.essay_agent_papers p
  where p.embedding is not null
    and (1 - (p.embedding <=> query_embedding)) >= min_similarity
  order by
    (1 - (p.embedding <=> query_embedding)) desc,
    p.domain_relevance_score desc,
    p.published desc
  limit greatest(match_count, 1);
$$;
