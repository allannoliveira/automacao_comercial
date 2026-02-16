# services/drive_service.py

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
import os

SCOPES = ["https://www.googleapis.com/auth/drive"]

def conectar_drive():
    creds = Credentials.from_service_account_file(
        "credentials/google_service_account.json",
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def criar_pasta_drive(nome_pasta, parent_id=None):
    service = conectar_drive()

    file_metadata = {
        "name": nome_pasta,
        "mimeType": "application/vnd.google-apps.folder"
    }

    if parent_id:
        file_metadata["parents"] = [parent_id]

    pasta = service.files().create(body=file_metadata, fields="id").execute()

    return pasta.get("id")

def upload_arquivo_para_pasta(file_path, pasta_id):
    service = conectar_drive()

    file_metadata = {
        "name": os.path.basename(file_path),
        "parents": [pasta_id]
    }

    media = MediaFileUpload(file_path, resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    return file.get("id")
