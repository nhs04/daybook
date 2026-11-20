-- Daybook database: one table holds everything (tasks, applications, chapters, courses, emails, thesis details, vision board pins, saved jobs).
-- Every row belongs to one signed-in person, and row-level security makes sure nobody else can read or change it.

create table if not exists public.items (
  user_id    uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  col        text        not null check (col in ('tasks', 'areas', 'apps', 'chapters', 'emails', 'meta', 'pins', 'jobs')),
  id         text        not null,
  data       jsonb       not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, col, id)
);

alter table public.items enable row level security;

drop policy if exists "Read my own items" on public.items;
drop policy if exists "Add my own items" on public.items;
drop policy if exists "Change my own items" on public.items;
drop policy if exists "Delete my own items" on public.items;

create policy "Read my own items"   on public.items for select using (auth.uid() = user_id);
create policy "Add my own items"    on public.items for insert with check (auth.uid() = user_id);
create policy "Change my own items" on public.items for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Delete my own items" on public.items for delete using (auth.uid() = user_id);

-- Live updates between your phone and laptop.
do $$
begin
  alter publication supabase_realtime add table public.items;
exception when duplicate_object then null;
end $$;
