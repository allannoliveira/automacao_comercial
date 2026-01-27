import re
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
import mysql.connector
import requests
from dateutil import parser

# =====================================================
# CONFIGURAÇÕES
# =====================================================
LOGIN_URL = "https://conlicitacao.com.br/"
CALENDARIO_URL = "https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins"
BIDDINGS_API = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins/{}/biddings.json"
BOLETIM_DETAIL_URL = "https://consultaonline.conlicitacao.com.br/boletim_web/public/biddings/{}"

CHECKPOINT_FILE = "ultimo_boletim.json"
LOG_FILE = "coleta_log.json"

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "licitacoes",
    "port": 3306,
    "autocommit": False
}

PADROES_REGEX = [
    r"\bCONSULTAS?\b",
    r"\bENFERMAG[EMN]S?\b",
    r"\bENFERMEIROS?\b",
    r"\bEQUIPES?\s+MEDICAS?\b",
    r"\bESPECIALIDADES?\s+MEDICAS?\b",
    r"\bMEDICOS?\b",
    r"\bSERVIÇOS?\s+MEDIC[OA]S?\b",
    r"\bTELE\s*ATENDIMENTOS?\b",
    r"\bTELEATENDIMENTOS?\b",
    r"\bTELECONSULTAS?\b",
]

log_entries = []

# =====================================================
# LOG
# =====================================================
def log_message(level, message, extra=None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level.upper(),
        "message": message
    }
    if extra:
        entry.update(extra)
    log_entries.append(entry)
    print(f"[{level.upper()}] {message}")

# =====================================================
# UTILIDADES
# =====================================================
def normalizar_texto(valor):
    return str(valor).strip().upper() if valor else None

def carregar_ultimo_boletim():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("ultimo_id", 0))
        except Exception:
            return 0
    return 0

def salvar_ultimo_boletim(boletim_id):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"ultimo_id": boletim_id, "data_processamento": datetime.now().isoformat()},
            f, indent=2, ensure_ascii=False
        )

def bate_regex(texto):
    texto = normalizar_texto(texto or "")
    return any(re.search(p, texto) for p in PADROES_REGEX)

# =====================================================
# MYSQL
# =====================================================
def conectar_mysql():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    log_message("INFO", "Conexão MySQL estabelecida")
    return conn

