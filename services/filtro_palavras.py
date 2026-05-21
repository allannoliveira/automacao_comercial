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
    r"\bambulancia\b",                          # ambulância (qualquer tipo)
    r"\buti movel\b",                           # UTI móvel (transporte de pacientes)
    r"\bremocao de pacientes?\b",               # remoção de pacientes
    r"\bassistencia social\b",                  # assistência social
    r"\bengenharia clinica\b",                  # engenharia clínica
    r"\bmanutencao (preventiva|corretiva)\b",   # manutenção de equipamentos
    r"\bmanutencao (em|de) equipamento\b",      # manutenção em/de equipamento
    r"\bpecas e componentes?\b",                # peças e componentes (equipamentos)
    r"\bpecas e componetes?\b",                 # variante com typo frequente
    r"\bcalibracao\b",                          # calibração de equipamentos
    r"\bventilador pulmonar\b",                 # ventilador pulmonar (equipamento)
    r"\bassistencia tecnica\b",                 # assistência técnica de equipamentos
]]

# =====================================================
# PADRÕES SIMPLES — um match basta para ser relevante
# =====================================================
_SIMPLES: List[re.Pattern] = [re.compile(p) for p in [
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
    r"\bteleatendimentos?\b",
    r"\bteles? atendimentos?\b",
    r"\btelemedicinas?\b",
    r"\bteles? medicinas?\b",
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
