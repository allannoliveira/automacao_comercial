import time
from services.gemini_service import analisar_edital


class GeminiQueue:

    def __init__(self, delay=10, max_retries=3):
        self.delay = delay
        self.max_retries = max_retries

    def processar(self, pdf_path, prompt):

        tentativa = 0

        while tentativa < self.max_retries:
            try:
                texto, status = analisar_edital(pdf_path, prompt)

                time.sleep(self.delay)

                return texto, status

            except Exception as e:
                tentativa += 1
                espera = 5 * tentativa
                print(f"[GEMINI QUEUE] Erro na tentativa {tentativa}/{self.max_retries}: {type(e).__name__}: {e}")
                print(f"[GEMINI QUEUE] Aguardando {espera}s...")
                time.sleep(espera)

        print(f"[GEMINI QUEUE] Todas as tentativas falharam para: {pdf_path}")
        return "", "ERRO"