import re
import csv
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# =====================================================
# CONFIGURAÇÕES
# =====================================================
LOGIN_URL = "https://conlicitacao.com.br/"
CALENDARIO_URL = "https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins"
BIDDINGS_API = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins/{}/biddings.json"
BOLETIM_DETAIL_URL = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins/{}"

CSV_OUTPUT = "licitacoes_filtradas.csv"
CHECKPOINT_FILE = "ultimo_boletim.json"
LOG_FILE = "coleta_log.json"

CSV_HEADERS = [
    "boletim_id", "bidding_id", "edital", "data_abertura", "valor_estimado",
    "cidade", "estado", "descricao", "situacao", "prazo", "data_coleta"
]

# =====================================================
# LOG EM MEMÓRIA
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
# PALAVRAS-CHAVE (REGEX)
# =====================================================
PADROES_REGEX = [
    r"\bconsultas?\b", r"\benfermage[mn]s?\b", r"\benfermeiros?\b",
    r"\bequipes?\s+(?:de\s+)?enfermage[mn]s?\b", r"\bequipes?\s+(?:para\s+)?enfermage[mn]s?\b",
    r"\bequipes?\s+medicas?\b", r"\bespecialidades?\s+medicas?\b",
    r"\bgest(?:ao|ão|ôes|oes)\s+(?:de\s+)?enfermage[mn]s?\b",
    r"\bgest(?:ao|ão|ôes|oes)\s+medicas?\b", r"\bgest(?:ao|ão|ôes|oes)\s+medicos?\b",
    r"\bmaos?\s+(?:de\s+)?obras?\s+(?:de\s+)?enfermage[mn]s?\b",
    r"\bmaos?\s+(?:de\s+)?obras?\s+medicas?\b", r"\bmedicos?\b",
    r"\bserviços?\s+medic[oa]s?\b", r"\btele\s*atendimentos?\b", r"\bteleatendimentos?\b",
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
    data = {"ultimo_id": boletim_id, "data_processamento": datetime.now().isoformat()}
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# =====================================================
# CREDENCIAIS
# =====================================================
def carregar_credenciais():
    caminho = "credentials/credentials.json"
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {caminho}")
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

# =====================================================
# LOGIN
# =====================================================
def criar_browser_autenticado():
    creds = carregar_credenciais()
    log_message("INFO", "Iniciando login com Playwright")
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    page.goto(LOGIN_URL, wait_until="networkidle")
    page.get_by_role("link", name="Acessar Conta").click()
    page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
    page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
    page.get_by_role("button", name="Acessar").click()
    page.wait_for_timeout(10000)
    log_message("INFO", "Login concluído")
    return p, browser, context

# =====================================================
# EXTRAIR BOLETINS
# =====================================================
def extrair_boletins(context):
    log_message("INFO", "Acessando calendário de boletins")
    page = context.new_page()
    page.goto(CALENDARIO_URL, wait_until="networkidle")
    page.wait_for_timeout(5000)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    html = page.content()
    page.close()

    soup = BeautifulSoup(html, "html.parser")
    boletins = set()
    for link in soup.find_all('a', href=True):
        href = link['href']
        match = re.search(r'\b\d{8,}\b', href)
        if match:
            boletins.add(int(match.group()))

    log_message("INFO", f"Boletins encontrados: {len(boletins)}")
    return sorted(boletins)

# =====================================================
# FILTRO REGEX
# =====================================================
def bate_regex(texto):
    if not texto:
        return False
    texto = texto.lower().replace('ã', 'a').replace('õ', 'o').replace('ô', 'o') \
                          .replace('á', 'a').replace('é', 'e').replace('í', 'i') \
                          .replace('ó', 'o').replace('ú', 'u').replace('ç', 'c')
    return any(re.search(p, texto, re.IGNORECASE) for p in PADROES_REGEX)

# =====================================================
# EXTRAIR DETALHE - COM CORREÇÕES DE CLIQUE
# =====================================================
def extrair_situacao_e_prazo(context, boletim_id, bidding_id):
    situacao = "NORMAL"
    prazo = ""

    log_message("INFO", f"Extraindo licitação {bidding_id} do boletim {boletim_id}", {"bidding_id": str(bidding_id)})
    page = context.new_page()
    try:
        boletim_url = BOLETIM_DETAIL_URL.format(boletim_id)
        page.goto(boletim_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        # Seletor mais preciso: link que leva para a página de detalhe (não para arquivos)
        link_selector = f'a[href*="/biddings/{bidding_id}"][href!*="arquivos"], a[href*="/licitacoes/{bidding_id}"][href!*="arquivos"]'
        locator = page.locator(link_selector)

        if locator.count() > 0:
            # Espera overlay/tour desaparecer
            page.wait_for_selector("#___reactour", state="detached", timeout=10000).or_else(None)

            log_message("INFO", f"Link encontrado para {bidding_id}. Tentando clique...", {"bidding_id": str(bidding_id)})
            try:
                locator.first.click(timeout=45000, force=True)  # force para ignorar interceptações leves
                page.wait_for_timeout(8000)
            except PlaywrightTimeoutError:
                log_message("WARNING", f"Timeout no clique para {bidding_id}. Usando URL direta.", {"bidding_id": str(bidding_id)})
                page.goto(f"https://consultaonline.conlicitacao.com.br/boletim_web/public/biddings/{bidding_id}", wait_until="networkidle")
        else:
            log_message("INFO", f"Link não encontrado. Usando URL direta para {bidding_id}")
            page.goto(f"https://consultaonline.conlicitacao.com.br/boletim_web/public/biddings/{bidding_id}", wait_until="networkidle")

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Situação
        urgente_tag = soup.find("span", class_=re.compile(r"bidding-situation-urgente|urgente", re.I))
        if urgente_tag:
            situacao = urgente_tag.get_text(strip=True).upper()
        elif "URGENTE" in html.upper():
            situacao = "URGENTE"

        # Prazo
        prazo_div = soup.find("div", class_=re.compile(r"col-md-4 d-flex|text-secondary"))
        if prazo_div:
            prazo_text = prazo_div.get_text(strip=True)
            if "Prazo:" in prazo_text:
                prazo = prazo_text.split("Prazo:")[-1].strip()

        log_message("INFO", f"Situação: {situacao} | Prazo: {prazo}", {"bidding_id": str(bidding_id)})

    except Exception as e:
        log_message("ERROR", f"Erro ao extrair {bidding_id}: {str(e)}", {"bidding_id": str(bidding_id), "error": str(e)})
        situacao = "Erro na consulta"

    finally:
        page.close()

    return situacao, prazo

# =====================================================
# COLETAR LICITAÇÕES
# =====================================================
def coletar_licitacoes(context, boletins):
    resultados = []
    import requests
    session = requests.Session()
    for cookie in context.cookies():
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'), path=cookie.get('path', '/'))

    for idx, boletim_id in enumerate(boletins, 1):
        log_message("INFO", f"Processando boletim {idx}/{len(boletins)} → {boletim_id}", {"boletim_id": boletim_id})
        try:
            resp = session.get(BIDDINGS_API.format(boletim_id), params={"page": 1, "per_page": 100}, timeout=30)
            if resp.status_code != 200:
                log_message("WARNING", f"API status {resp.status_code} para boletim {boletim_id}")
                continue

            biddings = resp.json().get("biddings", [])
            log_message("INFO", f"Encontradas {len(biddings)} licitações no boletim {boletim_id}")

            for item in biddings:
                texto = (str(item.get("objeto", "")) + " " + str(item.get("itens", ""))).replace("\n", " ")
                if not bate_regex(texto):
                    continue

                bidding_id = item.get("bidding_id")
                if not bidding_id:
                    continue

                situacao, prazo = extrair_situacao_e_prazo(context, boletim_id, bidding_id)

                data_abertura = item.get("data_abertura") or ""
                valor_estimado = item.get("valor_estimado") or item.get("valor") or ""
                if isinstance(valor_estimado, (int, float)):
                    valor_estimado = f"R$ {valor_estimado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                data_coleta = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                resultados.append({
                    "boletim_id": boletim_id,
                    "bidding_id": bidding_id,
                    "edital": item.get("edital", ""),
                    "data_abertura": data_abertura,
                    "valor_estimado": valor_estimado,
                    "cidade": item.get("orgao_cidade", ""),
                    "estado": item.get("orgao_estado", ""),
                    "descricao": texto,
                    "situacao": situacao,
                    "prazo": prazo,
                    "data_coleta": data_coleta
                })

        except Exception as e:
            log_message("ERROR", f"Erro no boletim {boletim_id}: {str(e)}", {"boletim_id": boletim_id})

    return resultados

