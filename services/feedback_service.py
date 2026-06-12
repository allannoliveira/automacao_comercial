import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SHEET_ID         = os.getenv("GOOGLE_SHEET_ID")
CREDENTIALS_FILE = "credentials/google_service_account.json"
CHECKPOINT_FILE  = "logs/feedbacks_processados.json"
MEMORIA_FILE     = "memory/gemini_memoria.md"

MARCADOR_OURO   = "## Padroes aprendidos — Editais OURO"
MARCADOR_PRATA  = "## Padroes aprendidos — Editais PRATA"
MARCADOR_BRONZE = "## Padroes aprendidos — Editais BRONZE"
MARCADOR_CORR   = "## Correcoes e feedbacks operacionais"

# Descrição de cada nível para orientar o Gemini
_NIVEL_DESC = {
    "ouro":   "Oportunidade de alto valor. Use como referencia positiva maxima.",
    "prata":  "Boa oportunidade com pontos de atencao. Requer verificacao antes de avançar.",
    "bronze": "Oportunidade marginal. Prioridade baixa; considere apenas se agenda permitir.",
}


# =========================
# CONEXÃO
# =========================

def _conectar_sheet(aba="aprovados"):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(aba)


# =========================
# CHECKPOINT
# =========================

def _carregar_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _salvar_checkpoint(dados):
    os.makedirs("logs", exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


# =========================
# LEITURA DA PLANILHA
# =========================

def _ler_todos_feedbacks():
    sheet = _conectar_sheet("aprovados")
    rows  = sheet.get_all_values()
    if len(rows) < 2:
        return []
    headers   = rows[0]
    registros = [dict(zip(headers, row)) for row in rows[1:]]
    return [r for r in registros if r.get("feedback_qualitativo", "").strip()]


# =========================
# MEMÓRIA
# =========================

def _carregar_memoria():
    os.makedirs("memory", exist_ok=True)
    if not os.path.exists(MEMORIA_FILE):
        return (
            "# Memoria operacional do Gemini\n\n"
            f"{MARCADOR_OURO}\n\n"
            f"{MARCADOR_PRATA}\n\n"
            f"{MARCADOR_BRONZE}\n\n"
            f"{MARCADOR_CORR}\n"
        )
    with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
        conteudo = f.read()
    for marcador in (MARCADOR_OURO, MARCADOR_PRATA, MARCADOR_BRONZE, MARCADOR_CORR):
        if marcador not in conteudo:
            conteudo += f"\n\n{marcador}\n"
    return conteudo


def _proxima_secao(conteudo, pos_inicio):
    """Retorna a posição do próximo marcador ## após pos_inicio, ou -1."""
    return conteudo.find("\n## ", pos_inicio + 4)


def _substituir_secao(conteudo, marcador, novo_corpo):
    """Substitui o conteúdo de uma seção identificada pelo marcador."""
    if marcador not in conteudo:
        return conteudo + f"\n\n{marcador}\n\n{novo_corpo}\n"

    inicio  = conteudo.index(marcador)
    proximo = _proxima_secao(conteudo, inicio)
    cabecalho = f"{marcador}\n\n{novo_corpo}\n"

    if proximo == -1:
        return conteudo[:inicio] + cabecalho
    return conteudo[:inicio] + cabecalho + "\n" + conteudo[proximo + 1:]


def _bloco_edital(fb):
    edital     = fb.get("edital", "N/A")
    cidade     = fb.get("orgao_cidade", "N/A")
    uf         = fb.get("orgao_estado", "")
    orgao      = fb.get("orgao_nome", "")
    valor      = fb.get("valor_estimado", "")
    modalidade = fb.get("modalidade", "")
    feedback   = fb.get("feedback_qualitativo", "").strip()
    resumo     = (fb.get("resumo_ia") or "")[:200].strip()

    bloco = (
        f"### {edital} — {cidade}/{uf}\n"
        f"- Orgao: {orgao}\n"
        f"- Valor: {valor} | Modalidade: {modalidade}\n"
        f"- Feedback: {feedback}\n"
    )
    if resumo:
        bloco += f"- Resumo IA (trecho): {resumo}...\n"
    return bloco


def _reconstruir_secao(conteudo, marcador, nivel, registros):
    """Reconstrói uma seção inteira (idempotente)."""
    if not registros:
        return conteudo

    desc   = _NIVEL_DESC.get(nivel, "")
    blocos = "\n".join(_bloco_edital(fb) for fb in registros)
    corpo  = (
        f"{desc}\n\n"
        + blocos
    )
    return _substituir_secao(conteudo, marcador, corpo)


def _adicionar_correcoes(conteudo, feedbacks_novos):
    """Appenda entradas não-classificadas na seção de correções."""
    if not feedbacks_novos:
        return conteudo, 0

    data    = datetime.now().strftime("%Y-%m-%d")
    entradas = []

    for fb in feedbacks_novos:
        classificacao = fb.get("classificacao", "").strip()
        feedback      = fb.get("feedback_qualitativo", "").strip()
        edital        = fb.get("edital", "N/A")
        cidade        = fb.get("orgao_cidade", "N/A")
        uf            = fb.get("orgao_estado", "")
        orgao         = fb.get("orgao_nome", "")

        entradas.append(
            f"### {data} — {edital} ({cidade}/{uf})\n"
            f"- Classificacao: {classificacao or 'Sem classificacao'} | Orgao: {orgao}\n"
            f"- Feedback: {feedback}\n"
            f"- Regra: Aplicar aprendizado deste caso em editais similares."
        )

    bloco = "\n\n".join(entradas)
    if MARCADOR_CORR in conteudo:
        pos = conteudo.index(MARCADOR_CORR) + len(MARCADOR_CORR)
        conteudo = conteudo[:pos] + "\n\n" + bloco + conteudo[pos:]
    else:
        conteudo += f"\n\n{MARCADOR_CORR}\n\n{bloco}\n"

    return conteudo, len(entradas)


# =========================
# PROCESSAMENTO PRINCIPAL
# =========================

def processar_feedbacks():
    print("[FEEDBACK] Iniciando processamento...")

    if not SHEET_ID:
        print("[FEEDBACK] GOOGLE_SHEET_ID nao definido — abortando")
        return 0

    checkpoint = _carregar_checkpoint()
    todos_fb   = _ler_todos_feedbacks()

    por_nivel = {
        "ouro":   [fb for fb in todos_fb if fb.get("classificacao", "").strip().lower() == "ouro"],
        "prata":  [fb for fb in todos_fb if fb.get("classificacao", "").strip().lower() == "prata"],
        "bronze": [fb for fb in todos_fb if fb.get("classificacao", "").strip().lower() == "bronze"],
    }

    novos = [
        fb for fb in todos_fb
        if fb.get("idconlicitacao", "").strip()
        and fb["idconlicitacao"].strip() not in checkpoint
    ]

    total_classificados = sum(len(v) for v in por_nivel.values())
    print(
        f"[FEEDBACK] {len(novos)} novo(s) | "
        f"Ouro: {len(por_nivel['ouro'])} | "
        f"Prata: {len(por_nivel['prata'])} | "
        f"Bronze: {len(por_nivel['bronze'])}"
    )

    if not novos and total_classificados == 0:
        print("[FEEDBACK] Nenhum feedback encontrado")
        return 0

    conteudo = _carregar_memoria()

    # Reconstrói cada seção classificada (idempotente — usa histórico completo)
    conteudo = _reconstruir_secao(conteudo, MARCADOR_OURO,   "ouro",   por_nivel["ouro"])
    conteudo = _reconstruir_secao(conteudo, MARCADOR_PRATA,  "prata",  por_nivel["prata"])
    conteudo = _reconstruir_secao(conteudo, MARCADOR_BRONZE, "bronze", por_nivel["bronze"])

    # Appenda correções dos novos sem classificação específica
    novos_sem_nivel = [
        fb for fb in novos
        if fb.get("classificacao", "").strip().lower() not in ("ouro", "prata", "bronze")
    ]
    conteudo, n_corr = _adicionar_correcoes(conteudo, novos_sem_nivel)

    with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
        f.write(conteudo)

    for fb in novos:
        uid = fb.get("idconlicitacao", "").strip()
        if uid:
            checkpoint[uid] = {
                "classificacao": fb.get("classificacao", ""),
                "feedback":      fb.get("feedback_qualitativo", ""),
                "edital":        fb.get("edital", ""),
                "processado_em": datetime.now().isoformat(),
            }

    _salvar_checkpoint(checkpoint)

    total = total_classificados + n_corr
    print(f"[FEEDBACK] Memoria atualizada — {total_classificados} classificados + {n_corr} correcoes")
    return total


if __name__ == "__main__":
    processar_feedbacks()
