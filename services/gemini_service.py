from google import genai
from google.genai import types
import json
import logging
import re
import time
import hashlib
import os

logger = logging.getLogger("gemini_service")

# =========================
# CONFIGURAÇÕES
# =========================

MODELOS_FALLBACK = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


MAX_OUTPUT_TOKENS = 4096
TEMPO_RETRY = 2
MAX_RETRIES = 2

CACHE_DIR = "cache_gemini"

# Preços gemini-2.5-flash (USD por milhão de tokens)
PRECO_INPUT_USD_POR_MILHAO = 0.15
PRECO_OUTPUT_USD_POR_MILHAO = 0.60


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
# CLASSIFICAÇÃO
# =========================

_STATUS_FINAL_RE = re.compile(r"STATUS_FINAL:\s*(APROVADO|REPROVADO)", re.IGNORECASE)


def _classificar_status(texto: str) -> str:
    match = _STATUS_FINAL_RE.search(texto)
    if match:
        return "SIM" if match.group(1).upper() == "APROVADO" else "NAO"

    # Fallback para respostas sem STATUS_FINAL (cache antigo)
    texto_upper = texto.upper()
    if "APROVADO" in texto_upper and "REPROVADO" not in texto_upper:
        return "SIM"
    return "NAO"


# =========================
# FUNÇÃO PRINCIPAL
# =========================

def analisar_edital(caminho_pdf, prompt, min_chars=500):
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
        print("[GEMINI] Cache encontrado, evitando custo")
        tokens_cache = {"prompt_tokens": 0, "output_tokens": 0, "cache_hit": True}
        return cache["texto"], cache["status"], tokens_cache

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

                # Resposta muito curta = provavelmente truncada ou bloqueada pelo modelo
                if min_chars > 0 and len(texto) < min_chars:
                    print(f"[GEMINI] Resposta curta recebida ({len(texto)} chars): {texto[:300]!r}")
                    raise Exception(f"truncamento: resposta com apenas {len(texto)} chars")

                usage = getattr(response, "usage_metadata", None)
                tokens_info = {
                    "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                    "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                    "cache_hit": False
                }

                print(f"[GEMINI] OK | {len(texto)} chars | "
                      f"tokens entrada={tokens_info['prompt_tokens']} "
                      f"saida={tokens_info['output_tokens']}")

                status = _classificar_status(texto)
                print(f"[GEMINI] Status: {status}")

                salvar_cache(hash_arquivo, {"texto": texto, "status": status})

                return texto, status, tokens_info

            except Exception as e:
                erro_str = str(e)
                logger.error(f"[ERRO GEMINI] modelo={modelo} tentativa={tentativa+1} {type(e).__name__}: {erro_str}")
                print(f"[ERRO GEMINI] {type(e).__name__}: {erro_str}")

                # Retry antes de fallback
                if tentativa < MAX_RETRIES - 1:
                    time.sleep(TEMPO_RETRY)
                    continue

                # Modelo indisponível, cota ou resposta truncada → tenta próximo
                _pular = (
                    "429" in erro_str
                    or "503" in erro_str
                    or "UNAVAILABLE" in erro_str
                    or "RESOURCE_EXHAUSTED" in erro_str
                    or "quota" in erro_str.lower()
                    or "404" in erro_str
                    or "NOT_FOUND" in erro_str
                    or "truncamento" in erro_str
                )
                if _pular:
                    logger.warning(f"[GEMINI] Modelo {modelo} indisponível, tentando próximo...")
                    print(f"[GEMINI] Modelo {modelo} indisponível, tentando próximo...")
                    ultimo_erro = e
                    break

                raise

    raise Exception(f"Cota esgotada em todos os modelos. Último erro: {ultimo_erro}")


def tokens_para_custo_usd(prompt_tokens: int, output_tokens: int) -> float:
    return (
        prompt_tokens * PRECO_INPUT_USD_POR_MILHAO / 1_000_000
        + output_tokens * PRECO_OUTPUT_USD_POR_MILHAO / 1_000_000
    )


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
