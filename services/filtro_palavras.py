import re
import unicodedata
from typing import List, Tuple


def _normalizar(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


# =====================================================
# EXCLUSÕES — qualquer match bloqueia, independente
# dos padrões positivos abaixo
# =====================================================
_EXCLUSOES: List[re.Pattern] = [re.compile(p) for p in [
    # --- TRANSPORTE / REMOÇÃO ---
    r"\bambulancia\b",                                      # ambulância (qualquer tipo)
    r"\buti movel\b",                                       # UTI móvel
    r"\bremocao de pacientes?\b",                           # remoção de pacientes
    r"\btransporte escolar\b",                              # transporte escolar
    r"\btransporte de alunos?\b",                           # transporte de alunos
    r"\btransporte de pacientes?\b",                        # transporte de pacientes

    # --- EVENTOS / ENTRETENIMENTO ---
    r"\bdj\b",                                              # disk jockey
    r"\bdisco?jockeys?\b",                                  # disk jockey escrito por extenso
    r"\btrio eletrico\b",                                   # trio elétrico
    r"\bshow (artistico|musical|de banda|sertanejo)\b",     # shows musicais
    r"\banimacao (cultural|artistica|de eventos?)\b",       # animação de eventos
    r"\blocacao de (palco|gradil|pavilhao|tenda|camarim|som e iluminacao)\b",
    r"\bfesta\b",                                           # festa (contexto de evento)
    r"\bcatering\b",                                        # catering/buffet
    r"\bbuffet\b",                                          # buffet

    # --- ENGENHARIA CLÍNICA / EQUIPAMENTOS ---
    r"\bassistencia social\b",                              # assistência social
    r"\bengenharia clinica\b",                              # engenharia clínica
    r"\bmanutencao (preventiva|corretiva)\b",               # manutenção de equipamentos
    r"\bmanutencao (em|de) equipamento\b",                  # manutenção em/de equipamento
    r"\bpecas e componentes?\b",                            # peças e componentes
    r"\bpecas e componetes?\b",                             # typo frequente
    r"\bcalibracao\b",                                      # calibração
    r"\bventilador pulmonar\b",                             # ventilador pulmonar
    r"\bassistencia tecnica\b",                             # assistência técnica de equipamentos

    # --- OUTROS SERVIÇOS NÃO MÉDICOS ---
    r"\blimpeza (urbana|publica|de vias)\b",                # limpeza urbana
    r"\bcoleta de (lixo|residuos|entulho)\b",               # coleta de lixo
    r"\bmerenda escolar\b",                                 # merenda escolar
    r"\balimentacao escolar\b",                             # alimentação escolar
    r"\bvigilancia patrimonial\b",                          # vigilância patrimonial
    r"\bguarda municipal\b",                                # guarda municipal
    r"\bpoda de arvores?\b",                                # poda de árvores
    r"\billuminacao publica\b",                             # iluminação pública
]]

# =====================================================
# PADRÕES DE TELEMEDICINA — subconjunto para filtro de valor
# =====================================================
_TELEMEDICINA: List[re.Pattern] = [re.compile(p) for p in [
    r"\bteleatendimentos?\b",
    r"\bteles? atendimentos?\b",
    r"\btelemedicinas?\b",
    r"\bteles? medicinas?\b",
    r"\btele?consultas?\b",
    r"\btelessaudes?\b",
    r"\btele saudes?\b",
]]

# =====================================================
# PADRÕES SIMPLES — um match basta para ser relevante
# =====================================================
_SIMPLES: List[re.Pattern] = _TELEMEDICINA + [re.compile(p) for p in [
    r"\bconsultas?\b",
    r"\benfermage(?:m|ns)\b",
    r"\benfermeiros?\b",
    r"\bequipes? de enfermage(?:m|ns)\b",
    r"\bequipes? medicas?\b",
    r"\bequipes? para enfermage(?:m|ns)\b",
    r"\bespecialidades? medicas?\b",
    r"\bgest(?:ao|oes) enfermage(?:m|ns)\b",
    r"\bgest(?:ao|oes) medicas?\b",
    r"\bgest(?:ao|oes) medicos?\b",
    r"\bmaos? de obras? de enfermage(?:m|ns)\b",
    r"\bmaos? de obras? enfermage(?:m|ns)\b",
    r"\bmaos? de obras? medicas?\b",
    r"\bmaos? obras? enfermage(?:m|ns)\b",
    r"\bmedicos?\b",
    r"\bservicos? medic(?:o|a)s?\b",
]]

# =====================================================
# PADRÕES COMPOSTOS — ambos os termos devem estar
# presentes em qualquer posição no texto (operador &)
# =====================================================
_AND: List[Tuple[re.Pattern, re.Pattern]] = [
    (re.compile(r"\bequipes?\b"), re.compile(r"\benfermage(?:m|ns)\b")),
]


def licitacao_relevante(edital: str, descricao: str = "", itens: str = "") -> bool:
    """Retorna True se a licitação é da área de saúde e não está na lista de exclusões."""
    texto = _normalizar(f"{edital} {descricao} {itens}")

    for pattern in _EXCLUSOES:
        if pattern.search(texto):
            return False

    for pattern in _SIMPLES:
        if pattern.search(texto):
            return True

    for p1, p2 in _AND:
        if p1.search(texto) and p2.search(texto):
            return True

    return False


def licitacao_telemedicina(edital: str, descricao: str = "", itens: str = "") -> bool:
    """Retorna True se o texto contém termos de telemedicina/teleconsulta."""
    texto = _normalizar(f"{edital} {descricao} {itens}")
    return any(p.search(texto) for p in _TELEMEDICINA)


def motivo_match(edital: str, descricao: str = "", itens: str = "") -> str:
    """Retorna o padrão que gerou o match, ou string vazia se excluído ou irrelevante."""
    texto = _normalizar(f"{edital} {descricao} {itens}")

    for pattern in _EXCLUSOES:
        if pattern.search(texto):
            return ""

    for pattern in _SIMPLES:
        m = pattern.search(texto)
        if m:
            return m.group(0)

    for p1, p2 in _AND:
        if p1.search(texto) and p2.search(texto):
            return f"{p1.pattern} & {p2.pattern}"

    return ""
