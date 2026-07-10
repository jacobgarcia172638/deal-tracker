-- ============================================================
-- Deal Tracker: paywall schema
-- ============================================================
-- Run this ONCE in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Contains no secrets -- safe to keep checked into the repo.
--
-- What this sets up:
--   profiles       - one row per signed-up visitor, records when their
--                    1-day free trial started
--   subscriptions  - one row per visitor, updated by the stripe-webhook
--                    Edge Function when they pay
--   deals          - the actual deal history (price drops, restocks,
--                    aggregator finds). Written by the GitHub Action
--                    using the service-role key, which bypasses RLS.
--   tracked_products - current price/stock snapshot for hand-picked
--                    products, same write path as deals.
--
-- Both deals and tracked_products only allow SELECT (read) via Row Level
-- Security, and only if the requesting visitor's trial is still active OR
-- they have an active subscription. This is the actual paywall enforcement
-- -- it happens in the database, not in the website's JavaScript, so it
-- can't be bypassed by viewing page source or disabling JS.
-- ============================================================

-- ------------------------------------------------------------
-- profiles
-- ------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  trial_started_at timestamptz not null default now(),
  is_comped boolean not null default false,  -- site owner/admin: never gated, never pays
  created_at timestamptz not null default now()
);

-- Safe to re-run on a table that already exists from before this column existed.
alter table public.profiles add column if not exists is_comped boolean not null default false;

alter table public.profiles enable row level security;

drop policy if exists "Users can read their own profile" on public.profiles;
create policy "Users can read their own profile"
  on public.profiles for select
  using (auth.uid() = id);

-- ------------------------------------------------------------
-- subscriptions
-- ------------------------------------------------------------
create table if not exists public.subscriptions (
  user_id uuid primary key references auth.users (id) on delete cascade,
  stripe_customer_id text,
  stripe_subscription_id text,
  status text not null default 'none', -- 'active' | 'past_due' | 'canceled' | 'none'
  current_period_end timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.subscriptions enable row level security;

drop policy if exists "Users can read their own subscription" on public.subscriptions;
create policy "Users can read their own subscription"
  on public.subscriptions for select
  using (auth.uid() = user_id);

-- ------------------------------------------------------------
-- deals (the gated content)
-- ------------------------------------------------------------
create table if not exists public.deals (
  id bigint generated always as identity primary key,
  type text not null,              -- 'price_drop' | 'restock' | 'aggregator_deal'
  product text not null,
  source text,
  store text,                      -- retailer name, e.g. "Amazon", "Lowes", "Best Buy"
  link text,
  affiliate_link text,
  old_price numeric,
  new_price numeric,
  snippet text,
  created_at timestamptz not null default now()
);

-- Safe to re-run on a table that already exists from before this column existed.
alter table public.deals add column if not exists store text;

-- Prevents the aggregator from re-adding the same RSS item every run.
-- Multiple NULLs are allowed by Postgres unique constraints, so hand-picked
-- price_drop/restock rows (which don't set "link") are unaffected.
create unique index if not exists deals_link_unique on public.deals (link);

alter table public.deals enable row level security;

drop policy if exists "Entitled users can read deals" on public.deals;
create policy "Entitled users can read deals"
  on public.deals for select
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.is_comped or p.trial_started_at > now() - interval '1 day')
    )
    or exists (
      select 1 from public.subscriptions s
      where s.user_id = auth.uid()
        and s.status = 'active'
    )
  );

-- ------------------------------------------------------------
-- tracked_products (the gated content)
-- ------------------------------------------------------------
create table if not exists public.tracked_products (
  name text primary key,
  url text,
  price numeric,
  in_stock boolean,
  last_checked timestamptz
);

alter table public.tracked_products enable row level security;

drop policy if exists "Entitled users can read tracked products" on public.tracked_products;
create policy "Entitled users can read tracked products"
  on public.tracked_products for select
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.is_comped or p.trial_started_at > now() - interval '1 day')
    )
    or exists (
      select 1 from public.subscriptions s
      where s.user_id = auth.uid()
        and s.status = 'active'
    )
  );

-- ------------------------------------------------------------
-- Auto-create a profile + subscription row (and start the trial clock)
-- the moment someone signs up via the magic-link email form.
-- ------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, trial_started_at)
  values (new.id, new.email, now())
  on conflict (id) do nothing;

  insert into public.subscriptions (user_id, status)
  values (new.id, 'none')
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
