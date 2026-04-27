import requests
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =========================
# CONFIG
# =========================

API_TOKEN = "7b468a4d212b9a56888de85994e639f93505fe4c"
BASE_URL = "https://api.pipedrive.com/v1"

PIPELINE_ID = 3
STAGE_ID = 23

GOOGLE_SHEET_NAME = "licitacoes"
ABA = "Página1"

# =========================
# GOOGLE SHEETS
# =========================

def conectar_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )

    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(ABA)

    return sheet


def ler_dados(sheet):
    return sheet.get_all_records()


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

    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S"
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

    valor = valor.replace("R$", "").replace(".", "").replace(",", ".")
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
    payload = {
        "title": f"{dados['edital']} | {dados['orgao_cidade']}/{dados['orgao_estado']}",
        "pipeline_id": PIPELINE_ID,
        "stage_id": STAGE_ID
    }

    url = f"{BASE_URL}/deals?api_token={API_TOKEN}"
    return requests.post(url, json=payload).json()


def atualizar_deal(deal_id, dados):
    payload = {
        "3bb14b1ac754aecd840706f3cd52d670221257ee": dados["idconlicitacao"],
        "bd6e872591ceb70567b6cd75a2f8c1edfb0198e7": dados["edital"],
        "1400a977de9ee3cbc0a0d53aa1d3d7dc35e61443": formatar_data(dados["datahora_abertura"]),
        "21a5de62805b729b00e5765fbb1ba0ce53072154": converter_valor(dados["valor_estimado"])
    }

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
# PROCESSAMENTO
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

        # 6 - nota IA
        criar_nota(deal_id, linha.get("resumo_ia"))

        # 7 - marcar planilha
        atualizar_flag_importado(sheet, i)

        print("FINALIZADO 🚀")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    processar()