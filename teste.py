import re
import csv
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')


# =====================================================
# CONFIGURAÇÕES
# =====================================================

LOGIN_URL = "https://conlicitacao.com.br/"
CALENDARIO_URL = "https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins"
BIDDINGS_API = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins/{}/biddings.json"
CSV_OUTPUT = "licitacoes_filtradas.csv"
CHECKPOINT_FILE = "ultimo_boletim.json"  # 🆕 Arquivo de controle

# =====================================================
# PALAVRAS-CHAVE (REGEX) - Versão Otimizada
# =====================================================

PADROES_REGEX = [
    # Consulta
    r"\bconsultas?\b",
    
    # Enfermagem/Enfermeiro
    r"\benfermage[mn]s?\b",
    r"\benfermeiros?\b",
    
    # Equipe + enfermagem
    r"\bequipes?\s+(?:de\s+)?enfermage[mn]s?\b",
    r"\bequipes?\s+(?:para\s+)?enfermage[mn]s?\b",
    
    # Equipe médica
    r"\bequipes?\s+medicas?\b",
    
    # Especialidade médica
    r"\bespecialidades?\s+medicas?\b",
    
    # Gestão enfermagem
    r"\bgest(?:ao|ão|ôes|oes)\s+(?:de\s+)?enfermage[mn]s?\b",
    
    # Gestão médica
    r"\bgest(?:ao|ão|ôes|oes)\s+medicas?\b",
    r"\bgest(?:ao|ão|ôes|oes)\s+medicos?\b",
    
    # Mão de obra enfermagem
    r"\bmaos?\s+(?:de\s+)?obras?\s+(?:de\s+)?enfermage[mn]s?\b",
    
    # Mão de obra médica
    r"\bmaos?\s+(?:de\s+)?obras?\s+medicas?\b",
    
    # Médico
    r"\bmedicos?\b",
    
    # Serviço médico
    r"\bserviços?\s+medic[oa]s?\b",
    
    # Teleatendimento (todas as variações)
    r"\btele\s*atendimentos?\b",
    r"\bteleatendimentos?\b",
    
    # Telemedicina (todas as variações)
    r"\btele\s*medicinas?\b",
    r"\btelemedicinas?\b",
]

# =====================================================
# CONTROLE DE CHECKPOINT
# =====================================================

