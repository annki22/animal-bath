-- Review in the Supabase SQL editor before running. This file is intentionally
-- not executed by the local test suite.

alter table public.scores enable row level security;
alter table public.saves enable row level security;
alter table public.events enable row level security;

-- events: anonymous clients may append telemetry, but cannot read or mutate it.
revoke all on table public.events from anon;
grant insert on table public.events to anon;

-- Remove any legacy permissive policy first; otherwise policies are OR-combined
-- and an old SELECT/UPDATE/DELETE policy could keep anonymous access open.
do $$
declare policy_name text;
begin
  for policy_name in
    select policyname from pg_policies
    where schemaname = 'public' and tablename = 'events'
  loop
    execute format('drop policy %I on public.events', policy_name);
  end loop;
end $$;

create policy "anon_insert_events"
  on public.events
  for insert
  to anon
  with check (true);

-- No anon policies are created for scores/saves here: enabling RLS therefore
-- denies anonymous access until the application adopts a real identity model.
-- Recommended follow-up:
--   1. Use Supabase Auth and bind rows to auth.uid(), not a client-supplied nickname.
--   2. Permit SELECT/UPDATE/DELETE only when user_id = auth.uid().
--   3. Restrict INSERT/UPDATE to an explicit column allow-list via RPCs or grants,
--      validate score/max_level ranges, and keep service-role writes server-side.
--   4. Expose public leaderboards through a security-definer RPC/view returning
--      only the fields required by the UI; do not expose saves.state publicly.
