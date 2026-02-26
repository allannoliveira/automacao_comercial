from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
import os

SCOPES = ["https://www.googleapis.com/auth/drive"]
SHARED_DRIVE_ID = "0ANze95S0dm6BUk9PVA"

def conectar_drive():
    creds = Credentials.from_service_account_file(
        "credentials/google_service_account.json",
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def criar_pasta(nome, parent_id):
    service = conectar_drive()

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

def upload_arquivo_para_pasta(file_path, pasta_id):
    service = conectar_drive()

    metadata = {
        "name": os.path.basename(file_path),
        "parents": [pasta_id]
    }

    media = MediaFileUpload(file_path, resumable=True)

    arquivo = service.files().create(
        body=metadata,
        media_body=media,
        fields="id",
        supportsAllDrives=True
    ).execute()

    return arquivo.get("id")