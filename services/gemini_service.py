# services/gemini_service.py

import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def analisar_edital(caminho_pdf, prompt):
    model = genai.GenerativeModel("gemini-1.5-pro")

    with open(caminho_pdf, "rb") as f:
        pdf_bytes = f.read()

    response = model.generate_content(
        [
            prompt,
            {
                "mime_type": "application/pdf",
                "data": pdf_bytes
            }
        ],
        generation_config={
            "temperature": 0.0,
            "max_output_tokens": 8192
        }
    )

    texto = response.text

    if "APROVADO" in texto.upper():
        status = "SIM"
    else:
        status = "NAO"

    return texto, status
