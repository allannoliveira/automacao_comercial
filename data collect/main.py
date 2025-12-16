import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# ---------------------------
# CARREGAR CREDENCIAIS
# ---------------------------
def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------
# SELECIONAR MÊS ATUAL
# ---------------------------
def selecionar_mes_atual(page):
    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    mes_atual = meses[datetime.now().month - 1]

    print(f"➡ Selecionando mês: {mes_atual}")
    page.get_by_role("button", name=mes_atual).click()


# ---------------------------
# APLICAR FILTRO
# ---------------------------
def aplicar_filtro(page, termo):
    print(f"🎯 Aplicando filtro: {termo}")

    filtro = page.locator("#react-select-3-input")
    filtro.click()
    filtro.fill(termo)

    page.get_by_role("option", name=termo).click()
    print("✔ Filtro aplicado!")


# ---------------------------
# SCRIPT PRINCIPAL
# ---------------------------
def main():
    creds = carregar_credenciais()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # -------------------------------------
        # 1. LOGIN
        # -------------------------------------
        page.goto("https://conlicitacao.com.br/")
        page.get_by_role("link", name="Acessar Conta").click()

        page.wait_for_load_state("networkidle")

        # Preencher credenciais
        page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
        page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
        page.get_by_role("button", name="Acessar").click()

        # Esperar redirecionamento pós-login
        page.wait_for_load_state("networkidle")

        # -------------------------------------
        # 2. FECHAR POPUP E ENTRAR EM BOLETINS
        # -------------------------------------
        try:
            page.get_by_role("button", name="Close").click()
            print("✔ Popup fechado")
        except:
            print("⚠ Popup não apareceu")

        # Agora o menu funciona
        page.get_by_role("link", name="Boletins de Licitações").click()
        page.wait_for_load_state("networkidle")
        print("✔ Entrou em Boletins de Licitações")

        # -------------------------------------
        # 3. SELECIONAR MÊS ATUAL
        # -------------------------------------
        selecionar_mes_atual(page)

        # -------------------------------------
        # 4. APLICAR FILTRO
        # -------------------------------------
        aplicar_filtro(page, "Licitações e Acompanhamentos")

        print("✔ Fluxo totalmente concluído!")

        page.wait_for_timeout(5000)
        browser.close()


if __name__ == "__main__":
    main()
