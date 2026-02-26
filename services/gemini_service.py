# services/gemini_service.py

from google import genai
from google.genai import types
import json


def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)


def analisar_edital(caminho_pdf, prompt):
    """
    Envia um único edital PDF para o Gemini
    e retorna (texto_completo, status_aprovacao)
    """

    try:
        creds = carregar_credenciais()
        api_key = creds.get("gemini_api_key")

        if not api_key:
            raise Exception("GEMINI API KEY não encontrada no credentials.json")

        client = genai.Client(api_key=api_key)

        with open(caminho_pdf, "rb") as f:
            pdf_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf"
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=8192
            )
        )

        texto = response.text or ""

        texto_upper = texto.upper()

        if "DECISÃO FINAL" in texto_upper and "APROVADO" in texto_upper:
            status = "SIM"
        else:
            status = "NAO"

        return texto, status

    except Exception as e:
        print(f"Erro ao analisar edital com Gemini: {e}")
        return None, "ERRO"
    

# texte somente  
if __name__ == "__main__":
    print("Testando conexão com Gemini...")

    try:
        creds = carregar_credenciais()
        api_key = creds.get("gemini_api_key")

        if not api_key:
            raise Exception("gemini_api_key não encontrada no credentials.json")

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Responda apenas com: OK"
        )

        print("Resposta do Gemini:")
        print(response.text)

    except Exception as e:
        print("Erro:", e)