def carregar_ultimo_boletim():
    """Carrega o ID do último boletim processado"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("ultimo_id", 0)
    return 0

def salvar_ultimo_boletim(boletim_id):
    """Salva o ID do último boletim processado"""
    data = {
        "ultimo_id": boletim_id,
        "data_processamento": datetime.now().isoformat()
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# =====================================================
# CREDENCIAIS
# =====================================================

def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

# =====================================================
# LOGIN COM PLAYWRIGHT
# =====================================================

def criar_sessao_autenticada():
    creds = carregar_credenciais()

    print("Fazendo login automatico...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL)
        page.get_by_role("link", name="Acessar Conta").click()

        page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
        page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
        page.get_by_role("button", name="Acessar").click()

        page.wait_for_timeout(5000)

        cookies = context.cookies()
        browser.close()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://consulteonline.conlicitacao.com.br/",
        "Origin": "https://consulteonline.conlicitacao.com.br",
    })

    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

    print("Sessao autenticada com sucesso")
    return session

# =====================================================
# EXTRAIR IDS DOS BOLETINS (PLAYWRIGHT)
# =====================================================

def extrair_boletins(session):
    """Extrai IDs dos boletins usando Playwright (renderiza JS)"""
    
    print("Extraindo boletins com Playwright...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # Adicionar os cookies da sessão autenticada
        cookies_playwright = []
        for name, value in session.cookies.items():
            cookies_playwright.append({
                "name": name,
                "value": value,
                "domain": ".conlicitacao.com.br",
                "path": "/"
            })
        context.add_cookies(cookies_playwright)
        
        page = context.new_page()
        page.goto(CALENDARIO_URL)
        
        # Aguardar o conteúdo carregar
        page.wait_for_timeout(5000)
        
        # 🆕 Extrair estrutura do calendário (dias e boletins)
        html_content = page.content()
        browser.close()
    
    # Parsear HTML para extrair datas e boletins
    soup = BeautifulSoup(html_content, "html.parser")
    
    boletins_com_data = []
    
    # Procurar por elementos que contêm as datas (ajuste o seletor conforme necessário)
    # Vamos tentar encontrar padrões comuns de calendário
    
    # Opção 1: Procurar por estrutura de tabela/grid de calendário
    dias = soup.find_all(['div', 'td', 'li'], class_=re.compile(r'(day|dia|date|calendario)', re.I))
    
    if not dias:
        # Opção 2: Procurar por qualquer elemento que contenha links de boletins
        dias = soup.find_all(['div', 'section', 'article'])
    
    for dia in dias:
        # Tentar extrair a data do elemento ou elementos próximos
        data_texto = dia.get_text(strip=True)
        
        # Procurar links de boletins dentro deste dia
        links = dia.find_all('a', href=re.compile(r'/boletins/\d+'))
        
        for link in links:
            href = link.get('href')
            if href:
                partes = href.rstrip("/").split("/")
                if partes[-1].isdigit():
                    boletim_id = int(partes[-1])
                    boletim_texto = link.get_text(strip=True)
                    
                    boletins_com_data.append({
                        'id': boletim_id,
                        'data': data_texto[:50],  # Limitar tamanho
                        'texto': boletim_texto
                    })
    
    # Se não encontrou nada estruturado, fazer extração simples
    if not boletins_com_data:
        print("⚠️  Não foi possível extrair datas. Coletando apenas IDs...")
        links = soup.find_all('a', href=re.compile(r'/boletins/\d+'))
        boletins = set()
        for link in links:
            href = link.get('href')
            if href:
                partes = href.rstrip("/").split("/")
                if partes[-1].isdigit():
                    boletins.add(int(partes[-1]))
        
        print(f"{len(boletins)} boletins encontrados no calendario")
        return sorted(boletins), {}
    
    # Remover duplicatas mantendo a primeira ocorrência
    boletins_unicos = {}
    for item in boletins_com_data:
        if item['id'] not in boletins_unicos:
            boletins_unicos[item['id']] = item
    
    # Criar mapa de ID -> data
    mapa_datas = {b['id']: b['data'] for b in boletins_unicos.values()}
    
    print(f"\n📅 CALENDÁRIO DE BOLETINS:")
    print("=" * 60)
    
    # Agrupar por data para exibição
    datas_agrupadas = {}
    for bid, data in mapa_datas.items():
        if data not in datas_agrupadas:
            datas_agrupadas[data] = []
        datas_agrupadas[data].append(bid)
    
    for data, ids in sorted(datas_agrupadas.items()):
        print(f"\n📆 {data}")
        for bid in sorted(ids):
            print(f"   → Boletim {bid}")
    
    print("=" * 60)
    print(f"\n{len(boletins_unicos)} boletins encontrados no calendario\n")
    
    return sorted(boletins_unicos.keys()), mapa_datas

# =====================================================
# FILTRO REGEX
# =====================================================

def bate_regex(texto):
    """
    Verifica se o texto contém alguma das palavras-chave.
    Normaliza o texto para facilitar a busca (remove acentos e converte para minúsculas).
    """
    if not texto:
        return False
    
    # Normalizar texto: minúsculas e remover alguns acentos comuns
    texto = texto.lower()
    
    # Substituir variações de acentuação
    texto = texto.replace('ã', 'a').replace('õ', 'o').replace('ô', 'o')
    texto = texto.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    texto = texto.replace('ó', 'o').replace('ú', 'u').replace('ç', 'c')
    
    # Testar cada padrão
    for padrao in PADROES_REGEX:
        if re.search(padrao, texto, re.IGNORECASE):
            return True
    
    return False

# =====================================================
# COLETAR LICITAÇÕES
# =====================================================

def coletar_licitacoes(session, boletins):
    resultados = []

    for idx, boletim_id in enumerate(boletins, start=1):
        print(f"Processando boletim {idx}/{len(boletins)} -> ID {boletim_id}")

        try:
            resp = session.get(
                BIDDINGS_API.format(boletim_id),
                params={"page": 1, "per_page": 50},
                timeout=30
            )

            if resp.status_code != 200:
                print(f"  ⚠️  Status {resp.status_code} - pulando")
                continue

            payload = resp.json()
            biddings = payload.get("biddings", [])

            for item in biddings:
                texto = (
                    str(item.get("objeto", "")) + " " +
                    str(item.get("itens", ""))
                )

                if bate_regex(texto):
                    # 🆕 Extrair data de abertura
                    data_abertura = item.get("data_abertura") or item.get("data_realizacao") or ""
                    
                    # 🆕 Extrair valor estimado
                    valor_estimado = item.get("valor_estimado") or item.get("valor") or ""
                    
                    # Formatar valor se for número
                    if isinstance(valor_estimado, (int, float)):
                        valor_estimado = f"R$ {valor_estimado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    
                    resultados.append({
                        "boletim_id": boletim_id,
                        "bidding_id": item.get("bidding_id"),
                        "edital": item.get("edital"),
                        "data_abertura": data_abertura,  # 🆕
                        "valor_estimado": valor_estimado,  # 🆕
                        "cidade": item.get("orgao_cidade"),
                        "estado": item.get("orgao_estado"),
                        "descricao": texto.replace("\n", " ")
                    })

        except Exception as e:
            print(f"  ❌ Erro ao processar boletim {boletim_id}: {e}")
            continue

    return resultados

# =====================================================
# MAIN
# =====================================================

def main():
    # 🆕 Carregar último boletim processado
    ultimo_id = carregar_ultimo_boletim()
    
    if ultimo_id > 0:
        print(f" Último boletim processado: {ultimo_id}")
        print(" Buscando apenas boletins novos...\n")
    else:
        print(" Primeira execução - processando todos os boletins\n")
    
    session = criar_sessao_autenticada()
    todos_boletins, mapa_datas = extrair_boletins(session)

    if not todos_boletins:
        print("Nenhum boletim encontrado")
        return

    # 🆕 Filtrar apenas boletins novos (ID maior que o último processado)
    boletins_novos = [b for b in todos_boletins if b > ultimo_id]
    
    if not boletins_novos:
        print(f" Nenhum boletim novo encontrado. Última coleta: ID {ultimo_id}")
        return
    
    print(f"\n {len(boletins_novos)} boletins novos para processar")
    print(f"   (IDs: {boletins_novos[0]} até {boletins_novos[-1]})")
    
    # 🆕 Mostrar quais datas serão processadas
    if mapa_datas:
        print("\n Datas dos boletins novos:")
        for bid in boletins_novos[:5]:  # Mostrar os 5 primeiros
            data = mapa_datas.get(bid, "Data não disponível")
            print(f"   → Boletim {bid}: {data}")
        if len(boletins_novos) > 5:
            print(f"   ... e mais {len(boletins_novos) - 5} boletins")
    
    print()

    resultados = coletar_licitacoes(session, boletins_novos)

    if not resultados:
        print("\n  Nenhuma licitacao filtrada encontrada nos novos boletins")
        # 🆕 Mesmo sem resultados, atualiza o checkpoint
        salvar_ultimo_boletim(boletins_novos[-1])
        return

    # 🆕 Verificar se o arquivo CSV já existe (append ou criar novo)
    arquivo_existe = os.path.exists(CSV_OUTPUT)
    modo = "a" if arquivo_existe else "w"
    
    with open(CSV_OUTPUT, modo, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=resultados[0].keys())
        
        # Escrever cabeçalho apenas se for arquivo novo
        if not arquivo_existe:
            writer.writeheader()
        
        writer.writerows(resultados)

    # 🆕 Salvar o ID do último boletim processado
    ultimo_processado = boletins_novos[-1]
    salvar_ultimo_boletim(ultimo_processado)

    print(f"\n Finalizado!")
    print(f"    {len(resultados)} novos registros salvos em {CSV_OUTPUT}")
    print(f"    Último boletim processado: {ultimo_processado}")
    print(f"    Checkpoint salvo em {CHECKPOINT_FILE}")

# =====================================================

if __name__ == "__main__":
    main()