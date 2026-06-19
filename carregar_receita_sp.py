# =====================================================================
#  MAXIMOS · Carregador da base de CNPJ -> Supabase  (v3)
#  Cole TODO este conteúdo em UMA célula do Google Colab e clique em Run.
#  Usa o espelho (mirror) da Casa dos Dados via Cloudflare (não bloqueia o Colab).
#
#  Antes: rode o supabase-empresas.sql no seu Supabase (cria a tabela).
#  Você vai precisar (Supabase > Settings > API):
#    - SUPABASE_URL          (ex: https://xxxx.supabase.co)
#    - SUPABASE_SERVICE_KEY  (a chave secret/service_role — SECRETA)
#  >>> NUNCA cole a chave secret no chat nem no HTML. Só aqui no Colab. <<<
# =====================================================================
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "supabase", "requests", "tqdm"])

import os, io, csv, re, zipfile, requests
from tqdm import tqdm
from supabase import create_client

def _secret(nome):
    try:
        from google.colab import userdata
        v = userdata.get(nome)
        if v: return v
    except Exception:
        pass
    if os.environ.get(nome): return os.environ[nome]
    import getpass
    return getpass.getpass(nome + ": ")

SUPABASE_URL         = _secret("SUPABASE_URL")
SUPABASE_SERVICE_KEY = _secret("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ===== CONFIG (mexa só aqui) =====
UFS          = {"SP"}       # estados a carregar
SO_ATIVAS    = True         # True = só empresas ATIVAS
CNAES_FILTRO = set()        # vazio = todos os CNAEs
LIMITE       = 500_000      # teste grátis. No Pro: troque por None p/ SP inteiro
LOTE         = 4000
PASTA_DATA   = ""           # "" = pega a mais recente. Ou fixe, ex: "2026-05-10"
# =================================

csv.field_size_limit(10**7)
SIT   = {"01":"Nula","02":"Ativa","03":"Suspensa","04":"Inapta","08":"Baixada"}
PORTE = {"01":"ME","03":"EPP","05":"Demais"}
UA    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
BASE  = "https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/"

if not PASTA_DATA:
    print("Procurando a base mais recente...")
    idx = requests.get(BASE, headers=UA, timeout=120).text
    datas = sorted(set(re.findall(r"(\d{4}-\d{2}-\d{2})/", idx)))
    if not datas:
        raise RuntimeError("Não consegui listar o espelho. Defina PASTA_DATA, ex: '2026-05-10'.")
    PASTA_DATA = datas[-1]
PASTA = BASE + PASTA_DATA + "/"
print("Usando base de:", PASTA_DATA)

URLS_ESTAB = [PASTA + f"Estabelecimentos{i}.zip" for i in range(10)]
URLS_EMP   = [PASTA + f"Empresas{i}.zip" for i in range(10)]
URLS_SIMP  = [PASTA + "Simples.zip"]
URL_MUN    = PASTA + "Municipios.zip"
URL_CNAE   = PASTA + "Cnaes.zip"

def linhas_zip(url):
    tmp = "/content/_tmp.zip"
    r = requests.get(url, headers=UA, stream=True, timeout=1800, allow_redirects=True)
    if r.status_code != 200:
        r.close(); print("  (pulando:", url.split("/")[-1], ")"); return
    with open(tmp, "wb") as f:
        for ch in r.iter_content(1 << 20):
            f.write(ch)
    r.close()
    with zipfile.ZipFile(tmp) as z:
        for nome in z.namelist():
            with z.open(nome) as fh:
                for row in csv.reader(io.TextIOWrapper(fh, encoding="latin-1", newline=""), delimiter=";", quotechar='"'):
                    yield row
    os.remove(tmp)

print("Carregando referências (municípios e CNAEs)...")
MUN, CNAE = {}, {}
for r in linhas_zip(URL_MUN):
    if len(r) >= 2: MUN[r[0].strip()] = r[1].strip()
for r in linhas_zip(URL_CNAE):
    if len(r) >= 2: CNAE[r[0].strip()] = r[1].strip()
print(f"  municípios: {len(MUN)}  cnaes: {len(CNAE)}")

print(f"Lendo Estabelecimentos e filtrando {UFS}...")
estabs, precisa = [], set()
class _Stop(Exception): pass
try:
    for url in URLS_ESTAB:
        for r in linhas_zip(url):
            if len(r) < 28: continue
            if r[19].strip() not in UFS: continue
            if SO_ATIVAS and r[5].strip() != "02": continue
            if CNAES_FILTRO and r[11].strip() not in CNAES_FILTRO: continue
            bas = r[0].strip(); ddd = r[21].strip(); tel = r[22].strip()
            estabs.append({"bas": bas, "cnpj": bas + r[1].strip() + r[2].strip(), "fant": r[4].strip(),
                "sit": SIT.get(r[5].strip(), r[5].strip()), "tipo": "Matriz" if r[3].strip() == "1" else "Filial",
                "cnae": r[11].strip(), "cnae_desc": CNAE.get(r[11].strip(), ""), "mun": MUN.get(r[20].strip(), ""),
                "uf": r[19].strip(), "abertura": r[10].strip(),
                "tel": (f"({ddd}) {tel}" if ddd and tel else (tel or "")), "email": r[27].strip().lower()})
            precisa.add(bas)
            if LIMITE and len(estabs) >= LIMITE: raise _Stop()
except _Stop:
    pass
print(f"  coletados: {len(estabs)}")
if not estabs:
    raise RuntimeError("Nada coletado — verifique se o download funcionou.")

print("Lendo Empresas (razão social / capital / porte)...")
EMP = {}
for url in URLS_EMP:
    for r in linhas_zip(url):
        if len(r) < 6: continue
        bas = r[0].strip()
        if bas in precisa:
            cap = r[4].strip().replace(".", "").replace(",", ".")
            try: cap = float(cap)
            except Exception: cap = None
            EMP[bas] = {"razao": r[1].strip(), "capital": cap, "porte": PORTE.get(r[5].strip(), "Demais")}

print("Lendo Simples / MEI...")
SIMP = {}
for url in URLS_SIMP:
    for r in linhas_zip(url):
        if len(r) < 5: continue
        bas = r[0].strip()
        if bas in precisa: SIMP[bas] = {"simples": r[1].strip() == "S", "mei": r[4].strip() == "S"}

def _data(s):
    if not s or len(s) != 8 or s == "00000000": return None
    if s[4:6] == "00" or s[6:] == "00": return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"

print(f"Enviando ao Supabase (lotes de {LOTE})...")
lote, enviados = [], 0
def _flush():
    global enviados
    if lote:
        sb.table("empresas").upsert(lote).execute(); enviados += len(lote); lote.clear()
for e in tqdm(estabs):
    emp = EMP.get(e["bas"], {}); sm = SIMP.get(e["bas"], {}); mei = sm.get("mei", False)
    lote.append({"cnpj": e["cnpj"], "cnpj_basico": e["bas"], "razao_social": emp.get("razao", ""),
        "nome_fantasia": e["fant"], "uf": e["uf"], "municipio": e["mun"], "cnae_principal": e["cnae"],
        "cnae_desc": e["cnae_desc"], "situacao": e["sit"], "tipo": e["tipo"],
        "porte": ("MEI" if mei else emp.get("porte", "Demais")), "simples": sm.get("simples", False), "mei": mei,
        "capital_social": emp.get("capital"), "data_abertura": _data(e["abertura"]),
        "telefone": e["tel"], "email": e["email"]})
    if len(lote) >= LOTE: _flush()
_flush()
print(f"\nPRONTO! Empresas enviadas: {enviados}")
