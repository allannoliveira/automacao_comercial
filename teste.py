import re
import csv
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# =====================================================
# CARREGAR CREDENCIAIS
# =====================================================

def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

# =====================================================
# URLS
# =====================================================

LOGIN_URL = "https://conlicitacao.com.br/"
BOLETINS_URL = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins.json"
BOLETIM_CONTEUDO_URL = "https://consultaonline.conlicitacao.com.br/boletim_web/bulletin_filter_content"

# =====================================================
# PADROES REGEX
# =====================================================

PADROES_REGEX = [
    r"consulta[s]?",
    r"enfermage(m|ns)",
    r"enfermeiro[s]?",
    r"equipe[s]?\s*&\s*enfermagem[s]?",
    r"equipe[s]?\s*de\s*enfermage(m|ns)",
    r"equipe[s]?\s*para\s*enfermage(m|ns)",
    r"equipe[s]?\s*medica[s]?",
    r"especialidade[s]?\s*medica[s]?",
    r"gest(ao|ão|ões|ôes)\s*enfermage(m|ns)",
    r"gest(ao|ão|ões|ôes)\s*medica[s]?",
    r"gest(ao|ão|ões|ôes)\s*medico[s]?",
    r"mao[s]?\s*de\s*obra[s]?\s*enfermage(m|ns)",
    r"mao[s]?\s*obra[s]?\s*enfermage(m|ns)",
    r"mao[s]?\s*de\s*obra[s]?\s*medica[s]?",
    r"medico[s]?",
    r"serviço[s]?\s*medic(o|a)[s]?",
    r"serviço[s]?\s*medico[s]?",
    r"tele\s*atendimento[s]?",
    r"teleatendimento[s]?",
    r"tele\s*medicina[s]?",
    r"telemedicina[s]?",
]

# =====================================================
# LOGIN AUTOMATICO (PLAYWRIGHT)
# =====================================================

def criar_sessao_autenticada():
    creds = carregar_credenciais()
    email = creds["email"]
    password = creds["password"]

    print("Fazendo login automatico...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Abrir site
        page.goto(LOGIN_URL)
        page.wait_for_load_state("domcontentloaded")

        # 2. Abrir formulário de login
        page.get_by_role("link", name="Acessar Conta").click()

        # 3. Esperar inputs reais do formulário
        page.get_by_role("textbox", name="Seu e-mail").wait_for(timeout=30000)
        page.get_by_role("textbox", name="Sua senha").wait_for(timeout=30000)

        # 4. Preencher credenciais
        page.get_by_role("textbox", name="Seu e-mail").fill(email)
        page.get_by_role("textbox", name="Sua senha").fill(password)

        # 5. Enviar login
        page.get_by_role("button", name="Acessar").click()

        # 6. Aguardar login finalizar (SPA)
        page.wait_for_timeout(5000)

        # 7. Capturar cookies autenticados
        cookies = context.cookies()
        browser.close()

    # Criar sessao requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://consulteonline.conlicitacao.com.br/",
    })

    for c in cookies:
        session.cookies.set(
            name=c["name"],
            value=c["value"],
            domain=c.get("domain"),
            path=c.get("path", "/")
        )

    print("Sessao autenticada com sucesso")
    return session

# =====================================================
# SCRAPER
# =====================================================

def bate_regex(texto):
    texto = texto.lower()
    return any(re.search(p, texto) for p in PADROES_REGEX)

def extrair_licitacoes(html):
    soup = BeautifulSoup(html, "html.parser")
    itens = []

    for i in soup.select(".bulletinItem"):
        itens.append({
            "titulo": i.select_one(".bulletinTitle") and i.select_one(".bulletinTitle").get_text(strip=True),
            "orgao": i.select_one(".bulletinAgency") and i.select_one(".bulletinAgency").get_text(strip=True),
            "objeto": i.select_one(".bulletinObject") and i.select_one(".bulletinObject").get_text(strip=True),
        })

    return itens

# =====================================================
# EXECUCAO PRINCIPAL
# =====================================================

def main():
    session = criar_sessao_autenticada()
    resultados = []

    boletins = session.get(BOLETINS_URL).json()

    for dia in boletins:
        for b in dia["boletins"]:
            html = session.get(
                BOLETIM_CONTEUDO_URL,
                params={"bulletin_filter_id": b["id"]}
            ).text

            licitacoes = extrair_licitacoes(html)

            for lic in licitacoes:
                texto = f"{lic['titulo']} {lic['orgao']} {lic['objeto']}"
                if bate_regex(texto):
                    resultados.append({
                        "data": dia["date"],
                        "boletim": b["name"],
                        "titulo": lic["titulo"],
                        "orgao": lic["orgao"],
                        "objeto": lic["objeto"],
                    })

    with open("licitacoes_filtradas.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["data", "boletim", "titulo", "orgao", "objeto"]
        )
        writer.writeheader()
        writer.writerows(resultados)

    print(f"Finalizado. {len(resultados)} registros salvos em licitacoes_filtradas.csv")

if __name__ == "__main__":
    main()
