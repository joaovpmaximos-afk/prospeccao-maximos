-- ============================================================
--  MAXIMOS · Listas para os seletores de CNAE e Município
--  Rode no Supabase: SQL Editor > New query > Run
--  Roda como administrador (sem limite de tempo). Leva alguns segundos.
--  OBS: são "fotos" da base atual. Se recarregar empresas, rode de novo.
-- ============================================================

-- CNAEs presentes na base (código, descrição, quantidade de empresas)
drop table if exists public.cnaes;
create table public.cnaes as
  select cnae_principal as codigo, min(cnae_desc) as descricao, count(*)::int as qtde
  from public.empresas
  where coalesce(cnae_principal,'') <> ''
  group by cnae_principal;
alter table public.cnaes add primary key (codigo);

-- Municípios por UF (com quantidade)
drop table if exists public.municipios;
create table public.municipios as
  select uf, municipio, count(*)::int as qtde
  from public.empresas
  where coalesce(municipio,'') <> ''
  group by uf, municipio;
create index on public.municipios (uf);

-- Leitura pública (o app lê essas listas com a chave anon/publishable)
alter table public.cnaes enable row level security;
alter table public.municipios enable row level security;
drop policy if exists "r_cnaes" on public.cnaes;
drop policy if exists "r_municipios" on public.municipios;
create policy "r_cnaes" on public.cnaes for select to anon using (true);
create policy "r_municipios" on public.municipios for select to anon using (true);
