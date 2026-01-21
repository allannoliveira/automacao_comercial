import mysql.connector
import requests
from datetime import datetime

# ================= CONFIG =================
API_TOKEN = "7b468a4d212b9a56888de85994e639f93505fe4c"
BASE_URL = "https://api.pipedrive.com/v1"

PIPELINE_ID = 3
STAGE_ID = 23  # Qualificado

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "licitacoes",
    "port": 3306,
    "autocommit": False
}

# Campos personalizados Pipedrive
CAMPO_ID_CONLICITACAO = "3bb14b1ac754aecd840706f3cd52d670221257ee"  # bidding_id
CAMPO_EDITAL = "bd6e872591ceb70567b6cd75a2f8c1edfb0198e7"
CAMPO_DATA_DISPUTA = "1400a977de9ee3cbc0a0d53aa1d3d7dc35e61443"
CAMPO_HORA_DISPUTA = "b983d5bb7f370518c749a52d5a14ab72b341a823"
CAMPO_VALOR_BRUTO = "21a5de62805b729b00e5765fbb1ba0ce53072154"
# =========================================


# ---------- UTIL ----------
def tratar_valor(valor):
    if not valor:
        return None

    valor = str(valor)
    return float(
        valor.replace("R$", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )


def tratar_data_hora(data_str):
    if not data_str:
        return None, None

    if isinstance(data_str, datetime):
        return data_str.date().isoformat(), data_str.strftime("%H:%M")

    dt = datetime.strptime(str(data_str), "%d/%m/%Y %H:%M")
    return dt.date().isoformat(), dt.strftime("%H:%M")


# ---------- BUSCA DUPLICIDADE ----------
def buscar_deal_por_bidding_id(bidding_id):
    if not bidding_id:
        return None

    url = f"{BASE_URL}/deals/search"
    params = {
        "api_token": API_TOKEN,
        "term": str(bidding_id),
        "fields": CAMPO_ID_CONLICITACAO,
        "exact_match": True
    }

    r = requests.get(url, params=params)
    data = r.json()

    if data.get("success") and data["data"]["items"]:
        return data["data"]["items"][0]["item"]["id"]

    return None


# ---------- CREATE DEAL ----------
def criar_deal(dados):
    url = f"{BASE_URL}/deals"

    edital = str(dados.get("edital", "")).strip()
    cidade = str(dados.get("cidade", "")).strip().upper()
    estado = str(dados.get("estado", "")).strip().upper()

    titulo = f"EDITAL {edital}"
    if cidade and estado:
        titulo += f" - {cidade}/{estado}"

    payload = {
        "title": titulo,
        "pipeline_id": PIPELINE_ID,
        "stage_id": STAGE_ID,
        CAMPO_EDITAL: edital,
        CAMPO_ID_CONLICITACAO: dados.get("bidding_id")
    }

    return requests.post(url, params={"api_token": API_TOKEN}, json=payload).json()


# ---------- UPDATE DEAL ----------
def atualizar_deal(deal_id, dados):
    url = f"{BASE_URL}/deals/{deal_id}"
    data_disputa, hora_disputa = tratar_data_hora(dados.get("data_abertura"))

    payload = {
        CAMPO_ID_CONLICITACAO: dados.get("bidding_id"),
        CAMPO_EDITAL: dados.get("edital"),
        CAMPO_VALOR_BRUTO: tratar_valor(dados.get("valor_estimado")),
        CAMPO_DATA_DISPUTA: data_disputa,
        CAMPO_HORA_DISPUTA: hora_disputa
    }

    return requests.put(url, params={"api_token": API_TOKEN}, json=payload).json()


# ---------- NOTA ----------
def criar_anotacao(deal_id, descricao):
    if not descricao:
        return None

    url = f"{BASE_URL}/notes"
    payload = {
        "content": descricao,
        "deal_id": deal_id
    }

    return requests.post(url, params={"api_token": API_TOKEN}, json=payload).json()


# ---------- MARCAR SINCRONIZADO ----------
def marcar_sincronizado(cursor, boletim_id):
    cursor.execute("""
        UPDATE boletins
        SET sincronizado_pipedrive = 1,
            data_sincronizacao = NOW()
        WHERE boletim_id = %s
    """, (boletim_id,))


# ---------- MYSQL ----------
def importar_mysql():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            boletim_id,
            bidding_id,
            edital,
            data_abertura,
            valor_estimado,
            cidade,
            estado,
            situacao,
            descricao
        FROM boletins
        WHERE sincronizado_pipedrive = 0
    """)

    registros = cursor.fetchall()

    for linha in registros:
        boletim_id = linha["boletim_id"]
        bidding_id = linha.get("bidding_id")

        if not bidding_id:
            print("Ignorado: bidding_id vazio (boletim_id =", boletim_id, ")")
            continue

        print("\nProcessando bidding_id", bidding_id)

        deal_id = buscar_deal_por_bidding_id(bidding_id)

        if deal_id:
            print("Deal existente - ID", deal_id)
        else:
            criado = criar_deal(linha)
            if not criado.get("success"):
                print("Erro ao criar deal:", criado)
                continue
            deal_id = criado["data"]["id"]
            print("Deal criado - ID", deal_id)

        atualizado = atualizar_deal(deal_id, linha)
        if not atualizado.get("success"):
            print("Erro ao atualizar deal:", atualizado)
            continue

        criar_anotacao(deal_id, linha.get("descricao"))

        marcar_sincronizado(cursor, boletim_id)
        conn.commit()
        print("Registro marcado como sincronizado")

    cursor.close()
    conn.close()


# ---------- EXEC ----------
if __name__ == "__main__":
    importar_mysql()
