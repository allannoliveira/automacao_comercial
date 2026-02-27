from google import genai
from google.genai import types
import json


# Ordem de fallback: tenta o primeiro, se cota esgotada tenta o próximo
MODELOS_FALLBACK = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
]


def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)


def analisar_edital(caminho_pdf, prompt):
    creds = carregar_credenciais()
    api_key = creds.get("gemini_api_key")

    if not api_key:
        raise Exception("GEMINI API KEY não encontrada no credentials.json")

    client = genai.Client(api_key=api_key)

    with open(caminho_pdf, "rb") as f:
        pdf_bytes = f.read()

    print(f"[GEMINI] Enviando PDF: {caminho_pdf} ({len(pdf_bytes)} bytes)")

    ultimo_erro = None

    for modelo in MODELOS_FALLBACK:
        try:
            print(f"[GEMINI] Tentando modelo: {modelo}")

            response = client.models.generate_content(
                model=modelo,
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

            print(f"[GEMINI] Modelo usado: {modelo} | Resposta: {len(texto)} caracteres")

            texto_upper = texto.upper()

            if "APROVADO" in texto_upper and "REPROVADO" not in texto_upper:
                status = "SIM"
            else:
                status = "NAO"

            print(f"[GEMINI] Status final: {status}")

            return texto, status

        except Exception as e:
            erro_str = str(e)
            # Se for cota esgotada, tenta o próximo modelo
            if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str or "quota" in erro_str.lower():
                print(f"[GEMINI] Cota esgotada no modelo {modelo}, tentando próximo...")
                ultimo_erro = e
                continue
            # Qualquer outro erro propaga imediatamente
            raise

    # Se todos os modelos falharam por cota
    raise Exception(f"Cota esgotada em todos os modelos disponíveis. Último erro: {ultimo_erro}")


# teste somente
if __name__ == "__main__":
    print("Testando conexão com Gemini...")

    try:
        creds = carregar_credenciais()
        api_key = creds.get("gemini_api_key")

        if not api_key:
            raise Exception("gemini_api_key não encontrada no credentials.json")

        client = genai.Client(api_key=api_key)

        for modelo in MODELOS_FALLBACK:
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents="Responda apenas com: OK"
                )
                print(f"Modelo {modelo} OK: {response.text}")
                break
            except Exception as e:
                print(f"Modelo {modelo} falhou: {e}")

    except Exception as e:
        print("Erro:", e)