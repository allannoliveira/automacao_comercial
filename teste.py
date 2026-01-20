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
    # Print para acompanhamento em tempo real
    print(f"[{level.upper()}] {message}")

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
    r"\bENFERMAG[EMN]S?\b",
    r"\bENFERMEIROS?\b",
    r"\bEQUIPES?\s+MEDICAS?\b",
    r"\bESPECIALIDADES?\s+MEDICAS?\b",
    r"\bMEDICOS?\b",
    r"\bSERVIÇOS?\s+MEDIC[OA]S?\b",
    r"\bTELE\s*ATENDIMENTOS?\b",
    r"\bTELEATENDIMENTOS?\b",
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
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        log_message("INFO", "Conexão MySQL estabelecida com sucesso")
        return conn
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
        """Converte string de data para datetime, retorna None se inválido"""
        if not valor or str(valor).strip() == "":
            return None
        try:
            # Remove espaços extras e tenta converter
            valor_limpo = str(valor).strip()
            return datetime.strptime(valor_limpo, "%d/%m/%Y %H:%M")
        except (ValueError, AttributeError) as e:
            log_message("WARNING", f"Erro ao converter data '{valor}': {e}")
            return None

    def parse_valor_estimado(valor_str):
        """Converte string de valor para float, retorna None se inválido"""
        if not valor_str or str(valor_str).strip() == "":
            return None
        try:
            # Remove R$, pontos de milhar e substitui vírgula por ponto
            valor_limpo = (
                str(valor_str)
                .replace("R$", "")
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )
            if valor_limpo == "" or valor_limpo == "0":
                return None
            return float(valor_limpo)
        except (ValueError, AttributeError) as e:
            log_message("WARNING", f"Erro ao converter valor '{valor_str}': {e}")
            return None

    for d in dados:
        data_abertura = parse_data(d.get("data_abertura", ""))
        prazo = parse_data(d.get("prazo", ""))
        valor = parse_valor_estimado(d.get("valor_estimado"))

        # Debug: mostrar dados antes de inserir
        log_message("DEBUG", f"Processando Bidding {d.get('bidding_id')}", {
            "data_abertura_raw": d.get("data_abertura"),
            "data_abertura_parsed": str(data_abertura),
            "prazo_raw": d.get("prazo"),
            "prazo_parsed": str(prazo),
            "valor_raw": d.get("valor_estimado"),
            "valor_parsed": str(valor)
        })

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
    cursor.close()

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

    log_message("INFO", "Iniciando processo de login...")
    page.goto(LOGIN_URL, wait_until="networkidle")
    page.get_by_role("link", name="Acessar Conta").click()
    page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
    page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
    page.get_by_role("button", name="Acessar").click()
    page.wait_for_timeout(8000)

    log_message("INFO", "Login concluído com sucesso")
    return p, browser, context

# =====================================================
# EXTRAIR BOLETINS
# =====================================================
def extrair_boletins(context):
    log_message("INFO", "Extraindo lista de boletins...")
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

    log_message("INFO", f"{len(boletins)} boletins encontrados")
    return sorted(boletins)

def bate_regex(texto):
    texto = normalizar_texto(texto or "")
    return any(re.search(p, texto) for p in PADROES_REGEX)

# =====================================================
# DETALHE
# =====================================================
def extrair_situacao_e_prazo(context, bidding_id):
    """
    Extrai situação (NORMAL/URGENTE) e prazo da página de detalhes
    Retorna prazo no formato DD/MM/YYYY HH:MM ou string vazia
    """
    situacao = "NORMAL"
    prazo = ""

    page = context.new_page()
    try:
        page.goto(BOLETIM_DETAIL_URL.format(bidding_id), wait_until="networkidle", timeout=15000)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Verifica situação URGENTE
        if "URGENTE" in html.upper():
            situacao = "URGENTE"

        # Busca por prazo - pode estar em vários formatos
        prazo_tag = soup.find(string=re.compile(r"PRAZO\s*:", re.I))
        if prazo_tag:
            texto_prazo = prazo_tag.parent.get_text(strip=True)
            # Remove o label "PRAZO:"
            texto_prazo = re.sub(r"PRAZO\s*:", "", texto_prazo, flags=re.I).strip()
            
            # Tenta extrair data no formato DD/MM/YYYY HH:MM
            match_data = re.search(r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}", texto_prazo)
            if match_data:
                prazo = match_data.group()
            else:
                # Se não encontrar data formatada, guarda o texto original
                prazo = texto_prazo if texto_prazo else ""
                
        log_message("DEBUG", f"Bidding {bidding_id}: situacao={situacao}, prazo='{prazo}'")

    except PlaywrightTimeoutError:
        log_message("ERROR", f"Timeout ao acessar detalhes do bidding {bidding_id}")
    except Exception as e:
        log_message("ERROR", f"Erro ao extrair detalhes do bidding {bidding_id}: {e}")

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

    log_message("INFO", f"Coletando licitações de {len(boletins)} boletins...")

    for idx, boletim_id in enumerate(boletins, 1):
        log_message("INFO", f"Processando boletim {boletim_id} ({idx}/{len(boletins)})")
        
        try:
            resp = session.get(BIDDINGS_API.format(boletim_id), timeout=30)
            if resp.status_code != 200:
                log_message("WARNING", f"Boletim {boletim_id} retornou status {resp.status_code}")
                continue

            biddings = resp.json().get("biddings", [])
            log_message("INFO", f"Boletim {boletim_id}: {len(biddings)} licitações encontradas")

            for item in biddings:
                texto = (item.get("objeto", "") + " " + item.get("itens", "")).replace("\n", " ")

                if not bate_regex(texto):
                    continue

                log_message("INFO", f"Licitação {item['bidding_id']} corresponde aos critérios")
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

        except Exception as e:
            log_message("ERROR", f"Erro ao processar boletim {boletim_id}: {e}")

    log_message("INFO", f"Total de {len(resultados)} licitações coletadas")
    return resultados

# =====================================================
# MAIN
# =====================================================
def main():
    log_message("INFO", "=== INICIANDO COLETA DE LICITAÇÕES ===")
    
    ultimo_id = carregar_ultimo_boletim()
    log_message("INFO", f"Último boletim processado: {ultimo_id}")
    
    playwright, browser, context = criar_browser_autenticado()

    try:
        boletins = extrair_boletins(context)
        boletins_novos = [b for b in boletins if b > ultimo_id]

        if not boletins_novos:
            log_message("INFO", "Nenhum boletim novo encontrado")
            return

        log_message("INFO", f"{len(boletins_novos)} boletins novos para processar")

        resultados = coletar_licitacoes(context, boletins_novos)

        if resultados:
            conn = conectar_mysql()
            inserir_boletins_mysql(conn, resultados)
            conn.close()
            log_message("INFO", "Dados inseridos com sucesso no banco de dados")
        else:
            log_message("INFO", "Nenhuma licitação corresponde aos critérios de busca")

        salvar_ultimo_boletim(max(boletins_novos))
        log_message("INFO", f"Checkpoint atualizado: {max(boletins_novos)}")

    except Exception as e:
        log_message("CRITICAL", f"Erro fatal na execução: {e}")
        raise

    finally:
        browser.close()
        playwright.stop()
        
        # Salva log completo
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)
        
        log_message("INFO", "=== COLETA FINALIZADA ===")
        print(f"\nLog salvo em: {LOG_FILE}")

if __name__ == "__main__":
    main()