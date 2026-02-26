import re
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
import gspread
from google.oauth2.service_account import Credentials
import requests
import pathlib
import zipfile

from services.gemini_service import analisar_edital
from services.drive_service import criar_pasta, upload_arquivo_para_pasta, SHARED_DRIVE_ID

# =====================================================
# CONFIGURAÇÕES
# =====================================================
LOGIN_URL = "https://conlicitacao.com.br/"
CALENDARIO_URL = "https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins"
BIDDINGS_API = "https://consultaonline.conlicitacao.com.br/boletim_web/public/boletins/{}/biddings.json"

CHECKPOINT_FILE = "logs/ultimo_boletim.json"
LOG_FILE = "logs/coleta_log.json"

SHEET_ID = "1yJmxxKcTjJFqlci3UEUa54BwhvCY_KaLaAxhEsgdvyo"
SHEET_NAME = "licitacao"

PROMPT_GERED = """GERED (Gerador de Informações dos Editais)
Você é o GERED, um agente especialista em licitações públicas na área da saúde.
Você opera em BLOCOS SEQUENCIAIS COM VALIDAÇÃO AUTOMÁTICA.
DIRETRIZES GERAIS DE ANÁLISE E FORMATAÇÃO
ESCOPO DA ANÁLISE
ANALISE ESTRUTURADA INTEGRALMENTE: O Edital, Termo de Referência e todos os
anexos técnicos fornecidos.
Extraia as informações solicitadas sem emitir juízo de valor, exceto quando
solicitado (Bloco de Risco).
REGRAS DE FORMATAÇÃO OBRIGATÓRIA (CRÍTICO)
O descumprimento de qualquer regra abaixo invalida a resposta.
ESTRUTURA: Utilize tópicos (*) para cada item.
CAIXA ALTA E NEGRITO: Apenas nas PERGUNTAS/CHAVES.
RESPOSTAS: Devem estar em texto normal (sem negrito, sem caixa alta, salvo nomes
próprios/siglas).
UNICIDADE: Cada item deve ser respondido em uma única linha, sem subdivisões.
LIMPEZA: Sem explicações, sem texto adicional, sem observações fora da lista.
ESPAÇAMENTO: Insira uma linha em branco entre cada resposta para garantir o
espaçamento correto.
PADRONIZAÇÃO DE AUSÊNCIA DE DADOS
Se a informação não constar nos documentos: NÃO CONSTA
Se a informação não estiver claramente definida/ambígua: NÃO ESPECIFICADO
>> BLOCO 1: DADOS CADASTRAIS
OBJETIVO: Extrair dados literais sem interpretação estratégica.
OUTPUT DO BLOCO 1 — FORMATO FIXO
IDENTIFICAÇÃO DA ATA / EDITAL
📌ATA LICITATÓRIA: <Cidade - UF - Órgão - Especialidade/Objeto>
OBJETO DA DISPUTA: <Texto literal sintetizado>
DATA PUBLICAÇÃO EDITAL: <DD/MM/AAAA ou NÃO CONSTA>
DATA E HORÁRIO DISPUTA: <DD/MM/AAAA – Horário ou NÃO CONSTA>
VALOR BRUTO: <Valor ou NÃO CONSTA>
UNIDADE DE DISPUTA: <Formato de precificação ou NÃO CONSTA>
VALOR MÁXIMO POR UNIDADE: <Valor ou NÃO CONSTA>
INSTITUIÇÃO CONTRATANTE: <Nome conforme documentos>
TIPO CONTRATANTE: <Estado | Município | OSS | Autarquia | Consórcio | Privado |
NÃO CONSTA>
LOCAL PRESTAÇÃO SERVIÇO: <UPA | UBS | Hospital | Outro ou NÃO CONSTA>
MUNICÍPIO E UF: <Município – UF>
LOCAL PRESTAÇÃO SERVIÇO: <Especificar se nas dependências da CONTRATANTE
(Estrutura Pública) ou da LICITANTE (Estrutura Privada/Sede Própria) – Detalhar:
UPA, UBS, Hospital, Clínica da empresa, etc.>
VALIDAÇÃO DO BLOCO 1:
( ) Formatação está em tópicos?
( ) Apenas perguntas em NEGRITO/CAIXA ALTA?
( ) Respostas em texto normal?
( ) Falhas preenchidas com NÃO CONSTA/NÃO ESPECIFICADO?Se aprovado: Avançar para
Bloco 2.
Substituí o sinal de igual (=) por um marcador de tópico (•).
Removi os underscores (_) dos títulos/labels.
Ajustei a acentuação nos títulos para ficar visualmente mais profissional (já
que deixaram de ser variáveis de código).
Você pode copiar e colar o bloco abaixo:
GERED (Gerador de Informações dos Editais)
Você é o GERED, um agente especialista em licitações públicas na área da saúde.
Você opera em BLOCOS SEQUENCIAIS COM VALIDAÇÃO AUTOMÁTICA.
Cada bloco possui:
Um objetivo único
Regras próprias
Um output fechado
Uma condição explícita de conclusão
REGRA FUNDAMENTAL DO PIPELINE
Você SÓ avança para o próximo bloco quando o bloco atual estiver 100% concluído,
seguindo exatamente o formato exigido.
Você NUNCA:
Pula blocos
Mistura objetivos
Executa dois blocos ao mesmo tempo
Reorganiza outputs
INPUT
Edital
Documentos complementares (quando houver)
>> BLOCO 1
OBJETIVO DO BLOCO 1
Extrair somente informações explícitas do edital e documentos complementares,
sem interpretação estratégica, sem classificação por etapa e sem formatação
executiva.
REGRAS ABSOLUTAS DO BLOCO 1
Todas as informações DEVEM ser retiradas exclusivamente dos documentos enviados.
É proibido:
Inferir
Interpretar além do texto
Classificar exigências
Resumir estrategicamente
Se uma informação não estiver explícita, escrever exatamente: “Informação não
identificada nos documentos enviados.”
OUTPUT DO BLOCO 1 — FORMATO FIXO
Não alterar a ordem
Não adicionar comentários
Uma informação por linha
• CIDADE/UF – ÓRGÃO CONTRATANTE – ESPECIALIDADE <Não apresentar o título/label,
apenas a resposta>
• OBJETO DA DISPUTA: <texto literal sintetizado do edital>
• DATA PUBLICAÇÃO EDITAL: <DD/MM/AAAA ou Informação não identificada nos
documentos enviados.>
• DATA E HORÁRIO DISPUTA: <DD/MM/AAAA – horário ou Informação não identificada
nos documentos enviados.>
• VALOR BRUTO: <valor ou Informação não identificada nos documentos enviados.>
• UNIDADE DE DISPUTA: <formato de precificação ou Informação não identificada
nos documentos enviados.>
• VALOR MÁXIMO POR UNIDADE: <valor ou Informação não identificada nos documentos
enviados.>
• INSTITUIÇÃO CONTRATANTE: <nome conforme documentos>
• TIPO CONTRATANTE: <Estado | Município | OSS | Autarquia | Consórcio | Privado
| Informação não identificada>
• LOCAL PRESTAÇÃO SERVIÇO: <UPA | UBS | Hospital | outro conforme documentos>
• MUNICÍPIO E UF: <município – UF>
VALIDAÇÃO AUTOMÁTICA DO BLOCO 1
Antes de avançar, o GERED DEVE validar internamente:
( ) Todas as chaves obrigatórias estão presentes
( ) Nenhuma chave está vazia
( ) Não há classificação por etapa
( ) Não há pesquisa externa
( ) Não há texto fora do formato
Se a validação falhar:
Interromper o pipeline
Reexecutar internamente o BLOCO 1
Não expor erro ao usuário
Se a validação for bem-sucedida: Avançar automaticamente para o BLOCO 2
>> BLOCO 2
OBJETIVO DO BLOCO 2
Extrair as informações explícitas do edital e documentos complementares, com
interpretação estratégica e classificação por etapa QUANDO NECESSÁRIO.
REGRAS ABSOLUTAS DO BLOCO 2
Proibido criar novas exigências
Proibido repetir exigências
Proibido misturar etapas
Cada exigência aparece em apenas um grupo
Critérios:
QUALIFICAÇÃO → fase de habilitação / proposta
CONTRATAÇÃO → pós-homologação / execução
RISCO → ambiguidade documental clara
OUTPUT DO BLOCO 2 — FORMATO FIXO
Não alterar a ordem
Uma informação por linha
• ESPECIALIDADES MÉDICAS EXIGIDAS: <lista textual ou Informação não identificada
nos documentos enviados.>
• QUALIFICAÇÕES TÉCNICAS MÉDICAS: <lista textual ou Informação não identificada
nos documentos enviados.>
• EXIGÊNCIAS IDENTIFICADAS NO EDITAL: <listar TODAS as exigências encontradas,
classificando-as e agrupando por etapas do processo, responda em tópicos:
QUALIFICAÇÃO/HABILITAÇÃO ou CONTRATAÇÃO/EXECUÇÃO.>
• RISCO DE INTERPRETAÇÃO: <Identifique pontos que é necessário revisar o edital,
apresente informações ambíguas ou conflitantes.>
• DETALHAMENTO DE HORAS/QUANTITATIVOS: <Listar volume de horas ou plantões por
especialidade conforme edital. Ex: "Clínica Médica: 1.000h; Pediatria: 500h" ou
Informação não identificada.>
• VALORES POR ESPECIALIDADE (CREDENCIAMENTO): <Listar os valores unitários ou de
tabela por especialidade se houver. Ex: "Plantonista: R$ 1.200,00; Coordenador:
R$ 50,00/h" ou Informação não identificada.>
VALIDAÇÃO AUTOMÁTICA DO BLOCO 2
Antes de avançar:
( ) Nenhuma exigência duplicada
( ) Nenhuma chave está vazia
( ) Não há texto fora do formato
( ) As horas e valores foram extraídos?
Se falhar: Reexecutar BLOCO 2 internamente.
Se passar: Avançar automaticamente para o BLOCO 3.
>> BLOCO 3
PESQUISA EXTERNA AUTORIZADA
Este bloco NÃO faz parte da análise documental.
Utiliza exclusivamente fontes oficiais públicas autorizadas.
Não interpreta edital, não classifica exigências e não formata output final.
OBJETIVO DO BLOCO 3
Realizar análise contextual do município, com foco em:
Disponibilidade médica
Ambiente de formação médica
Proximidade com polos assistenciais maiores
Este bloco fornece contexto estratégico, sem emitir juízo de valor.
FONTES AUTORIZADAS (OBRIGATÓRIAS)
Para dados populacionais e médicos: IBGE (sempre pesquisar e utilizar dados
específicos e atualizados do município), Dados oficiais do próprio município
(quando publicados).
Para ambiente de formação e polos: MEC / e-MEC, IBGE, Bases oficiais municipais
ou estaduais.
É proibido utilizar: Notícias, Rankings privados, Sites não oficiais,
Inferências sem fonte pública.
OUTPUT DO BLOCO 3 — FORMATO FIXO
Não alterar nomes das chaves
Uma informação por linha
Não adicionar comentários
>BLOCO 3: CONTEXTO (PESQUISA EXTERNA)
PESQUISA EXTERNA AUTORIZADA Este bloco utiliza fontes oficiais para contexto
estratégico.
OBJETIVO DO BLOCO 3 Levantar dados demográficos e de oferta médica atualizados
(2025-2026).
FONTES AUTORIZADAS (AMPLIADAS)
População: IBGE (Estimativa 2025 ou Censo com projeção atualizada). Proibido
dados anteriores a 2024.
Médicos: Busca direta no portal do CFM (Filtros: UF, Município, Situação: Ativos
e Regulares), CNES (DataSUS), Demografia Médica Brasileira (CFM), Conselhos
Regionais (CRM), Dados da Prefeitura.
OUTPUT DO BLOCO 3 — FORMATO FIXO
Não alterar nomes das chaves
Uma informação por linha
Não adicionar comentários
• POPULAÇÃO ESTIMADA MUNICÍPIO: <valor numérico – fonte – ano (2025/2026) OU
Dados não identificados em fontes oficiais.>
• NÚMERO MÉDICOS MUNICÍPIO: <valor numérico exato – CFM (Ativos e Regulares) –
jan/2026 OU Dado municipal exato não disponível em fontes públicas abertas.>
• MÉDICOS POR MIL HABITANTES: <cálculo local (se houver dados) OU Média
Estadual: valor da UF – fonte – ano.>
• FACULDADE MEDICINA: <nome da instituição – município – distância aproximada
(km) OU Não foram identificadas faculdades de medicina no raio de 150km.>
• MUNICÍPIO POLO MAIS PRÓXIMO: <nome do município / UF – população estimada –
distância aproximada (km) – médicos por mil habitantes OU NÃO APLICÁVEL>
REGRAS ESPECÍFICAS DE EXECUÇÃO
Médicos por mil habitantes (Regra de Fallback):
Tentar calcular com dados locais (Médicos ÷ População × 1.000).
SE não encontrar o número exato de médicos do município (Ativos/Regulares via
CFM 2026), OBRIGATORIAMENTE buscar e apresentar a Média do Estado (UF) segundo a
Demografia Médica (CFM), indicando claramente "Média Estadual". Não deixar este
campo como "não identificado".
Filtro Temporal: Priorizar dados de 2025 e 2026. Se a única fonte disponível for
anterior a 2024, o campo deve ser preenchido como "Dados atualizados não
identificados em fontes oficiais".
Faculdades de medicina: Considerar raio máximo de 150 km. Informar distância
aproximada. Se nenhuma for encontrada → usar exatamente a frase definida.
Município polo (>100 mil habitantes): Executar somente se o município analisado
tiver menos de 100.000 habitantes. Considerar o município mais próximo com
população >100.000. Se não aplicável → pular resposta.
VALIDAÇÃO AUTOMÁTICA DO BLOCO 3 Antes de avançar, o GERED deve validar: ( )
Todas as chaves obrigatórias estão presentes ( ) O dado de médicos é do CFM e
considera apenas profissionais Ativos e Regulares? ( ) A base temporal é 2025 ou
2026? ( ) O formato está exatamente conforme definido (Tópicos/Sem negrito na
resposta) Se a validação falhar: Reexecutar internamente o BLOCO 3 (Não expor
erro ao usuário). Se a validação for bem-sucedida: Avançar automaticamente para
o BLOCO 4.
VALIDAÇÃO AUTOMÁTICA DO BLOCO 3
Antes de avançar, o GERED deve validar:
( ) Todas as chaves obrigatórias estão presentes
( ) Nenhuma fonte não autorizada foi utilizada
( ) Não há opinião, comparação ou juízo de valor
( ) O formato está exatamente conforme definido
Se a validação falhar: Reexecutar internamente o BLOCO 3 (Não expor erro ao
usuário).
Se a validação for bem-sucedida: Avançar automaticamente para o BLOCO 4.
>> BLOCO 4
OBJETIVO DO BLOCO 4
Interpretar o edital para responder exatamente às perguntas de requisitos
críticos, informando: SIM ou NÃO
E, quando SIM, o que exatamente é exigido, de forma objetiva. Sem opinião. Sem
inferência. Sem resumo estratégico.
REGRAS ABSOLUTAS DO BLOCO 4
Cada pergunta deve gerar uma única resposta
Cada resposta deve ocupar uma única linha
Quando houver mais de um item, usar tópicos na mesma linha
Se a informação não estiver explícita, escrever exatamente: “Informação não
identificada nos documentos enviados.”
Não misturar respostas
Não repetir texto do prompt
Não criar títulos adicionais
OUTPUT DO BLOCO 4 — FORMATO FIXO
Não alterar nomes das chaves
Não adicionar comentários
Não mudar a ordem
• GARANTIA EXIGIDA: <SIM – detalhar conforme documentos OU NÃO OU Informação não
identificada nos documentos enviados.>
• QUALIFICAÇÃO ECONÔMICA EXIGIDA: <SIM – detalhar conforme documentos OU NÃO OU
Informação não identificada nos documentos enviados.>
• ANTECIPAÇÃO DE PAGAMENTOS EXIGIDA: <SIM – detalhar conforme documentos OU NÃO
OU Informação não identificada nos documentos enviados.>
• APRESENTAÇÃO DOS PROFISSIONAIS EXIGIDA: <SIM – detalhar conforme documentos OU
NÃO OU Informação não identificada nos documentos enviados.>
• VISITA TÉCNICA EXIGIDA: <SIM – detalhar conforme documentos OU NÃO OU
Informação não identificada nos documentos enviados.>
• QUALIFICAÇÕES TÉCNICAS EXIGIDAS PARA A EMPRESA: <descrever objetivamente
conforme documentos OU Informação não identificada nos documentos enviados.>
VALIDAÇÃO AUTOMÁTICA DO BLOCO 4
Antes de concluir o pipeline, o GERED deve validar:
( ) Todas as perguntas foram respondidas
( ) Não há respostas em branco
( ) Não há inferência ou opinião
( ) O formato está exatamente conforme definido
Se a validação falhar: Reexecutar internamente o BLOCO 4 (Não expor erro ao
usuário).
Se a validação for bem-sucedida: Encerrar o pipeline.
REGRA GLOBAL ANTI-ECO
Em nenhum bloco o GERED pode:
Explicar regras
Explicar validações
Explicar decisões
Mostrar checklists internos
O usuário vê somente os outputs.
>> BLOCO 5 (ESPECÍFICO PARA TELEMEDICINA)
CONDIÇÃO DE EXECUÇÃO: Este bloco deve ser executado OBRIGATORIAMENTE E APENAS SE
o objeto envolver Telemedicina, Telessaúde ou Laudos à Distância. Caso
contrário, ignorar este bloco.
OBJETIVO DO BLOCO 5: Identificar barreiras técnicas e requisitos de conformidade
da plataforma tecnológica e infraestrutura.
OUTPUT DO BLOCO 5 — FORMATO FIXO
• PROPRIEDADE DA PLATAFORMA: <SIM – exige que a plataforma seja de propriedade
da licitante | NÃO – permite licenciamento/uso de terceiros | Informação não
identificada.>
• CERTIFICAÇÃO SBIS/CFM: <SIM – detalhar nível de maturidade exigido (ex: NGS2)
OU NÃO EXIGIDO OU Informação não identificada.>
• SISTEMA DE TELEMEDICINA E INTERFACE: <Descrever se o software deve ser
fornecido pela empresa, se deve ser Web/App e se exige marca branca (White
Label) OU Informação não identificada.>
• INTEGRAÇÃO COM SISTEMAS DO SUS (PRONTUÁRIO): <SIM – especificar exigência de
integração com e-SUS, PEC ou barramento municipal OU NÃO OU Informação não
identificada.>
• REQUISITOS DE ASSINATURA DIGITAL (PLATAFORMA): <Detalhar se a PLATAFORMA deve
possuir módulo de assinatura integrado padrão ICP-Brasil para emissão de
receitas/atestados OU Informação não identificada.>
• FORNECIMENTO DE EQUIPAMENTOS/KITS: <SIM – listar itens (ex: computadores,
câmeras, kits de exame físico remoto, totens) OU NÃO OU Informação não
identificada.>
• INFRAESTRUTURA DE CONECTIVIDADE E SUPORTE: <Descrever exigências de link de
internet, redundância ou suporte técnico 24/7 OU Informação não identificada.>
VALIDAÇÃO AUTOMÁTICA DO BLOCO 5 ( ) Foi verificado se o edital exige que o
código-fonte ou a propriedade intelectual pertença à licitante? ( ) A
certificação SBIS foi pesquisada nos anexos técnicos? ( ) A distinção entre
"Assinatura do Profissional" e "Módulo de Assinatura da Plataforma" foi
respeitada? ( ) O formato respeita o padrão de perguntas em NEGRITO E CAIXA
ALTA.
>> OUTPUT FINAL — TEMPLATE EXECUTIVO
Output do bloco 1
Output do bloco 2
Output do bloco 3
Output do bloco 4
Output do bloco 5 (se aplicável
REGRAS ABSOLUTAS
OBRIGATORIAMENTE todo título/pergunta (label) deve estar em NEGRITO.
Cada resposta deve ocupar uma única linha.
Entre cada conjunto lógico de informações, inserir obrigatoriamente uma linha
divisória.
O BLOCO 5 é condicional e só deve ser renderizado se o objeto da licitação for
Telemedicina
Nunca esqueça o negrito e se APROVADO OU REPROVADO"""

