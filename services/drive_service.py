import pathlib
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
SHARED_DRIVE_ID = "0ANze95S0dm6BUk9PVA"


def conectar_drive():
    creds = Credentials.from_service_account_file(
        "credentials/google_service_account.json",
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def escapar_texto_query_drive(valor):
    return str(valor).replace("\\", "\\\\").replace("'", "\\'")


def buscar_pasta_por_nome(nome, parent_id):
    service = conectar_drive()
    nome_query = escapar_texto_query_drive(nome)

    query = (
        f"name = '{nome_query}' "
        f"and '{parent_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    arquivos = results.get("files", [])

    if arquivos:
        return arquivos[0]["id"]

    return None


def buscar_arquivo_por_nome(nome, parent_id):
    service = conectar_drive()
    nome_query = escapar_texto_query_drive(nome)

    query = (
        f"name = '{nome_query}' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    arquivos = results.get("files", [])

    if arquivos:
        return arquivos[0]["id"]

    return None


def criar_pasta(nome, parent_id):
    service = conectar_drive()

    pasta_existente = buscar_pasta_por_nome(nome, parent_id)

    if pasta_existente:
        return pasta_existente

    metadata = {
        "name": nome,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id]
    }

    pasta = service.files().create(
        body=metadata,
        fields="id",
        supportsAllDrives=True
    ).execute()

    return pasta.get("id")


def upload_arquivo_para_pasta(caminho_arquivo, pasta_id):
    service = conectar_drive()
    nome_arquivo = pathlib.Path(caminho_arquivo).name
    arquivo_existente = buscar_arquivo_por_nome(nome_arquivo, pasta_id)

    if arquivo_existente:
        print(f"Arquivo ja existe no Drive: {nome_arquivo}")
        return arquivo_existente

    file_metadata = {
        "name": nome_arquivo,
        "parents": [pasta_id]
    }

    max_tentativas = 3

    for tentativa in range(1, max_tentativas + 1):
        try:
            media = MediaFileUpload(
                caminho_arquivo,
                resumable=True
            )

            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True
            )

            response = None

            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Upload {int(status.progress() * 100)}%")

            print(f"Upload concluído: {nome_arquivo}")
            return response.get("id")

        except Exception as e:
            print(f"Tentativa {tentativa}/{max_tentativas} falhou: {type(e).__name__}: {e}")
            if tentativa < max_tentativas:
                time.sleep(5 * tentativa)
            else:
                raise Exception(f"Falha definitiva no upload após {max_tentativas} tentativas: {e}")
