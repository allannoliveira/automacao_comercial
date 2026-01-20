import csv
import requests
from datetime import datetime

# =========================
# CONFIGURACAO
# =========================

API_TOKEN = "7b468a4d212b9a56888de85994e639f93505fe4c"
BASE_URL = "https://api.pipedrive.com/v1"

PIPELINE_ID = 3
STAGE_ID = 23


# =========================
# UTILITARIOS
# =========================

def formatar_data(data_str):
    if not data_str:
        return None

    data_str = data_str.strip()

    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y"
    ]

    for fmt in formatos:
        try:
            return datetime.strptime(data_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    print("Data nao reconhecida:", data_str)
    return None


def converter_valor_monetario(valor_str):
    if not valor_str:
        return 0.0

    valor = valor_str.replace("R$", "").replace(" ", "")
    valor = valor.replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except ValueError:
        print("Valor invalido:", valor_str)
        return 0.0


# =========================
# PAYLOADS
# =========================

def payload_criacao(dados):
    return {
        "title": f"Edital {dados['edital']} - {dados['cidade']}/{dados['estado']}",
        "pipeline_id": PIPELINE_ID,
        "stage_id": STAGE_ID,
        "status": "open"
    }


def payload_atualizacao(dados):
    return {
        # ID Conlicitacao (bidding_id)
        "3bb14b1ac754aecd840706f3cd52d670221257ee": dados.get("bidding_id"),

        # Numero do Edital
        "bd6e872591ceb70567b6cd75a2f8c1edfb0198e7": dados.get("edital"),

        # Data Disputa
        "1400a977de9ee3cbc0a0d53aa1d3d7dc35e61443": formatar_data(dados.get("data_abertura")),

        # Valor Bruto
        "21a5de62805b729b00e5765fbb1ba0ce53072154": converter_valor_monetario(dados.get("valor_estimado"))
    }


# =========================
# API - DEALS
# =========================

def criar_deal(dados):
    url = f"{BASE_URL}/deals"
    params = {"api_token": API_TOKEN}

    response = requests.post(url, params=params, json=payload_criacao(dados))
    return response.json()


def atualizar_deal(deal_id, dados):
    url = f"{BASE_URL}/deals/{deal_id}"
    params = {"api_token": API_TOKEN}

    response = requests.put(url, params=params, json=payload_atualizacao(dados))
    return response.json()


# =========================
# API - NOTES (ANOTACOES)
# =========================

def criar_anotacao(deal_id, descricao):
    if not descricao:
        return None

    url = f"{BASE_URL}/notes"
    params = {"api_token": API_TOKEN}

    payload = {
        "deal_id": deal_id,
        "content": descricao
    }

    response = requests.post(url, params=params, json=payload)
    return response.json()


# =========================
# CSV
# =========================

def importar_csv(caminho_csv):
    with open(caminho_csv, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for linha in reader:
            print("\nProcessando edital", linha.get("edital"))

            # 1 - CRIAR DEAL
            criado = criar_deal(linha)

            if not criado.get("success"):
                print("Erro ao criar deal:", criado)
                continue

            deal_id = criado["data"]["id"]
            print("Deal criado - ID", deal_id)

            # 2 - ATUALIZAR DEAL
            atualizado = atualizar_deal(deal_id, linha)

            if atualizado.get("success"):
                print("Deal atualizado com sucesso - ID", deal_id)
            else:
                print("Erro ao atualizar deal", deal_id, atualizado)
                continue

            # 3 - CRIAR ANOTACAO (DESCRICAO)
            nota = criar_anotacao(deal_id, linha.get("descricao"))

            if nota and nota.get("success"):
                print("Anotacao criada para o deal", deal_id)
            else:
                print("Nenhuma anotacao criada para o deal", deal_id)


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    importar_csv("input_data/licitacoes_filtradas.csv")
