import os
import re
import requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# =========================
# CONFIG
# =========================

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1"

PIPELINE_ID = int(os.getenv("PIPEDRIVE_PIPELINE_ID", "3"))
STAGE_ID = int(os.getenv("PIPEDRIVE_STAGE_ID", "23"))

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
ABA = "aprovados"
CREDENTIALS_FILE = "credentials/google_service_account.json"

if not API_TOKEN:
    raise EnvironmentError("PIPEDRIVE_API_TOKEN não definido no .env")
if not SHEET_ID:
    raise EnvironmentError("GOOGLE_SHEET_ID não definido no .env")

# =========================
# PADRONIZAÇÃO UNIVERSAL
# =========================

MESES = {
    1: "JAN",
    2: "FEV",
    3: "MAR",
    4: "ABR",
    5: "MAI",
    6: "JUN",
    7: "JUL",
    8: "AGO",
    9: "SET",
    10: "OUT",
    11: "NOV",
    12: "DEZ"
}


def limpar_texto(valor):
    if not valor:
        return "NÃO INFORMADO"

    return str(valor).strip().upper()


# Regex para extrair o primeiro bullet do BLOCO 1 do GERED:
# "• CIDADE/UF – ÓRGÃO – ESPECIALIDADE"
_RE_BLOCO1_TITULO = re.compile(
    r"[•\*]\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n•\*]{5,120}(?:–|-)[^\n•\*]{3,80}(?:–|-)[^\n•\*]{3,80})",
    re.IGNORECASE
)


def _titulo_de_resumo(resumo: str) -> str | None:
    """Extrai o título estruturado do BLOCO 1 do GERED (primeiro bullet com 3 partes)."""
    if not resumo:
        return None

    for linha in resumo.splitlines():
        linha = linha.strip()
        # procura linha bullet com pelo menos dois separadores (– ou -)
        if not linha.startswith(("•", "*", "-")):
            continue
        conteudo = linha.lstrip("•*- ").strip()
        partes = re.split(r"\s*[–\-]\s*", conteudo)
        if len(partes) >= 3:
            # normaliza: uppercase, troca – por -
            titulo = " - ".join(p.strip().upper() for p in partes[:4] if p.strip())
            if len(titulo) > 20:
                return titulo

    return None


def _fallback_nome(dados):
    """Fallback: monta título a partir dos campos brutos."""
    municipio = limpar_texto(dados.get("orgao_cidade"))
    uf        = limpar_texto(dados.get("orgao_estado"))
    orgao_raw = limpar_texto(
        dados.get("orgao_nome") or dados.get("orgao") or dados.get("nome_orgao")
    )
    orgao = orgao_raw[:30].rsplit(" ", 1)[0] if len(orgao_raw) > 30 else orgao_raw

    objeto_raw = (
        dados.get("objeto") or dados.get("descricao") or
        dados.get("itens") or dados.get("edital") or ""
    )
    objeto = str(objeto_raw).strip().upper()[:40].rsplit(" ", 1)[0]

    return f"{municipio} - {uf} - {orgao} - {objeto}"


def gerar_nome_padrao(dados):
    """Gera o título do deal. Tenta extrair do resumo Gemini; usa fallback se não encontrar."""
    resumo = dados.get("resumo_ia") or ""
    titulo = _titulo_de_resumo(resumo)
    if titulo:
        return titulo
    return _fallback_nome(dados)


