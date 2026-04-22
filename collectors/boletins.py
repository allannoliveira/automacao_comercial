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

#from services.gemini_service import analisar_edital
from services.drive_service import criar_pasta, upload_arquivo_para_pasta, SHARED_DRIVE_ID
from services.gemini_queue import GeminiQueue


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
gemini_queue = GeminiQueue(delay=15)  # 15 segundos entre envios
PROMPT_GERED = """
Você é o GERED, especialista em análise de editais de saúde.

REGRAS:
- Responda em tópicos (*)
- Perguntas em NEGRITO e CAIXA ALTA
- Respostas em texto normal
- Uma linha por item
- Sem explicações extras
- Se não houver informação: NÃO CONSTA

EXECUTE TODOS OS BLOCOS EM SEQUÊNCIA.

BLOCO 1 – DADOS CADASTRAIS
• ATA LICITATÓRIA:
• OBJETO DA DISPUTA:
• DATA PUBLICAÇÃO EDITAL:
• DATA E HORÁRIO DISPUTA:
• VALOR BRUTO:
• UNIDADE DE DISPUTA:
• VALOR MÁXIMO POR UNIDADE:
• INSTITUIÇÃO CONTRATANTE:
• TIPO CONTRATANTE:
• LOCAL PRESTAÇÃO SERVIÇO:
• MUNICÍPIO E UF:

BLOCO 2 – ANÁLISE TÉCNICA
• ESPECIALIDADES MÉDICAS EXIGIDAS:
• QUALIFICAÇÕES TÉCNICAS MÉDICAS:
• EXIGÊNCIAS IDENTIFICADAS:
• RISCO DE INTERPRETAÇÃO:
• DETALHAMENTO DE HORAS:
• VALORES POR ESPECIALIDADE:

BLOCO 3 – CONTEXTO
• POPULAÇÃO ESTIMADA MUNICÍPIO:
• NÚMERO MÉDICOS MUNICÍPIO:
• MÉDICOS POR MIL HABITANTES:
• FACULDADE MEDICINA:
• MUNICÍPIO POLO MAIS PRÓXIMO:

BLOCO 4 – REQUISITOS
• GARANTIA EXIGIDA:
• QUALIFICAÇÃO ECONÔMICA EXIGIDA:
• ANTECIPAÇÃO DE PAGAMENTOS EXIGIDA:
• APRESENTAÇÃO DOS PROFISSIONAIS EXIGIDA:
• VISITA TÉCNICA EXIGIDA:
• QUALIFICAÇÕES TÉCNICAS EXIGIDAS:

RETORNE O STATUS FINAL OBRIGATORIAMENTE NA ÚLTIMA LINHA NO FORMATO:

STATUS_FINAL: APROVADO
OU
STATUS_FINAL: REPROVADO
"""

