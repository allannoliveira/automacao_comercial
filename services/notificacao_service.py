import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_APROVADOS  = os.getenv("GOOGLE_CHAT_WEBHOOK_APROVADOS")
WEBHOOK_REPROVADOS = os.getenv("GOOGLE_CHAT_WEBHOOK_REPROVADOS")
MAX_CHARS = 3800  # limite seguro do Google Chat por mensagem


def _enviar(webhook_url, texto):
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"text": texto}, timeout=10).raise_for_status()
    except Exception as e:
        print(f"[NOTIFICACAO] Falha: {type(e).__name__}: {e}")


def _formatar_valor(valor):
    try:
        return f"R$ {float(valor):_.2f}".replace("_", ".").replace(".", ",", 1)
    except Exception:
        return str(valor) if valor else "N/I"


def _linha_deal(dados):
    cidade = (dados.get("orgao_cidade") or "").upper()
    uf     = (dados.get("orgao_estado") or "").upper()
    orgao  = (dados.get("orgao_nome") or "").upper()[:25]
    edital = dados.get("edital") or "N/A"
    valor  = _formatar_valor(dados.get("valor_estimado"))
    link   = dados.get("link_drive") or dados.get("link_drive_edital") or ""

    linha = f"• {cidade}/{uf} — {orgao}\n  Edital: {edital} | {valor}"
    if link:
        linha += f"\n  Drive: {link}"
    return linha


def _linha_reprovado(dados):
    cidade = (dados.get("orgao_cidade") or "").upper()
    uf     = (dados.get("orgao_estado") or "").upper()
    edital = dados.get("edital") or "N/A"
    valor  = _formatar_valor(dados.get("valor_estimado"))
    status = dados.get("status_ia") or "?"
    termo  = dados.get("termo_match") or ""

    motivo = "ERRO IA" if status == "ERRO" else "Reprovado IA"
    linha  = f"• {cidade}/{uf} — {edital} | {valor} | {motivo}"
    if termo:
        linha += f" [{termo}]"
    return linha


def _enviar_em_blocos(webhook_url, cabecalho, itens, rodape=""):
    """Envia em múltiplas mensagens se ultrapassar o limite do Google Chat."""
    bloco_atual = cabecalho + "\n\n"
    mensagens   = []

    for item in itens:
        candidato = bloco_atual + item + "\n"
        if len(candidato) > MAX_CHARS:
            if rodape:
                mensagens.append(bloco_atual + rodape)
            else:
                mensagens.append(bloco_atual)
            bloco_atual = "[continuação]\n\n" + item + "\n"
        else:
            bloco_atual = candidato

    if bloco_atual.strip():
        if rodape:
            bloco_atual += "\n" + rodape
        mensagens.append(bloco_atual)

    for msg in mensagens:
        _enviar(webhook_url, msg)


def notificar_resumo_coleta(stats, resultados=None):
    data       = datetime.now().strftime("%d/%m/%Y %H:%M")
    boletins   = stats.get("boletins_processados", 0)
    coletadas  = stats.get("licitacoes_coletadas", 0)
    aprovadas  = stats.get("licitacoes_aprovadas", 0)
    reprovadas = stats.get("licitacoes_reprovadas", 0)
    erros      = stats.get("licitacoes_erro_ia", 0)
    custo      = stats.get("custo_estimado_usd", 0.0)
    cache_hits = stats.get("cache_hits", 0)

    cabecalho_stats = (
        f"*RELATORIO DE COLETA — {data}*\n"
        f"Boletins: {boletins} | Analisados: {coletadas}\n"
        f"Aprovados: *{aprovadas}* | Reprovados: {reprovadas} | Erros: {erros}\n"
        f"Cache hits: {cache_hits} | Custo: US$ {custo:.4f}"
    )

    if not resultados:
        _enviar(WEBHOOK_APROVADOS, cabecalho_stats)
        return

    lista_aprovados  = [r for r in resultados if r.get("status_ia") == "SIM" and not r.get("skipped")]
    lista_reprovados = [r for r in resultados if r.get("status_ia") not in ("SIM", None) and not r.get("skipped")]

    # --- Mensagem de aprovados ---
    if lista_aprovados and WEBHOOK_APROVADOS:
        itens = [_linha_deal(r) for r in lista_aprovados]
        _enviar_em_blocos(
            WEBHOOK_APROVADOS,
            cabecalho_stats + f"\n\n*APROVADOS ({len(lista_aprovados)})*",
            itens
        )
    elif WEBHOOK_APROVADOS:
        _enviar(WEBHOOK_APROVADOS, cabecalho_stats + "\n\nNenhuma licitacao aprovada nesta coleta.")

    # --- Mensagem de reprovados/erros ---
    if lista_reprovados and WEBHOOK_REPROVADOS:
        itens = [_linha_reprovado(r) for r in lista_reprovados]
        _enviar_em_blocos(
            WEBHOOK_REPROVADOS,
            f"*REPROVADOS/ERROS ({len(lista_reprovados)}) — {data}*",
            itens
        )
