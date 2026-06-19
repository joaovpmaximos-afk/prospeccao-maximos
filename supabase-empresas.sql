-- ============================================================
--  MAXIMOS · Prospecção de Leads — estrutura da base de CNPJ
--  Rode no Supabase: painel > SQL Editor > New query > Run
--  (cria a tabela "empresas", os índices de filtro e a leitura pública)
-- ============================================================

-- 1) Tabela principal (campos enxutos p/ caber no plano grátis).
--    Mapeada a partir dos Dados Abertos do CNPJ (Receita Federal).
create table if not exists public.empresas (
  cnpj            text primary key,          -- CNPJ completo, 14 dígitos (só números)
  cnpj_basico     text,                      -- 8 primeiros dígitos (raiz)
  razao_social    text,
  nome_fantasia   text,
  uf              text,
  municipio       text,
  cnae_principal  text,
  cnae_desc       text,
  situacao        text,                       -- 'Ativa','Baixada','Suspensa','Inapta','Nula'
  tipo            text,                       -- 'Matriz' ou 'Filial'
  porte           text,                       -- 'MEI','ME','EPP','Demais'
  simples         boolean default false,
  mei             boolean default false,
  capital_social  numeric,
  data_abertura   date,
  telefone        text,
  email           text
);

-- 2) Índices p/ os filtros do app ficarem rápidos.
create index if not exists idx_emp_uf          on public.empresas (uf);
create index if not exists idx_emp_municipio   on public.empresas (municipio);
create index if not exists idx_emp_cnae        on public.empresas (cnae_principal);
create index if not exists idx_emp_situacao    on public.empresas (situacao);
create index if not exists idx_emp_porte       on public.empresas (porte);
create index if not exists idx_emp_abertura    on public.empresas (data_abertura);
create extension if not exists pg_trgm;
create index if not exists idx_emp_razao_trgm  on public.empresas using gin (razao_social gin_trgm_ops);
create index if not exists idx_emp_fant_trgm   on public.empresas using gin (nome_fantasia gin_trgm_ops);

-- 3) Segurança: o app (file:// ou web) usa a chave ANON/publishable e só LÊ.
--    O carregamento (Colab) usa a chave SERVICE_ROLE/secret, que ignora estas regras.
alter table public.empresas enable row level security;
drop policy if exists "leitura publica empresas" on public.empresas;
create policy "leitura publica empresas" on public.empresas for select to anon using (true);
