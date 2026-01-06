import re
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import mysql.connector
from mysql.connector import Error
import requests

# =====================================================
# CONFIGURAÇÕES
# =====================================================
LOGIN_URL = "https://conlicitacao.com.br/"
CALENDARIO_URL = "https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins"
BIDDINGS_API = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins/{}/biddings.json"
BOLETIM_DETAIL_URL = "https://consultaonline.conlicitacao.com.br/boletim_web/public/biddings/{}"

CHECKPOINT_FILE = "ultimo_boletim.json"
LOG_FILE = "coleta_log.json"

# =====================================================
# CONFIGURAÇÃO MYSQL
# =====================================================
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "licitacoes",
    "port": 3306,
    "autocommit": False
}

# =====================================================
# LOG
# =====================================================
log_entries = []

def log_message(level, message, extra=None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level.upper(),
        "message": message
    }
    if extra:
        entry.update(extra)
    log_entries.append(entry)

# =====================================================
# NORMALIZAÇÃO DE TEXTO (UPPER)
# =====================================================
def normalizar_texto(valor):
    if valor is None:
        return None
    return str(valor).strip().upper()

# =====================================================
# PALAVRAS-CHAVE (REGEX)
# =====================================================
PADROES_REGEX = [
    r"\bCONSULTAS?\b",
    r"\BENFERMAG[EMN]S?\b",
    r"\BENFERMEIROS?\b",
    r"\BEQUIPES?\s+MEDICAS?\b",
    r"\BESPECIALIDADES?\s+MEDICAS?\b",
    r"\BMEDICOS?\b",
    r"\BSERVIÇOS?\s+MEDIC[OA]S?\b",
    r"\BTELE\s*ATENDIMENTOS?\b",
    r"\BTELEATENDIMENTOS?\b",
]

# =====================================================
# CHECKPOINT
# =====================================================
def carregar_ultimo_boletim():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("ultimo_id", 0)
    return 0

def salvar_ultimo_boletim(boletim_id):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"ultimo_id": boletim_id, "data_processamento": datetime.now().isoformat()},
            f,
            indent=2,
            ensure_ascii=False
        )

# =====================================================
# MYSQL
# =====================================================
def conectar_mysql():
    try:
        return mysql.connector.connect(**MYSQL_CONFIG)
    except Error as e:
        log_message("CRITICAL", f"Erro ao conectar no MySQL: {e}")
        raise

def inserir_boletins_mysql(conn, dados):
    sql = """
        INSERT IGNORE INTO boletins (
            boletim_id, bidding_id, edital,
            data_abertura, prazo, data_coleta,
            valor_estimado, cidade, estado,
            situacao, descricao
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    valores = []

    def parse_data(valor):
        try:
            return datetime.strptime(valor, "%d/%m/%Y %H:%M")
        except:
            return None

    for d in dados:
        data_abertura = parse_data(d.get("data_abertura", ""))
        prazo = parse_data(d.get("prazo", ""))

        valor = None
        if d.get("valor_estimado"):
            try:
                valor = float(
                    d["valor_estimado"]
                    .replace("R$", "")
                    .replace(".", "")
                    .replace(",", ".")
                    .strip()
                )
            except:
                pass

        valores.append((
            d["boletim_id"],
            normalizar_texto(d["bidding_id"]),
            normalizar_texto(d["edital"]),
            data_abertura,
            prazo,
            datetime.now(),
            valor,
            normalizar_texto(d["cidade"]),
            normalizar_texto(d["estado"]),
            normalizar_texto(d["situacao"]),
            normalizar_texto(d["descricao"])
        ))

    cursor = conn.cursor()
    cursor.executemany(sql, valores)
    conn.commit()

    log_message("INFO", f"{cursor.rowcount} registros inseridos no MySQL")

# =====================================================
# CREDENCIAIS
# =====================================================
def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

# =====================================================
# LOGIN
# =====================================================
def criar_browser_autenticado():
    creds = carregar_credenciais()
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL, wait_until="networkidle")
    page.get_by_role("link", name="Acessar Conta").click()
    page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
    page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
    page.get_by_role("button", name="Acessar").click()
    page.wait_for_timeout(8000)

    log_message("INFO", "Login concluído")
    return p, browser, context

# =====================================================
# EXTRAIR BOLETINS
# =====================================================
def extrair_boletins(context):
    page = context.new_page()
    page.goto(CALENDARIO_URL, wait_until="networkidle")
    page.wait_for_timeout(5000)
    html = page.content()
    page.close()

    soup = BeautifulSoup(html, "html.parser")
    boletins = set()

    for link in soup.find_all("a", href=True):
        match = re.search(r"\b\d{8,}\b", link["href"])
        if match:
            boletins.add(int(match.group()))

    return sorted(boletins)

def bate_regex(texto):
    texto = normalizar_texto(texto or "")
    return any(re.search(p, texto) for p in PADROES_REGEX)

# =====================================================
# DETALHE
# =====================================================
def extrair_situacao_e_prazo(context, bidding_id):
    situacao = "NORMAL"
    prazo = ""

    page = context.new_page()
    try:
        page.goto(BOLETIM_DETAIL_URL.format(bidding_id), wait_until="networkidle")
        html = page.content().upper()
        soup = BeautifulSoup(html, "html.parser")

        if "URGENTE" in html:
            situacao = "URGENTE"

        prazo_tag = soup.find(string=re.compile("PRAZO:", re.I))
        if prazo_tag:
            prazo = prazo_tag.parent.get_text(strip=True).replace("PRAZO:", "").strip()

    except Exception as e:
        log_message("ERROR", f"Erro detalhe {bidding_id}: {e}")

    finally:
        page.close()

    return situacao, prazo

# =====================================================
# COLETAR LICITAÇÕES
# =====================================================
def coletar_licitacoes(context, boletins):
    resultados = []
    session = requests.Session()

    for c in context.cookies():
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

    for boletim_id in boletins:
        resp = session.get(BIDDINGS_API.format(boletim_id), timeout=30)
        if resp.status_code != 200:
            continue

        for item in resp.json().get("biddings", []):
            texto = (item.get("objeto", "") + " " + item.get("itens", "")).replace("\n", " ")

            if not bate_regex(texto):
                continue

            situacao, prazo = extrair_situacao_e_prazo(context, item["bidding_id"])

            resultados.append({
                "boletim_id": boletim_id,
                "bidding_id": item["bidding_id"],
                "edital": item.get("edital", ""),
                "data_abertura": item.get("data_abertura", ""),
                "valor_estimado": item.get("valor_estimado", ""),
                "cidade": item.get("orgao_cidade", ""),
                "estado": item.get("orgao_estado", ""),
                "descricao": texto,
                "situacao": situacao,
                "prazo": prazo
            })

    return resultados

# =====================================================
# MAIN
# =====================================================
def main():
    ultimo_id = carregar_ultimo_boletim()
    playwright, browser, context = criar_browser_autenticado()

    try:
        boletins = extrair_boletins(context)
        boletins_novos = [b for b in boletins if b > ultimo_id]

        if not boletins_novos:
            log_message("INFO", "Nenhum boletim novo encontrado")
            return

        resultados = coletar_licitacoes(context, boletins_novos)

        if resultados:
            conn = conectar_mysql()
            inserir_boletins_mysql(conn, resultados)
            conn.close()

        salvar_ultimo_boletim(max(boletins_novos))

    finally:
        browser.close()
        playwright.stop()
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