def inserir_boletins_mysql(conn, dados):
    sql = """
        INSERT IGNORE INTO boletins (
            boletim_id,
            bidding_id,
            orgao_cidade,
            orgao_estado,
            edital,
            edital_site,
            itens,
            descricao,
            valor_estimado,
            datahora_abertura,
            datahora_prazo,
            data_coleta
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    def parse_data(valor):
        if not valor:
            return None
        try:
            dt = parser.isoparse(valor)
            return dt.replace(tzinfo=None)
        except Exception:
            return None

    cur = conn.cursor()

    for d in dados:
        cur.execute(sql, (
            d.get("boletim_id"),
            d.get("bidding_id"),
            normalizar_texto(d.get("orgao_cidade")),
            normalizar_texto(d.get("orgao_estado")),
            normalizar_texto(d.get("edital")),
            d.get("edital_site"),
            d.get("itens"),
            d.get("descricao"),
            d.get("valor_estimado"),          # ✅ DIRETO (float)
            parse_data(d.get("datahora_abertura")),
            parse_data(d.get("datahora_prazo")),
            datetime.now()
        ))

    conn.commit()
    cur.close()

# =====================================================
# LOGIN
# =====================================================
def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

def criar_browser_autenticado():
    creds = carregar_credenciais()
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    log_message("INFO", "Iniciando login...")
    page.goto(LOGIN_URL, wait_until="networkidle")
    page.get_by_role("link", name="Acessar Conta").click()
    page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
    page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
    page.get_by_role("button", name="Acessar").click()
    page.wait_for_timeout(8000)
    log_message("INFO", "Login concluído")

    return p, browser, context

# =====================================================
# EXTRAIR BOLETINS (VERSÃO QUE FUNCIONA)
# =====================================================
def extrair_boletins(context):
    log_message("INFO", "Extraindo boletins via Playwright (FullCalendar)")

    page = context.new_page()
    boletins = set()

    try:
        page.goto(
            CALENDARIO_URL,
            wait_until="networkidle",
            timeout=30000
        )

        # 🔑 espera o calendário existir
        page.wait_for_selector(".fc-event", timeout=30000)

        # dá tempo do JS preencher os eventos
        page.wait_for_timeout(3000)

        eventos = page.locator(".fc-event").all()

        for ev in eventos:
            try:
                # pega qualquer atributo ou texto do evento
                html = ev.inner_html()

                # boletins SEMPRE têm IDs longos (8+ dígitos)
                encontrados = re.findall(r"\b1\d{7,}\b", html)
                for b in encontrados:
                    boletins.add(int(b))

            except Exception:
                continue

        log_message("INFO", f"{len(boletins)} boletins válidos encontrados")
        return sorted(boletins)

    except Exception as e:
        log_message("ERROR", f"Erro ao extrair boletins: {e}")
        return []

    finally:
        page.close()

# =====================================================
# EXTRAÇÃO DETALHES (HTML)
# =====================================================
def extrair_detalhes_bidding(context, bidding_id):
    situacao = "NORMAL"
    data_abertura = None
    prazo = None
    valor_estimado = None

    page = context.new_page()
    try:
        page.goto(
            BOLETIM_DETAIL_URL.format(bidding_id),
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_selector("div.bidding-info-title", timeout=20000)

        textos = []
        textos += page.locator("div.bidding-info-title").all_text_contents()
        textos += page.locator("div.text-secondary").all_text_contents()
        textos += page.locator("span.estimated").all_text_contents()

        texto = " ".join(textos)

        if re.search(r"\bURGENTE\b", texto, re.I):
            situacao = "URGENTE"

        m = re.search(r"Abertura\s*:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", texto)
        if m:
            data_abertura = m.group(1)

        m = re.search(r"Prazo\s*:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", texto)
        if m:
            prazo = m.group(1)

        m = re.search(r"R\$\s*([\d\.,]+)", texto)
        if m:
            valor_estimado = m.group(1)

    except Exception as e:
        log_message("ERROR", f"Erro ao extrair bidding {bidding_id}: {e}")

    finally:
        page.close()

    return situacao, prazo, data_abertura, valor_estimado


def ativar_boletim_html(context, boletim_id):
    """
    Abre a página HTML do boletim apenas para ativar a sessão no backend.
    NÃO extrai dados.
    """
    page = context.new_page()
    try:
        url = f"https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins/{boletim_id}"
        log_message("INFO", f"Ativando boletim HTML {boletim_id}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
    except Exception as e:
        log_message("WARNING", f"Falha ao ativar boletim {boletim_id}: {e}")
    finally:
        page.close()

# =====================================================
# COLETA
# =====================================================
def coletar_licitacoes(context, boletins):
    resultados = []
    session = requests.Session()

    # Copia cookies do Playwright
    for c in context.cookies():
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

    for boletim_id in boletins:
        # 🔑 ativa o boletim no backend
        ativar_boletim_html(context, boletim_id)

        url = BIDDINGS_API.format(boletim_id)
        resp = session.get(url, timeout=30)

        if resp.status_code != 200:
            log_message("WARNING", f"API não respondeu para boletim {boletim_id}")
            continue

        dados = resp.json()
        biddings = dados.get("biddings", [])

        log_message("INFO", f"Boletim {boletim_id}: {len(biddings)} biddings")

        for item in biddings:
            resultados.append({
                "boletim_id": boletim_id,
                "bidding_id": item.get("bidding_id"),
                "orgao_cidade": item.get("orgao_cidade"),
                "orgao_estado": item.get("orgao_estado"),
                "edital": item.get("edital"),
                "edital_site": item.get("edital_site"),
                "itens": item.get("itens"),
                "descricao": item.get("descricao"),
                "datahora_abertura": item.get("datahora_abertura"),
                "datahora_prazo": item.get("datahora_prazo"),
                "valor_estimado": item.get("valor_estimado")
            })

            log_message(
                "INFO",
                f"Bidding {item.get('bidding_id')} coletado",
                {
                    "cidade": item.get("orgao_cidade"),
                    "estado": item.get("orgao_estado"),
                    "abertura": item.get("datahora_abertura"),
                    "prazo": item.get("datahora_prazo")
                }
            )

    return resultados


# =====================================================
# MAIN
# =====================================================
def main():
    log_message("INFO", "=== INICIANDO COLETA ===")

    ultimo = carregar_ultimo_boletim()
    log_message("INFO", f"Último boletim processado: {ultimo}")

    p, browser, context = criar_browser_autenticado()

    try:
        boletins = extrair_boletins(context)
        novos = [b for b in boletins if b > ultimo]

        if not novos:
            log_message("INFO", "Nenhum boletim novo encontrado")
            return

        dados = coletar_licitacoes(context, novos)

        if dados:
            conn = conectar_mysql()
            inserir_boletins_mysql(conn, dados)
            conn.close()

        salvar_ultimo_boletim(max(novos))

    finally:
        browser.close()
        p.stop()

        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)

        log_message("INFO", "=== COLETA FINALIZADA ===")

if __name__ == "__main__":
    main()
