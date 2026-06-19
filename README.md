# MAXIMOS · Prospecção de Leads

Sistema de prospecção B2B que filtra a **base pública de CNPJ da Receita Federal**
(cidade, CNAE, situação, porte, capital, etc.) e gera listas de leads em massa —
com exportação para **Excel, CSV e Dashboard HTML**, login por usuário e identidade
visual da **MAXIMOS Soluções Empresariais**.

🔗 **No ar:** https://joaovpmaximos-afk.github.io/prospeccao-maximos/

---

## Como funciona (arquitetura)

```
  Receita Federal (Dados Abertos CNPJ)
            │  (carregamento único, via Google Colab)
            ▼
   Supabase  ──  Postgres (tabela "empresas") + Auth (login)
            ▲
            │  consultas REST (filtros, contagem, paginação)
            ▼
   index.html  ──  app estático (front-end) publicado no GitHub Pages
```

- **Front-end:** um único arquivo HTML (sem servidor) — abre no navegador / GitHub Pages.
- **Dados + login:** Supabase (banco Postgres + autenticação).
- **Origem dos dados:** Dados Abertos do CNPJ (Receita Federal), via espelho Cloudflare.

---

## Arquivos do sistema

| Arquivo | O que é |
|---|---|
| `index.html` | O **app** (front-end). Mesmo conteúdo de `prospeccao-maximos.html`. |
| `prospeccao-maximos.html` | Cópia do app (nome amigável para edição local). |
| `logo-maximos.jpg` | Logo oficial da MAXIMOS usada no app e nos relatórios. |
| `supabase-empresas.sql` | Cria a tabela `empresas` (+ índices e leitura pública) no Supabase. |
| `supabase-listas.sql` | Cria as listas `cnaes` e `municipios` (seletores de CNAE e cidade). |
| `carregar_receita_sp.py` | **Carregador** — roda no Google Colab, baixa os dados da Receita e envia ao Supabase. |

---

## Como montar do zero (resumo)

1. **Supabase:** crie um projeto (plano Free para testes). Rode `supabase-empresas.sql` no SQL Editor.
2. **Carregar dados:** no Google Colab, cole/rode `carregar_receita_sp.py` (informe a URL do projeto e a chave *secret*). Carrega SP (ativas).
   - Plano Free: `LIMITE = 500_000` (amostra). Plano Pro: `LIMITE = None` (SP inteiro).
3. **Listas:** rode `supabase-listas.sql` para habilitar os seletores de CNAE/cidade.
4. **Login:** em *Authentication → Users*, crie os usuários (com *Auto Confirm*).
5. **Publicar:** o `index.html` é estático — publique no GitHub Pages (Settings → Pages → main /root) ou em qualquer hospedagem estática.

> No `index.html` ficam a **URL do projeto** e a **chave publishable** do Supabase
> (são públicas e protegidas por RLS). A chave **secret** NUNCA vai no código — só no Colab.

---

## Recursos do app

- Filtros: busca, CNPJ, localização, CNAE, situação, tipo, Simples/MEI, porte, capital, data de abertura, "remover contadores".
- Resultado: contagem (exata/estimada), visão em **cards** ou **tabela**, paginação.
- Clique no card → **detalhes completos** da empresa.
- **Buscas salvas** com pastas.
- Exportar **Excel · CSV · Dashboard HTML** (com KPIs e gráficos, na marca MAXIMOS).
- **Login** por e-mail/senha (Supabase Auth).

---

© MAXIMOS Soluções Empresariais. Dados públicos da Receita Federal.