def extrair_hora(datahora_str):
    if not datahora_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(str(datahora_str).strip(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None

# =========================
# GOOGLE SHEETS
# =========================

def conectar_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=scopes
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(ABA)

    return sheet


def ler_dados(sheet):
    rows = sheet.get_all_values()
    if len(rows) < 2:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


def atualizar_flag_importado(sheet, row_index):
    col_index = 15  # coluna "importado_pipedrive"
    sheet.update_cell(row_index, col_index, "TRUE")


# =========================
# UTIL
# =========================

def aprovado_ia(valor):
    return str(valor).strip().lower() in ["true", "1", "sim", "yes"]


def formatar_data(data_str):
    if not data_str:
        return None

    if isinstance(data_str, datetime):
        return data_str.strftime("%Y-%m-%d")

    data_str = str(data_str).strip()

    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]

    for fmt in formatos:
        try:
            return datetime.strptime(data_str, fmt).strftime("%Y-%m-%d")
        except:
            continue

    return None


def converter_valor(valor):
    if not valor:
        return 0

    if isinstance(valor, (int, float)):
        return float(valor)

    valor = str(valor).strip()
    valor = valor.replace("R$", "").replace(" ", "")

    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except:
        return 0


# =========================
# PIPEDRIVE
# =========================

def buscar_deal_existente(bidding_id):
    url = f"{BASE_URL}/deals/search"
    params = {
        "api_token": API_TOKEN,
        "term": bidding_id,
        "fields": "custom_fields",
        "exact_match": True
    }

    r = requests.get(url, params=params).json()

    if r.get("data", {}).get("items"):
        return r["data"]["items"][0]["item"]["id"]

    return None


def criar_deal(dados):

    titulo_padrao = gerar_nome_padrao(dados)

    payload = {
        "title": titulo_padrao,
        "pipeline_id": PIPELINE_ID,
        "stage_id": STAGE_ID
    }

    print(f"Título gerado: {titulo_padrao}")

    url = f"{BASE_URL}/deals?api_token={API_TOKEN}"

    return requests.post(url, json=payload).json()


# =========================
# MAPEAMENTO ENUMS PIPEDRIVE
# =========================

_MODALIDADE_MAP = {
    "pregão eletrônico": 41,       "pregao eletronico": 41,
    "pregão presencial": 40,        "pregao presencial": 40,
    "credenciamento": 43,
    "cotação eletrônica": 92,       "cotacao eletronica": 92,
    "chamamento público": 96,       "chamamento publico": 96,
    "dispensa de licitação": 94,    "dispensa de licitacao": 94,
    "dispensa eletrônica": 94,      "dispensa eletronica": 94,
    "concorrência pública": 97,     "concorrencia publica": 97,
    "concorrência eletrônica": 99,  "concorrencia eletronica": 99,
    "inexigibilidade": 98,
    "sem modalidade": 144,
}

_MODO_DISPUTA_MAP = {
    "ABERTO": 76,
    "FECHADO": 77,
    "ABERTO-FECHADO": 78,
    "FECHADO-ABERTO": 79,
}

_PORTAL_URL_MAP = [
    ("portaldecompraspublicas.com.br", 47),
    ("bllcompras.com", 50),
    ("licitanet.com.br", 48),
    ("comprasnet.gov.br", 49),
    ("bbmnet.com.br", 52),
    ("licitar.digital", 53),
    ("publinexo.com.br", 54),
    ("licitamaisbrasil.com.br", 56),
    ("comprasbr.com.br", 57),
    ("banrisul.com.br", 58),
    ("compras.am.gov.br", 59),
    ("compras.rs.gov.br", 60),
    ("pncp.gov.br", 64),
    ("compras.gov.br", 46),
    ("comprasgovernamentais.gov.br", 46),
    ("bnc.org.br", 51),
]


def _portal_id(edital_site: str):
    if not edital_site:
        return None
    url = re.sub(r"https?://", "", str(edital_site)).lower()
    for pattern, pid in _PORTAL_URL_MAP:
        if pattern in url:
            return pid
    return 61  # OUTROS PORTAIS


def _modalidade_id(modalidade: str):
    if not modalidade:
        return None
    return _MODALIDADE_MAP.get(str(modalidade).strip().lower())


def _modo_disputa_id(modo: str):
    if not modo:
        return None
    return _MODO_DISPUTA_MAP.get(str(modo).strip().upper())


def atualizar_deal(deal_id, dados):
    payload = {
        # === ESCOPO EDITAL ===
        "3bb14b1ac754aecd840706f3cd52d670221257ee": dados.get("idconlicitacao"),
        "bd6e872591ceb70567b6cd75a2f8c1edfb0198e7": dados.get("edital"),
        "e43e128e00c00de6c02bfdbdb5c5526408db2f50": formatar_data(dados.get("data_publicacao") or dados.get("datahora_abertura")),
        "1400a977de9ee3cbc0a0d53aa1d3d7dc35e61443": formatar_data(dados.get("datahora_abertura")),
        "b983d5bb7f370518c749a52d5a14ab72b341a823": extrair_hora(dados.get("datahora_abertura")),
        "9ca65967f492439f97a73c0c071a5b96508c39ac": dados.get("descricao") or dados.get("itens"),
        "21a5de62805b729b00e5765fbb1ba0ce53072154": converter_valor(dados.get("valor_estimado")),
        # === CLASSIFICAÇÃO ===
        "13483a504035275a5c3f7eec34ea59d2730cb1ea": _portal_id(dados.get("edital_site")),
        "407fdaabe344549d85b6761509a54aa381129e72": _modalidade_id(dados.get("modalidade")),
        "be66b17ec248f7eabcaa0657563498b034e41534": _modo_disputa_id(dados.get("modo_disputa")),
    }

    # Remove campos sem valor para não sobrescrever com None
    payload = {k: v for k, v in payload.items() if v not in (None, "", 0)}

    url = f"{BASE_URL}/deals/{deal_id}?api_token={API_TOKEN}"
    return requests.put(url, json=payload).json()


def criar_nota(deal_id, texto):
    if not texto:
        return None

    payload = {
        "deal_id": deal_id,
        "content": texto
    }

    url = f"{BASE_URL}/notes?api_token={API_TOKEN}"
    return requests.post(url, json=payload).json()


# =========================
# IMPORTAÇÃO UNITÁRIA (inline, sem ler planilha)
# =========================

def importar_deal_unico(dados):
    """Cria/atualiza um deal diretamente de um dict de licitacao_dados.
    Normaliza aliases de campo entre o dict interno e a planilha.
    Retorna o deal_id criado/existente, ou None em caso de falha."""

    dados_norm = dict(dados)
    # bidding_id (interno) ↔ idconlicitacao (planilha / Pipedrive)
    if not dados_norm.get("idconlicitacao"):
        dados_norm["idconlicitacao"] = dados_norm.get("bidding_id", "")
    # link_drive (interno) ↔ link_drive_edital (planilha)
    if not dados_norm.get("link_drive_edital"):
        dados_norm["link_drive_edital"] = dados_norm.get("link_drive", "")

    bidding_id = str(dados_norm.get("idconlicitacao", "")).strip()
    if not bidding_id:
        print("[PIPEDRIVE] idconlicitacao vazio — pulando")
        return None

    existente = buscar_deal_existente(bidding_id)
    if existente:
        print(f"[PIPEDRIVE] Deal já existe: {existente}")
        return existente

    criado = criar_deal(dados_norm)
    if not criado.get("success"):
        print(f"[PIPEDRIVE] Erro ao criar deal: {criado}")
        return None

    deal_id = criado["data"]["id"]
    print(f"[PIPEDRIVE] Deal criado inline: {deal_id}")

    atualizar_deal(deal_id, dados_norm)

    criar_nota(deal_id, dados_norm.get("resumo_ia"))
    link = dados_norm.get("link_drive_edital") or ""
    if link:
        criar_nota(deal_id, f"Pasta no Google Drive:\n{link}")

    return deal_id


# =========================
# PROCESSAMENTO (batch — lê planilha, serve como fallback/retry)
# =========================

def processar():
    sheet = conectar_sheet()
    dados = ler_dados(sheet)

    for i, linha in enumerate(dados, start=2):  # começa na linha 2

        print("\n====================")
        print("Edital:", linha.get("edital"))

        # 1 - já importado?
        if str(linha.get("importado_pipedrive")).lower() == "true":
            print("Já importado")
            continue

        # 2 - aprovado IA?
        if not aprovado_ia(linha.get("aprovado_ia")):
            print("Reprovado pela IA")
            continue

        # 3 - duplicado?
        existente = buscar_deal_existente(linha.get("idconlicitacao"))
        if existente:
            print("Já existe no Pipedrive:", existente)
            atualizar_flag_importado(sheet, i)
            continue

        # 4 - criar deal
        criado = criar_deal(linha)

        if not criado.get("success"):
            print("Erro ao criar:", criado)
            continue

        deal_id = criado["data"]["id"]
        print("Criado:", deal_id)

        # 5 - atualizar
        atualizar_deal(deal_id, linha)

        # 6 - notas
        criar_nota(deal_id, linha.get("resumo_ia"))
        if linha.get("link_drive_edital"):
            criar_nota(deal_id, f"Pasta no Google Drive:\n{linha.get('link_drive_edital')}")

        # 7 - marcar planilha
        atualizar_flag_importado(sheet, i)

        print("FINALIZADO")


# =========================
# TESTE — importa os últimos N aprovados sem marcar importado_pipedrive
# =========================

def _adicionar_notas(deal_id, linha):
    criar_nota(deal_id, linha.get("resumo_ia"))
    link_drive = linha.get("link_drive_edital") or ""
    if link_drive:
        criar_nota(deal_id, f"Pasta no Google Drive:\n{link_drive}")
        print(f"Nota Drive adicionada: {link_drive}")
    else:
        print("AVISO: link_drive_edital vazio na planilha")


def testar_importacao(n=2):
    sheet = conectar_sheet()
    dados = ler_dados(sheet)

    aprovados = [l for l in dados if aprovado_ia(l.get("aprovado_ia"))]

    if not aprovados:
        print("Nenhum registro aprovado na planilha")
        return

    candidatos = aprovados[-n:]
    print(f"Testando {len(candidatos)} registro(s)...\n")

    for linha in candidatos:
        print("=" * 50)
        print(f"Edital          : {linha.get('edital')}")
        print(f"Cidade          : {linha.get('orgao_cidade')} – {linha.get('orgao_estado')}")
        print(f"Orgao           : {linha.get('orgao_nome')}")
        print(f"Link Drive      : {linha.get('link_drive_edital') or '(vazio)'}")
        print(f"Modalidade      : {linha.get('modalidade') or '(vazio)'}")
        print(f"Modo Disputa    : {linha.get('modo_disputa') or '(vazio)'}")

        existente = buscar_deal_existente(linha.get("idconlicitacao"))

        if existente:
            print(f"Deal ja existe ({existente}) — atualizando campos e adicionando notas...")
            atualizar_deal(existente, linha)
            _adicionar_notas(existente, linha)
            print("FINALIZADO (importado_pipedrive NAO marcado — modo teste)")
            continue

        criado = criar_deal(linha)
        if not criado.get("success"):
            print(f"Erro ao criar deal: {criado}")
            continue

        deal_id = criado["data"]["id"]
        print(f"Deal criado: {deal_id}")

        atualizar_deal(deal_id, linha)
        _adicionar_notas(deal_id, linha)

        print("FINALIZADO (importado_pipedrive NAO marcado — modo teste)")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--teste":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        testar_importacao(n)
    else:
        processar()