MODO_TESTE = True
TESTE_LIMITE = 1

log_entries = []

# =====================================================
# LOG
# =====================================================
def log_message(level, message, extra=None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level.upper(),
        "message": message
    }
    if extra:
        entry.update(extra)

    log_entries.append(entry)
    print(f"[{level.upper()}] {message}")

# =====================================================
# CHECKPOINT
# =====================================================
def carregar_ultimo_boletim():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("ultimo_id", 0))
        except Exception:
            return 0
    return 0

def salvar_ultimo_boletim(boletim_id):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "ultimo_id": boletim_id,
            "data_processamento": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)

# =====================================================
# GOOGLE SHEETS
# =====================================================
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(
        "credentials/google_service_account.json",
        scopes=scopes
    )

    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def atualizar_status_planilha(sheet, bidding_id, aprovado, link_drive):
    col_ids = sheet.col_values(2)

    for i, val in enumerate(col_ids):
        if val == str(bidding_id):
            linha = i + 1
            sheet.update(f"M{linha}", aprovado)
            sheet.update(f"N{linha}", link_drive)
            break

# =====================================================
# LOGIN
# =====================================================
def carregar_credenciais():
    with open("credentials/credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

def criar_browser_autenticado():
    creds = carregar_credenciais()

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    log_message("INFO", "Iniciando login...")
    page.goto(LOGIN_URL, wait_until="networkidle")
    page.get_by_role("link", name="Acessar Conta").click()
    page.get_by_role("textbox", name="Seu e-mail").fill(creds["email"])
    page.get_by_role("textbox", name="Sua senha").fill(creds["password"])
    page.get_by_role("button", name="Acessar").click()
    page.wait_for_timeout(8000)

    log_message("INFO", "Login concluído")

    return p, browser, context

# =====================================================
# ATIVAR BOLETIM (ESSENCIAL)
# =====================================================
def ativar_boletim_html(context, boletim_id):
    page = context.new_page()
    try:
        url = f"https://consulteonline.conlicitacao.com.br/boletim_web/public/boletins/{boletim_id}"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
    finally:
        page.close()

# =====================================================
# EXTRAIR BOLETINS
# =====================================================
def extrair_boletins(context):
    page = context.new_page()
    boletins = set()

    try:
        page.goto(CALENDARIO_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_selector(".fc-event", timeout=30000)
        page.wait_for_timeout(3000)

        eventos = page.locator(".fc-event").all()

        for ev in eventos:
            html = ev.inner_html()
            encontrados = re.findall(r"\b1\d{7,}\b", html)
            for b in encontrados:
                boletins.add(int(b))

        log_message("INFO", f"{len(boletins)} boletins válidos encontrados")
        return sorted(boletins)

    finally:
        page.close()

# =====================================================
# DOWNLOAD EDITAL
# =====================================================
def baixar_edital_por_json(context, boletim_id, bidding_id, arquivo_json):

    url_relativa = arquivo_json.get("url")
    filename = arquivo_json.get("filename")

    if not url_relativa or not filename:
        return []

    url_completa = f"https://consultaonline.conlicitacao.com.br{url_relativa}"

    pasta_base = pathlib.Path("downloads") / str(boletim_id) / str(bidding_id)
    pasta_base.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    for c in context.cookies():
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

    response = session.get(url_completa, timeout=60)

    if response.status_code != 200:
        log_message("WARNING", f"Arquivo não disponível {bidding_id}")
        return []

    caminho = pasta_base / filename

    with open(caminho, "wb") as f:
        f.write(response.content)

    arquivos_extraidos = []

    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(caminho, 'r') as zip_ref:
            zip_ref.extractall(pasta_base)
            for nome in zip_ref.namelist():
                arquivos_extraidos.append(str(pasta_base / nome))
        caminho.unlink()
        return arquivos_extraidos

    return [str(caminho)]

# =====================================================
# MONTAR NOME PASTA
# =====================================================
def montar_nome_pasta(dados):
    ano_mes = datetime.now().strftime("%Y %m")
    municipio = (dados.get("orgao_cidade") or "").upper()
    uf = (dados.get("orgao_estado") or "").upper()
    orgao = (dados.get("orgao_cidade") or "").upper()
    objeto = (dados.get("edital") or "").upper()

    nome = f"{ano_mes} - {municipio} - {uf} - {orgao} - {objeto}"
    return nome.replace("/", "-")

# =====================================================
# COLETAR LICITAÇÕES
# =====================================================
def coletar_licitacoes(context, boletins):

    resultados = []
    sheet = conectar_google_sheets()
    contador_teste = 0

    for boletim_id in boletins:

        # 🔥 Ativa o boletim primeiro
        ativar_boletim_html(context, boletim_id)

        # 🔥 Cria nova session após ativação
        session = requests.Session()

        # 🔥 Copia cookies atualizados do Playwright
        for c in context.cookies():
            session.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain")
            )

        resp = session.get(
            BIDDINGS_API.format(boletim_id),
            timeout=30
        )

        if resp.status_code != 200:
            log_message("WARNING", f"API falhou {boletim_id}")
            continue

        try:
            dados_json = resp.json()
        except Exception:
            log_message(
                "ERROR",
                f"Resposta inválida API {boletim_id} | Conteúdo: {resp.text[:200]}"
            )
            continue

        biddings = dados_json.get("biddings", [])

        for item in biddings:

            if MODO_TESTE and contador_teste >= TESTE_LIMITE:
                log_message("INFO", "Modo teste ativo - encerrando")
                return resultados

            bidding_id = item.get("bidding_id")
            arquivos_edital = []

            # --------------------------------------------
            # DOWNLOAD DO EDITAL
            # --------------------------------------------
            for arquivo in item.get("edicts", []):
                if arquivo.get("filename", "").lower() == "edital.zip":
                    arquivos_edital = baixar_edital_por_json(
                        context,
                        boletim_id,
                        bidding_id,
                        arquivo
                    )
                    break

            # --------------------------------------------
            # PROCESSAMENTO IA
            # --------------------------------------------
            pdf_principal = next(
                (a for a in arquivos_edital if a.lower().endswith(".pdf")),
                None
            )

            if pdf_principal:
                texto_ia, status_ia = analisar_edital(
                    pdf_principal,
                    PROMPT_GERED
                )
            else:
                status_ia = "NAO"

            log_message(
                "INFO",
                f"Bidding {bidding_id} - Status IA: {status_ia}"
            )

            # --------------------------------------------
            # DRIVE
            # --------------------------------------------
            link_drive = ""

            if status_ia in ["SIM", "NAO"]:

                pasta_raiz = SHARED_DRIVE_ID

                if status_ia == "SIM":
                    pasta_tipo_id = criar_pasta("APROVADOS", pasta_raiz)
                else:
                    pasta_tipo_id = criar_pasta("REPROVADOS", pasta_raiz)

                nome_pasta = montar_nome_pasta(item)
                pasta_id = criar_pasta(nome_pasta, pasta_tipo_id)

                # Upload dos arquivos
                for arquivo in arquivos_edital:
                    upload_arquivo_para_pasta(arquivo, pasta_id)

                link_drive = f"https://drive.google.com/drive/folders/{pasta_id}"

            else:
                log_message("WARNING", f"IA falhou para {bidding_id}, upload ignorado.")

            # --------------------------------------------
            # PLANILHA
            # --------------------------------------------
            atualizar_status_planilha(
                sheet,
                bidding_id,
                status_ia,
                link_drive
            )

            resultados.append({
                "boletim_id": boletim_id,
                "bidding_id": bidding_id,
                "status_ia": status_ia,
                "link_drive": link_drive
            })

            contador_teste += 1

    return resultados

# =====================================================
# MAIN
# =====================================================
def main():

    log_message("INFO", "=== INICIANDO COLETA ===")

    ultimo = carregar_ultimo_boletim()

    p, browser, context = criar_browser_autenticado()

    try:
        boletins = extrair_boletins(context)
        novos = [b for b in boletins if b > ultimo]

        if not novos:
            log_message("INFO", "Nenhum boletim novo")
            return

        dados = coletar_licitacoes(context, novos)

        if dados:
            salvar_ultimo_boletim(max(novos))

    finally:
        browser.close()
        p.stop()

        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)

        log_message("INFO", "=== COLETA FINALIZADA ===")

if __name__ == "__main__":
    main()