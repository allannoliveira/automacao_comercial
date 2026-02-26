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


def buscar_pasta_por_nome(nome, parent_id):
    service = conectar_drive()

    query = (
        f"name = '{nome}' "
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

    file_metadata = {
        "name": pathlib.Path(caminho_arquivo).name,
        "parents": [pasta_id]
    }

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
    tentativa = 0
    max_tentativas = 3

    while response is None and tentativa < max_tentativas:
        try:
            status, response = request.next_chunk()
        except Exception:
            tentativa += 1
            print(f"Tentativa {tentativa} falhou no upload. Retentando...")
            time.sleep(5)

    if response is None:
        raise Exception("Falha definitiva no upload após 3 tentativas.")

    return response.get("id")