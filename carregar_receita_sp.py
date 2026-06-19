# =====================================================================
#  MAXIMOS · Carregador da base de CNPJ -> Supabase  (v4 — SP completo)
#  Cole TODO este conteúdo em UMA célula do Google Colab e clique em Run.
#  Memória-segura: grava os estabelecimentos em disco (não estoura a RAM).
#  Mirror Cloudflare (não bloqueia o Colab).
#
#  Antes: tabela criada (supabase-empresas.sql) e projeto no Supabase ATIVO (Pro).
#  Precisa (Supabase > Settings > API): SUPABASE_URL e SUPABASE_SERVICE_KEY (secret).
#  >>> NUNCA cole a chave secret no chat. Só aqui no Colab. <<<
# =====================================================================
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "supabase", "requests", "tqdm"])

import os, io, csv, re, json, zipfile, requests
from supabase import create_client

def _secret(n):
    try:
        from google.colab import userdata
        v = userdata.get(n)
        if v: return v
    except Exception:
        pass
    if os.environ.get(n): return os.environ[n]
    import getpass
    return getpass.getpass(n + ": ")

SUPABASE_URL         = _secret("SUPABASE_URL")
SUPABASE_SERVICE_KEY = _secret("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ===== CONFIG =====
UFS          = {"SP"}       # estados
SO_ATIVAS    = True         # só ATIVAS
CNAES_FILTRO = set()        # vazio = todos os CNAEs
LIMITE       = None         # None = SP INTEIRO (Pro). Ou um número p/ limitar.
LOTE         = 5000
PASTA_DATA   = ""           # "" = mais recente
# ==================

csv.field_size_limit(10**7)
SIT   = {"01":"Nula","02":"Ativa","03":"Suspensa","04":"Inapta","08":"Baixada"}
PORTE = {"01":"ME","03":"EPP","05":"Demais"}
UA    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
BASE  = "https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/"

if not PASTA_DATA:
    print("Procurando a base mais recente...")
    idx = requests.get(BASE, headers=UA, timeout=120).text
    datas = sorted(set(re.findall(r"(\d{4}-\d{2}-\d{2})/", idx)))
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

print("Referências (municípios e CNAEs)...")
MUN, CNAE = {}, {}
for r in linhas_zip(URL_MUN):
    if len(r) >= 2: MUN[r[0].strip()] = r[1].strip()
for r in linhas_zip(URL_CNAE):
    if len(r) >= 2: CNAE[r[0].strip()] = r[1].strip()
print(f"  municípios: {len(MUN)}  cnaes: {len(CNAE)}")

# PASS 1 — Estabelecimentos -> grava em disco (poupa RAM) e coleta os CNPJ básicos
print(f"Estabelecimentos (gravando em disco, filtrando {UFS})...")
precisa = set(); n_estab = 0; stop = False
fout = open("/content/estab.jsonl", "w", encoding="utf-8")
for url in URLS_ESTAB:
    if stop: break
    for r in linhas_zip(url):
        if len(r) < 28: continue
        if r[19].strip() not in UFS: continue
        if SO_ATIVAS and r[5].strip() != "02": continue
        if CNAES_FILTRO and r[11].strip() not in CNAES_FILTRO: continue
        bas = r[0].strip(); ddd = r[21].strip(); tel = r[22].strip()
        rec = {"bas": bas, "cnpj": bas + r[1].strip() + r[2].strip(), "fant": r[4].strip(),
               "sit": SIT.get(r[5].strip(), r[5].strip()), "tipo": "Matriz" if r[3].strip() == "1" else "Filial",
               "cnae": r[11].strip(), "cnae_desc": CNAE.get(r[11].strip(), ""), "mun": MUN.get(r[20].strip(), ""),
               "uf": r[19].strip(), "abertura": r[10].strip(),
               "tel": (f"({ddd}) {tel}" if ddd and tel else (tel or "")), "email": r[27].strip().lower()}
        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        precisa.add(bas); n_estab += 1
        if n_estab % 200000 == 0: print("  ...", n_estab, "estabelecimentos")
        if LIMITE and n_estab >= LIMITE: stop = True; break
fout.close()
print(f"  total estabelecimentos: {n_estab}  (empresas distintas: {len(precisa)})")
if not n_estab: raise RuntimeError("Nada coletado.")

# PASS 2 — Empresas (razão, capital, porte) — guarda como tupla p/ poupar memória
print("Empresas...")
EMP = {}
for url in URLS_EMP:
    for r in linhas_zip(url):
        if len(r) < 6: continue
        bas = r[0].strip()
        if bas in precisa:
            cap = r[4].strip().replace(".", "").replace(",", ".")
            try: cap = float(cap)
            except Exception: cap = None
            EMP[bas] = (r[1].strip(), cap, PORTE.get(r[5].strip(), "Demais"))

# PASS 3 — Simples / MEI
print("Simples / MEI...")
SIMP = {}
for url in URLS_SIMP:
    for r in linhas_zip(url):
        if len(r) < 5: continue
        bas = r[0].strip()
        if bas in precisa: SIMP[bas] = (r[1].strip() == "S", r[4].strip() == "S")

def _data(s):
    if not s or len(s) != 8 or s == "00000000": return None
    if s[4:6] == "00" or s[6:] == "00": return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"

# PASS 4 — lê o disco, junta e envia em lotes (streaming, baixa RAM)
print(f"Enviando ao Supabase (lotes de {LOTE})...")
lote = []; enviados = 0
def flush():
    global enviados
    if lote:
        sb.table("empresas").upsert(lote).execute(); enviados += len(lote); lote.clear()
        if enviados % 50000 == 0: print("  enviadas:", enviados)
with open("/content/estab.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        e = json.loads(line); bas = e["bas"]
        emp = EMP.get(bas); sm = SIMP.get(bas); mei = sm[1] if sm else False
        lote.append({"cnpj": e["cnpj"], "cnpj_basico": bas, "razao_social": emp[0] if emp else "",
            "nome_fantasia": e["fant"], "uf": e["uf"], "municipio": e["mun"], "cnae_principal": e["cnae"],
            "cnae_desc": e["cnae_desc"], "situacao": e["sit"], "tipo": e["tipo"],
            "porte": ("MEI" if mei else (emp[2] if emp else "Demais")), "simples": (sm[0] if sm else False), "mei": mei,
            "capital_social": (emp[1] if emp else None), "data_abertura": _data(e["abertura"]),
            "telefone": e["tel"], "email": e["email"]})
        if len(lote) >= LOTE: flush()
flush()
print(f"\nPRONTO! Empresas enviadas: {enviados}")
