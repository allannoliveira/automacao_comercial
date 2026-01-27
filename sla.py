"""
Script de teste para debugar extração de data_abertura
Use este script para testar com um bidding_id específico
"""
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import json

# Coloque aqui o bidding_id que você quer testar
BIDDING_ID_TESTE = "18519610"  # Exemplo do seu CSV
BOLETIM_DETAIL_URL = "https://consultaonline.conlicitacao.com.br/boletim_web/public/biddings/{}"

def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

def testar_extracao():
    creds = carregar_credenciais()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False para você ver o navegador
        context = browser.new_context()
        page = context.new_page()

        # Login
        print("=== FAZENDO LOGIN ===")
        page.goto("https://conlicitacao.com.br/", wait_until="networkidle")
        page.get_by_role("link", name="Acessar Conta").click()
        page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
        page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
        page.get_by_role("button", name="Acessar").click()
        page.wait_for_timeout(8000)
        
        # Acessa a página de detalhes
        print(f"\n=== ACESSANDO BIDDING {BIDDING_ID_TESTE} ===")
        page.goto(BOLETIM_DETAIL_URL.format(BIDDING_ID_TESTE), wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # Salva o HTML completo para análise
        html_content = page.content()
        with open(f"debug_bidding_{BIDDING_ID_TESTE}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✓ HTML salvo em: debug_bidding_{BIDDING_ID_TESTE}.html")
        
        # Analisa o conteúdo
        soup = BeautifulSoup(html_content, "html.parser")
        texto_completo = soup.get_text(" ", strip=True)
        
        # Salva o texto extraído
        with open(f"debug_bidding_{BIDDING_ID_TESTE}_texto.txt", "w", encoding="utf-8") as f:
            f.write(texto_completo)
        print(f"✓ Texto salvo em: debug_bidding_{BIDDING_ID_TESTE}_texto.txt")
        
        print("\n=== BUSCANDO DATA DE ABERTURA ===")
        
        # Tenta vários padrões
        padroes = [
            (r"(?:DATA\s+DE\s+)?ABERTURA\s*:?\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)", "ABERTURA com label"),
            (r"DATA\s*:?\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)", "DATA genérica"),
            (r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}(?::\d{2})?)", "Qualquer data com hora"),
        ]
        
        encontrou = False
        for padrao, descricao in padroes:
            matches = re.finditer(padrao, texto_completo, re.IGNORECASE)
            matches_list = list(matches)
            if matches_list:
                print(f"\n✓ Padrão '{descricao}' encontrou {len(matches_list)} ocorrência(s):")
                for i, match in enumerate(matches_list, 1):
                    print(f"   {i}. {match.group(1)}")
                    # Mostra o contexto ao redor
                    start = max(0, match.start() - 50)
                    end = min(len(texto_completo), match.end() + 50)
                    contexto = texto_completo[start:end]
                    print(f"      Contexto: ...{contexto}...")
                encontrou = True
        
        if not encontrou:
            print("\n✗ NENHUMA DATA ENCONTRADA com os padrões!")
            print("\nPrimeiros 1000 caracteres do texto:")
            print(texto_completo[:1000])
        
        print("\n=== BUSCANDO PRAZO ===")
        padroes_prazo = [
            (r"PRAZO(?:\s+FINAL)?\s*:?\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)", "PRAZO com label"),
            (r"(?:ENCERRAMENTO|TÉRMINO)\s*:?\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)", "Encerramento"),
        ]
        
        encontrou_prazo = False
        for padrao, descricao in padroes_prazo:
            matches = re.finditer(padrao, texto_completo, re.IGNORECASE)
            matches_list = list(matches)
            if matches_list:
                print(f"\n✓ Padrão '{descricao}' encontrou {len(matches_list)} ocorrência(s):")
                for i, match in enumerate(matches_list, 1):
                    print(f"   {i}. {match.group(1)}")
                encontrou_prazo = True
        
        if not encontrou_prazo:
            print("\n✗ NENHUM PRAZO ENCONTRADO")
        
        # Procura também por elementos específicos no HTML
        print("\n=== BUSCANDO ELEMENTOS HTML COM CLASSES/IDS RELEVANTES ===")
        elementos_interesse = soup.find_all(['div', 'span', 'p', 'td', 'th'], 
                                           attrs={'class': re.compile(r'data|date|abertura|prazo', re.I)})
        
        if elementos_interesse:
            print(f"Encontrados {len(elementos_interesse)} elementos:")
            for elem in elementos_interesse[:10]:  # Mostra só os 10 primeiros
                print(f"  - Tag: {elem.name}, Class: {elem.get('class')}, Texto: {elem.get_text(strip=True)[:100]}")
        
        input("\nPressione ENTER para fechar o navegador...")
        browser.close()

if __name__ == "__main__":
    print("=" * 70)
    print("TESTE DE EXTRAÇÃO DE DATA_ABERTURA")
    print("=" * 70)
    print(f"\nTestando bidding_id: {BIDDING_ID_TESTE}")
    print("O navegador abrirá e você poderá ver o que está acontecendo.")
    print("\nOs arquivos HTML e texto serão salvos para análise.")
    print("-" * 70)
    
    testar_extracao()
    
    print("\n" + "=" * 70)
    print("Teste concluído!")
    print("Verifique os arquivos gerados:")
    print(f"  - debug_bidding_{BIDDING_ID_TESTE}.html")
    print(f"  - debug_bidding_{BIDDING_ID_TESTE}_texto.txt")
    print("=" * 70)