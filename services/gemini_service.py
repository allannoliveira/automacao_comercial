from google import genai
from google.genai import types
import json
import time
import hashlib
import os

# =========================
# CONFIGURAÇÕES
# =========================

MODELOS_FALLBACK = [
    "gemini-3-flash-preview",  
    "gemini-2.0-flash",
    "gemini-2.5-flash",
]

MAX_OUTPUT_TOKENS = 5000
TEMPO_RETRY = 2  # segundos
MAX_RETRIES = 2

CACHE_DIR = "cache_gemini"


# =========================
# UTILIDADES
# =========================

def carregar_credenciais():
    caminho = os.getenv("GEMINI_CREDENTIALS", "credentials/credentials.json")

    if not os.path.exists(caminho):
        raise Exception(f"Arquivo de credenciais não encontrado: {caminho}")

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def gerar_hash(pdf_bytes):
    return hashlib.md5(pdf_bytes).hexdigest()


def salvar_cache(hash_arquivo, resultado):
    os.makedirs(CACHE_DIR, exist_ok=True)
    caminho = os.path.join(CACHE_DIR, f"{hash_arquivo}.json")

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)


def carregar_cache(hash_arquivo):
    caminho = os.path.join(CACHE_DIR, f"{hash_arquivo}.json")

    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)

    return None


# =========================
# FUNÇÃO PRINCIPAL
# =========================

def analisar_edital(caminho_pdf, prompt):
    creds = carregar_credenciais()
    api_key = creds.get("gemini_api_key")

    if not api_key:
        raise Exception("GEMINI API KEY não encontrada no credentials.json")

    client = genai.Client(api_key=api_key)

    with open(caminho_pdf, "rb") as f:
        pdf_bytes = f.read()

    print(f"[GEMINI] PDF: {caminho_pdf} ({len(pdf_bytes)} bytes)")

    # =========================
    # CACHE
    # =========================
    hash_arquivo = gerar_hash(pdf_bytes)
    cache = carregar_cache(hash_arquivo)

    if cache:
        print("[GEMINI] Cache encontrado, evitando custo 🚀")
        return cache["texto"], cache["status"]

    ultimo_erro = None

    # =========================
    # LOOP DE MODELOS + RETRY
    # =========================
    for modelo in MODELOS_FALLBACK:
        for tentativa in range(MAX_RETRIES):
            try:
                print(f"[GEMINI] Modelo: {modelo} | Tentativa: {tentativa + 1}")

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
                        max_output_tokens=MAX_OUTPUT_TOKENS
                    )
                )

                texto = getattr(response, "text", "") or ""

                if not texto:
                    raise Exception("Resposta vazia do Gemini")

                print(f"[GEMINI] OK | {len(texto)} chars")

                texto_upper = texto.upper()

                if "APROVADO" in texto_upper and "REPROVADO" not in texto_upper:
                    status = "SIM"
                else:
                    status = "NAO"

                print(f"[GEMINI] Status: {status}")

                # =========================
                # SALVAR CACHE
                # =========================
                salvar_cache(hash_arquivo, {
                    "texto": texto,
                    "status": status
                })

                return texto, status

            except Exception as e:
                erro_str = str(e)
                print(f"[ERRO GEMINI] {type(e).__name__}: {erro_str}")

                # Retry antes de fallback
                if tentativa < MAX_RETRIES - 1:
                    time.sleep(TEMPO_RETRY)
                    continue

                # Cota estourada → tenta próximo modelo
                if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str or "quota" in erro_str.lower():
                    print(f"[GEMINI] Cota no modelo {modelo}, tentando próximo...")
                    ultimo_erro = e
                    break

                raise

    raise Exception(f"Cota esgotada em todos os modelos. Último erro: {ultimo_erro}")


# =========================
# TESTE DIRETO
# =========================

if __name__ == "__main__":
    print("Testando Gemini...")

    try:
        creds = carregar_credenciais()
        api_key = creds.get("gemini_api_key")

        if not api_key:
            raise Exception("gemini_api_key não encontrada")

        client = genai.Client(api_key=api_key)

        for modelo in MODELOS_FALLBACK:
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents="Responda apenas com OK"
                )
                print(f"[TESTE] {modelo}: {response.text}")
                break
            except Exception as e:
                print(f"[TESTE] {modelo} falhou: {e}")

    except Exception as e:
        print("[ERRO TESTE]:", e)