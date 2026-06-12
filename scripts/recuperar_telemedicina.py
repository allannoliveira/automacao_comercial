"""
Recupera licitações de telemedicina que foram reprovadas indevidamente.
Lê a aba 'reprovados', identifica linhas com keywords de telemedicina,
importa no Pipedrive e move para a aba 'aprovados'.

Uso:
    python -m scripts.recuperar_telemedicina
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

from services.filtro_palavras import licitacao_telemedicina
from inputData.inputDataPipedrive import importar_deal_unico

load_dotenv()

SHEET_ID         = os.getenv("GOOGLE_SHEET_ID")
CREDENTIALS_FILE = "credentials/google_service_account.json"


def _conectar():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds  = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def _ler_aba(spreadsheet, aba):
    sheet = spreadsheet.worksheet(aba)
    rows  = sheet.get_all_values()
    if len(rows) < 2:
        return sheet, [], []
    headers = rows[0]
    dados   = [dict(zip(headers, row)) for row in rows[1:]]
    return sheet, dados, rows


def recuperar():
    print("[RECUPERAR] Conectando à planilha...")
    spreadsheet = _conectar()

    sheet_rep, reprovados, rows_rep = _ler_aba(spreadsheet, "reprovados")
    sheet_apr, aprovados,  _        = _ler_aba(spreadsheet, "aprovados")

    ids_aprovados = {r.get("idconlicitacao", "").strip() for r in aprovados}

    # Linhas para processar (índice na planilha = i + 2, pois row 1 é header)
    candidatos = []
    for i, row in enumerate(reprovados):
        edital = row.get("edital", "")
        itens  = row.get("itens", "")
        descr  = row.get("descricao", "")
        uid    = row.get("idconlicitacao", "").strip()

        if not uid:
            continue

        if uid in ids_aprovados:
            print(f"[SKIP] {uid} já está em aprovados")
            continue

        if licitacao_telemedicina(edital, descr, itens):
            candidatos.append((i + 2, row))  # +2: row 1 = header, i começa em 0

    print(f"[RECUPERAR] {len(candidatos)} licitação(ões) de telemedicina encontrada(s) em reprovados\n")

    if not candidatos:
        print("[RECUPERAR] Nenhuma ação necessária.")
        return

    linhas_para_deletar = []

    for sheet_row_idx, dados in candidatos:
        uid    = dados.get("idconlicitacao", "").strip()
        edital = dados.get("edital", "N/A")
        cidade = dados.get("orgao_cidade", "")
        uf     = dados.get("orgao_estado", "")

        print(f"Processando: {uid} | {edital} | {cidade}/{uf}")

        # Força status aprovado
        dados["aprovado_ia"] = "SIM"
        dados["status_ia"]   = "SIM"

        # Importa no Pipedrive
        try:
            deal_id = importar_deal_unico(dados)
            if deal_id:
                dados["deal_id_pipedrive"]  = deal_id
                dados["importado_pipedrive"] = "TRUE"
                print(f"  -> Pipedrive deal: {deal_id}")
            else:
                print(f"  -> Pipedrive: deal já existia ou falhou")
        except Exception as e:
            print(f"  -> Erro Pipedrive: {type(e).__name__}: {e}")

        # Insere em aprovados
        nova_linha = [
            dados.get("boletim_id", ""),
            dados.get("idconlicitacao", ""),
            dados.get("orgao_cidade", ""),
            dados.get("orgao_estado", ""),
            dados.get("edital", ""),
            dados.get("edital_site", ""),
            dados.get("itens", ""),
            dados.get("descricao", ""),
            dados.get("valor_estimado", ""),
            dados.get("datahora_abertura", ""),
            dados.get("datahora_prazo", ""),
            dados.get("data_coleta", ""),
            "SIM",                                          # aprovado_ia
            dados.get("link_drive_edital", ""),
            dados.get("importado_pipedrive", ""),
            dados.get("resumo_ia", ""),
            dados.get("orgao_nome", ""),
            dados.get("modalidade", ""),
            dados.get("modo_disputa", ""),
            dados.get("classificacao", ""),
            dados.get("feedback_qualitativo", ""),
        ]
        sheet_apr.append_row(nova_linha, value_input_option="USER_ENTERED")
        print(f"  -> Inserido em aprovados")

        linhas_para_deletar.append(sheet_row_idx)

    # Deleta das reprovadas de trás para frente (evita deslocamento de índice)
    for idx in sorted(linhas_para_deletar, reverse=True):
        sheet_rep.delete_rows(idx)
        print(f"  -> Linha {idx} removida de reprovados")

    print(f"\n[RECUPERAR] Concluído. {len(linhas_para_deletar)} licitação(ões) migrada(s).")


if __name__ == "__main__":
    recuperar()
