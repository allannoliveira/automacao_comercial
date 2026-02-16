import re
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
import gspread
from google.oauth2.service_account import Credentials
import requests
import pathlib
import zipfile

# =====================================================
# CONFIGURAÇÕES
# =====================================================
LOGIN_URL = "https://conlicitacao.com.br/"
CALENDARIO_URL = "https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins"
BIDDINGS_API = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins/{}/biddings.json"

CHECKPOINT_FILE = "logs/ultimo_boletim.json"
LOG_FILE = "logs/coleta_log.json"

SHEET_ID = "1yJmxxKcTjJFqlci3UEUa54BwhvCY_KaLaAxhEsgdvyo"
SHEET_NAME = "licitacao"

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
# CHECKPOINT
# =====================================================
def carregar_ultimo_boletim():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("ultimo_id", 0))
        except Exception:
            return 0
    return 0

def salvar_ultimo_boletim(boletim_id):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)

    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ultimo_id": boletim_id,
                "data_processamento": datetime.now().isoformat()
            },
            f,
            indent=2,
            ensure_ascii=False
        )

    log_message("INFO", f"Checkpoint atualizado para {boletim_id}")

# =====================================================
# GOOGLE SHEETS
# =====================================================
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(
        "credentials/google_service_account.json",
        scopes=scopes
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

    log_message("INFO", "Conectado ao Google Sheets")

    return sheet

def inserir_boletins_google_sheets(dados):
    sheet = conectar_google_sheets()

    valores_coluna = sheet.col_values(2)
    ids_existentes = set(valores_coluna[1:]) if len(valores_coluna) > 1 else set()

    linhas = []

    for d in dados:
        bidding_id = d.get("bidding_id")
        if not bidding_id:
            continue

        id_conlicitacao = str(bidding_id).strip()

        if id_conlicitacao in ids_existentes:
            log_message("INFO", f"Já existe na planilha: {id_conlicitacao}")
            continue

        linhas.append([
            d.get("boletim_id"),
            id_conlicitacao,
            d.get("orgao_cidade"),
            d.get("orgao_estado"),
            d.get("edital"),
            d.get("edital_site"),
            d.get("itens"),
            d.get("descricao"),
            d.get("valor_estimado"),
            d.get("datahora_abertura"),
            d.get("datahora_prazo"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "",
            "",
            ""
        ])

    if linhas:
        sheet.append_rows(linhas, value_input_option="USER_ENTERED")
        log_message("INFO", f"{len(linhas)} novos registros inseridos")

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
# EXTRAIR BOLETINS
# =====================================================
def extrair_boletins(context):
    page = context.new_page()
    boletins = set()

    try:
        page.goto(CALENDARIO_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_selector(".fc-event", timeout=30000)
        page.wait_for_timeout(3000)

        eventos = page.locator(".fc-event").all()

        for ev in eventos:
            html = ev.inner_html()
            encontrados = re.findall(r"\b1\d{7,}\b", html)
            for b in encontrados:
                boletins.add(int(b))

        log_message("INFO", f"{len(boletins)} boletins válidos encontrados")
        return sorted(boletins)

    except Exception as e:
        log_message("ERROR", f"Erro ao extrair boletins: {e}")
        return []

    finally:
        page.close()

# =====================================================
# DOWNLOAD EDITAL (USANDO JSON edicts)
# =====================================================
def baixar_edital_por_json(context, boletim_id, bidding_id, arquivo_json):

    url_relativa = arquivo_json.get("url")
    filename = arquivo_json.get("filename")

    if not url_relativa or not filename:
        return []

    url_completa = f"https://consultaonline.conlicitacao.com.br{url_relativa}"

    pasta_base = pathlib.Path("downloads") / str(boletim_id) / str(bidding_id)
    pasta_base.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    for c in context.cookies():
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

    try:
        response = session.get(url_completa, timeout=60)

        if response.status_code != 200:
            log_message("WARNING", f"Arquivo não disponível para {bidding_id}")
            return []

        caminho = pasta_base / filename

        with open(caminho, "wb") as f:
            f.write(response.content)

        log_message("INFO", f"Arquivo baixado: {caminho}")

        arquivos_extraidos = []

        if filename.lower().endswith(".zip"):
            with zipfile.ZipFile(caminho, 'r') as zip_ref:
                zip_ref.extractall(pasta_base)
                for nome in zip_ref.namelist():
                    arquivos_extraidos.append(str(pasta_base / nome))

            caminho.unlink()
            log_message("INFO", f"{len(arquivos_extraidos)} arquivos extraídos")
            return arquivos_extraidos

        return [str(caminho)]

    except Exception as e:
        log_message("ERROR", f"Erro ao baixar arquivo {bidding_id}: {e}")
        return []

# =====================================================
# COLETAR LICITAÇÕES
# =====================================================
def coletar_licitacoes(context, boletins):
    resultados = []
    session = requests.Session()

    for c in context.cookies():
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

    for boletim_id in boletins:

        url = BIDDINGS_API.format(boletim_id)

        try:
            resp = session.get(url, timeout=30)
            dados_json = resp.json()
        except Exception:
            continue

        biddings = dados_json.get("biddings", [])

        for item in biddings:

            bidding_id = item.get("bidding_id")
            arquivos_edital = []

            for arquivo in item.get("edicts", []):
                if arquivo.get("filename", "").lower() == "edital.zip":
                    arquivos_edital = baixar_edital_por_json(
                        context, boletim_id, bidding_id, arquivo
                    )
                    break

            resultados.append({
                "boletim_id": boletim_id,
                "bidding_id": bidding_id,
                "orgao_cidade": item.get("orgao_cidade"),
                "orgao_estado": item.get("orgao_estado"),
                "edital": item.get("edital"),
                "edital_site": item.get("edital_site"),
                "itens": item.get("itens"),
                "descricao": item.get("descricao"),
                "datahora_abertura": item.get("datahora_abertura"),
                "datahora_prazo": item.get("datahora_prazo"),
                "valor_estimado": item.get("valor_estimado"),
                "arquivos_edital": arquivos_edital
            })

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
            inserir_boletins_google_sheets(dados)
            salvar_ultimo_boletim(max(novos))

    finally:
        browser.close()
        p.stop()

        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)

        log_message("INFO", "=== COLETA FINALIZADA ===")

if __name__ == "__main__":
    main()
