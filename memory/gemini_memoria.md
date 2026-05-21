# Memoria operacional do Gemini

Use este arquivo para ensinar correcoes ao Gemini.
As instrucoes aqui sao anexadas automaticamente ao prompt antes da analise de cada edital.

## Regras gerais aprendidas

### REGRA 1 — Categorias fora do escopo: STATUS_FINAL: REPROVADO imediato

Reprovar automaticamente qualquer edital cujo objeto principal seja uma das categorias abaixo, mesmo que mencione "médico" ou "enfermagem" como tripulação/suporte:

- **Ambulância** (qualquer tipo: suporte básico, UTI móvel Tipo A/B/C/D, suporte avançado, ambulância para evento)
- **Remoção e transporte de pacientes** (transporte inter-hospitalar, remoção eletiva, UTI móvel de transporte)
- **Assistência social** (CRAS, CREAS, acompanhamento social, benefícios, vulnerabilidade social)
- **Engenharia clínica** (manutenção preventiva/corretiva de equipamentos hospitalares, calibração, teste de segurança elétrica, peças e componentes para equipamentos médico-hospitalares, assistência técnica autorizada de equipamentos)
- **Serviços de eventos** (locação de palco, som, iluminação, gradil, sanitários, pavilhão, geradores para festas/eventos, ambulância para evento/festa)

### REGRA 2 — O objeto principal define a categoria, não menções incidentais

A classificação se baseia no OBJETO PRINCIPAL do edital.

**Exemplos de REPROVAÇÃO correta:**
- Licitação de ambulância para evento que menciona "técnico em enfermagem" na tripulação → REPROVADO (objeto: ambulância/evento)
- Licitação de peças para ventilador pulmonar que menciona "uso médico-hospitalar" → REPROVADO (objeto: engenharia clínica/equipamentos)
- Licitação de UTI móvel para transporte inter-hospitalar com "médico socorrista" → REPROVADO (objeto: remoção de pacientes)
- Licitação de manutenção preventiva de ventilador pulmonar com "calibração e teste de segurança elétrica" → REPROVADO (objeto: engenharia clínica)

**Exemplos de APROVAÇÃO correta:**
- Contratação de médicos clínicos gerais para atendimento em UBS → APROVADO
- Serviços de telemedicina para consultas remotas → APROVADO
- Equipe de enfermagem para plantões hospitalares → APROVADO
- Gestão de serviços médicos em UPA/UBS/Hospital → APROVADO
