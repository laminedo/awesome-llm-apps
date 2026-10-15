-- Debt Payoff Coach: Supabase schema (run once in the SQL editor).

-- One row per user: debts, budgets, payments, settings (everything except purchases).
create table public.user_state (
  user_id uuid primary key references auth.users(id) on delete cascade default auth.uid(),
  state jsonb not null,
  updated_at timestamptz not null default now(),
  constraint user_state_size check (pg_column_size(state) < 2000000)
);

-- Purchases grouped by month so one save never rewrites the whole history.
create table public.purchase_months (
  user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  month text not null check (month ~ '^\d{4}-(0[1-9]|1[0-2])$'),
  items jsonb not null check (jsonb_typeof(items) = 'array'),
  updated_at timestamptz not null default now(),
  primary key (user_id, month),
  constraint purchase_months_size check (pg_column_size(items) < 2000000)
);

alter table public.user_state enable row level security;
alter table public.purchase_months enable row level security;

-- Each signed-in person can only see and change their own rows.
create policy "own state select" on public.user_state for select to authenticated using ((select auth.uid()) = user_id);
create policy "own state insert" on public.user_state for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own state update" on public.user_state for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own state delete" on public.user_state for delete to authenticated using ((select auth.uid()) = user_id);

create policy "own months select" on public.purchase_months for select to authenticated using ((select auth.uid()) = user_id);
create policy "own months insert" on public.purchase_months for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own months update" on public.purchase_months for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own months delete" on public.purchase_months for delete to authenticated using ((select auth.uid()) = user_id);

-- Signed-out visitors get nothing.
revoke all on public.user_state, public.purchase_months from anon;
grant select, insert, update, delete on public.user_state, public.purchase_months to authenticated;