MODO_TESTE = False
TESTE_LIMITE = 1

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
        json.dump({
            "ultimo_id": boletim_id,
            "data_processamento": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)

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
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def atualizar_status_planilha(sheet, bidding_id, aprovado, link_drive, link_txt):
    """
    Colunas da planilha:
    1  boletim_id
    2  idconlicitacao
    3  orgao_cidade
    4  orgao_estado
    5  edital
    6  edital_site
    7  itens
    8  descricao
    9  valor_estimado
    10 datahora_abertura
    11 datahora_prazo
    12 data_coleta
    13 aprovado_ia
    14 link_drive_edital
    15 importado_pipedrive
    16 resumo_ia  ← salva o link do TXT aqui
    """
    col_ids = sheet.col_values(2)

    for i, val in enumerate(col_ids):
        if val == str(bidding_id):
            linha = i + 1
            sheet.update_cell(linha, 13, aprovado)    # aprovado_ia
            sheet.update_cell(linha, 14, link_drive)  # link_drive_edital
            sheet.update_cell(linha, 16, link_txt)    # resumo_ia ← link do TXT
            break

def inserir_boletins_google_sheets(sheet, dados):

    valores_coluna = sheet.col_values(2)
    ids_existentes = set(valores_coluna[1:]) if len(valores_coluna) > 1 else set()

    novas_linhas = []

    for d in dados:
        bidding_id = str(d.get("bidding_id")).strip()

        if bidding_id in ids_existentes:
            continue

        novas_linhas.append([
            d.get("boletim_id") or "",
            bidding_id,
            d.get("orgao_cidade") or "",
            d.get("orgao_estado") or "",
            d.get("edital") or "",
            d.get("edital_site") or "",
            d.get("itens") or "",
            d.get("descricao") or "",
            d.get("valor_estimado") or "",
            d.get("datahora_abertura") or "",
            d.get("datahora_prazo") or "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            d.get("status_ia") or "",
            d.get("link_drive") or "",
            "",                            # importado_pipedrive (col 15) — vazio
            d.get("link_txt") or "",       # resumo_ia (col 16) ← link do TXT
        ])

    if novas_linhas:
        sheet.append_rows(novas_linhas, value_input_option="USER_ENTERED")
        print(f"{len(novas_linhas)} linhas inseridas na planilha")

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
# ATIVAR BOLETIM (ESSENCIAL)
# =====================================================
def ativar_boletim_html(context, boletim_id):
    page = context.new_page()
    try:
        url = f"https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins/{boletim_id}"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
    finally:
        page.close()

# =====================================================
# EXTRAIR BOLETINS
# =====================================================
def extrair_boletins(context):
    log_message("INFO", "Extraindo boletins via Playwright (FullCalendar)")

    page = context.new_page()
    boletins = set()

    try:
        page.goto(
            CALENDARIO_URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_selector(".fc-event", state="attached", timeout=60000)
        page.wait_for_timeout(5000)

        eventos = page.locator(".fc-event").all()

        for ev in eventos:
            try:
                html = ev.inner_html()
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
# DOWNLOAD EDITAL
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

    response = session.get(url_completa, timeout=60)

    if response.status_code != 200:
        log_message("WARNING", f"Arquivo não disponível {bidding_id}")
        return []

    caminho = pasta_base / filename

    with open(caminho, "wb") as f:
        f.write(response.content)

    arquivos_extraidos = []

    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(caminho, 'r') as zip_ref:
            zip_ref.extractall(pasta_base)
            for nome in zip_ref.namelist():
                arquivos_extraidos.append(str(pasta_base / nome))
        caminho.unlink()
        return arquivos_extraidos

    return [str(caminho)]

# =====================================================
# MONTAR NOME PASTA
# =====================================================
def montar_nome_pasta(dados):
    ano_mes = datetime.now().strftime("%Y %m")
    municipio = (dados.get("orgao_cidade") or "").upper()
    uf = (dados.get("orgao_estado") or "").upper()
    orgao = (dados.get("orgao_cidade") or "").upper()
    objeto = (dados.get("edital") or "").upper()

    nome = f"{ano_mes} - {municipio} - {uf} - {orgao} - {objeto}"
    return nome.replace("/", "-")

# =====================================================
# COLETAR LICITAÇÕES
# =====================================================
def coletar_licitacoes(context, boletins):

    resultados = []
    sheet = conectar_google_sheets()
    contador_teste = 0

    for boletim_id in boletins:

        ativar_boletim_html(context, boletim_id)

        session = requests.Session()
        for c in context.cookies():
            session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

        resp = session.get(BIDDINGS_API.format(boletim_id), timeout=30)

        if resp.status_code != 200:
            log_message("WARNING", f"API falhou {boletim_id}")
            continue

        try:
            dados_json = resp.json()
        except Exception:
            log_message("ERROR", f"Resposta inválida API {boletim_id} | Conteúdo: {resp.text[:200]}")
            continue

        biddings = dados_json.get("biddings", [])

        for item in biddings:

            if MODO_TESTE and contador_teste >= TESTE_LIMITE:
                log_message("INFO", "Modo teste ativo - encerrando")
                return resultados

            bidding_id = item.get("bidding_id")
            arquivos_edital = []

            # --------------------------------------------
            # DOWNLOAD DO EDITAL
            # --------------------------------------------
            for arquivo in item.get("edicts", []):
                if arquivo.get("filename", "").lower() == "edital.zip":
                    arquivos_edital = baixar_edital_por_json(
                        context, boletim_id, bidding_id, arquivo
                    )
                    break

            # --------------------------------------------
            # PROCESSAMENTO IA
            # --------------------------------------------
            # Inicializa sempre para evitar NameError
            texto_ia = ""
            status_ia = "NAO"

            pdf_principal = next(
                (a for a in arquivos_edital if a.lower().endswith(".pdf")),
                None
            )

            if pdf_principal:
                texto_ia, status_ia = gemini_queue.processar(pdf_principal, PROMPT_GERED)
                log_message("INFO", f"Gemini retornou - Status: {status_ia} | Chars: {len(texto_ia or '')}")
            else:
                log_message("WARNING", f"Nenhum PDF encontrado para bidding {bidding_id}")

            # --------------------------------------------
            # DRIVE
            # --------------------------------------------
            link_drive = ""
            link_txt = ""

            if status_ia in ["SIM", "NAO"]:

                if status_ia == "SIM":
                    pasta_tipo_id = criar_pasta("APROVADOS", SHARED_DRIVE_ID)
                else:
                    pasta_tipo_id = criar_pasta("REPROVADOS", SHARED_DRIVE_ID)

                nome_pasta = montar_nome_pasta(item)
                pasta_id = criar_pasta(nome_pasta, pasta_tipo_id)

                # Gera TXT com resposta do Gemini e adiciona à lista de upload
                if texto_ia:
                    caminho_txt = pathlib.Path("downloads") / str(boletim_id) / str(bidding_id) / "resumo_gemini.txt"
                    caminho_txt.parent.mkdir(parents=True, exist_ok=True)
                    with open(caminho_txt, "w", encoding="utf-8") as f:
                        f.write(texto_ia)
                    arquivos_edital.append(str(caminho_txt))

                # Upload de todos os arquivos (edital + TXT)
                file_id_txt = None
                for arquivo in arquivos_edital:
                    file_id = upload_arquivo_para_pasta(arquivo, pasta_id)
                    if arquivo.endswith("resumo_gemini.txt"):
                        file_id_txt = file_id

                # Link direto para o TXT no Drive
                if file_id_txt:
                    link_txt = f"https://drive.google.com/file/d/{file_id_txt}/view"

                link_drive = f"https://drive.google.com/drive/folders/{pasta_id}"

            else:
                log_message("WARNING", f"IA falhou para {bidding_id}, upload ignorado.")

            # --------------------------------------------
            # PLANILHA
            # --------------------------------------------
            atualizar_status_planilha(
                sheet,
                bidding_id,
                status_ia,
                link_drive,
                link_txt       # ← link do TXT vai para coluna resumo_ia (col 16)
            )

            resultados.append({
                "boletim_id": boletim_id,
                "bidding_id": bidding_id,
                "orgao_cidade": item.get("orgao_cidade"),
                "orgao_estado": item.get("orgao_estado"),
                "edital": item.get("edital"),
                "edital_site": item.get("edital_site"),
                "itens": item.get("itens"),
                "descricao": item.get("descricao"),
                "valor_estimado": item.get("valor_estimado"),
                "datahora_abertura": item.get("datahora_abertura"),
                "datahora_prazo": item.get("datahora_prazo"),
                "status_ia": status_ia,
                "link_drive": link_drive,
                "link_txt": link_txt,      # ← link do TXT para inserir na planilha
            })
            contador_teste += 1

    return resultados

# =====================================================
# MAIN
# =====================================================
def main():

    log_message("INFO", "=== INICIANDO COLETA ===")

    ultimo = carregar_ultimo_boletim()

    p, browser, context = criar_browser_autenticado()

    try:
        boletins = extrair_boletins(context)
        novos = [b for b in boletins if b > ultimo]

        if not novos:
            log_message("INFO", "Nenhum boletim novo encontrado")
            return

        dados = coletar_licitacoes(context, novos)

        if dados:
            sheet = conectar_google_sheets()
            inserir_boletins_google_sheets(sheet, dados)
            salvar_ultimo_boletim(max(novos))

    finally:
        browser.close()
        p.stop()

if __name__ == "__main__":
    main()