# =====================================================
# MAIN
# =====================================================
def main():
    log_message("INFO", "Iniciando script de coleta")
    ultimo_id = carregar_ultimo_boletim()
    log_message("INFO", f"Último boletim processado: {ultimo_id if ultimo_id > 0 else 'Primeira execução'}")

    playwright, browser, context = criar_browser_autenticado()

    try:
        boletins = extrair_boletins(context)
        if not boletins:
            log_message("WARNING", "Nenhum boletim encontrado")
            return

        boletins_novos = [b for b in boletins if b > ultimo_id]
        if not boletins_novos:
            log_message("INFO", "Nenhum boletim novo")
            return

        resultados = coletar_licitacoes(context, boletins_novos)

        if resultados:
            existe = os.path.exists(CSV_OUTPUT)
            with open(CSV_OUTPUT, "a" if existe else "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                if not existe:
                    writer.writeheader()
                writer.writerows(resultados)
            log_message("INFO", f"{len(resultados)} licitações salvas em {CSV_OUTPUT}")

        if boletins_novos:
            salvar_ultimo_boletim(max(boletins_novos))
            log_message("INFO", f"Checkpoint atualizado para {max(boletins_novos)}")

    except Exception as e:
        log_message("CRITICAL", f"Erro fatal: {str(e)}")

    finally:
        browser.close()
        playwright.stop()
        log_message("INFO", "Sessão do navegador encerrada")

        # Salva log
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)
        print(f"Log salvo em: {os.path.abspath(LOG_FILE)}")

if __name__ == "__main__":
    main()