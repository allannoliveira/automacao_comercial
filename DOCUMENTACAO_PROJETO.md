# Documentacao do Projeto - Monitor de Licitacoes

## 1. Visao geral

Este projeto automatiza a coleta, analise e organizacao de licitacoes publicas da area da saude. O fluxo atual busca boletins no portal ConLicitacao, baixa os editais, envia os PDFs para analise com Gemini, registra os dados em uma planilha Google, organiza os arquivos no Google Drive e prepara as licitacoes aprovadas para importacao no Pipedrive.

Na pratica, o sistema funciona como uma esteira comercial automatizada:

1. Coleta novas licitacoes.
2. Baixa os arquivos do edital.
3. Analisa o edital com IA.
4. Classifica como aprovado ou reprovado.
5. Salva tudo na planilha.
6. Organiza documentos no Drive.
7. Envia aprovados para o Pipedrive por meio de um script separado.

## 2. Percentual estimado de conclusao

O projeto esta aproximadamente 70% pronto como automacao backend de uso interno.

Como produto completo, considerando integracao total, painel visual, seguranca, padronizacao de configuracoes e operacao mais robusta, a estimativa fica entre 55% e 60%.

Estimativa por modulo:

| Modulo | Status estimado |
| --- | --- |
| Coleta de boletins | 80% |
| Download e extracao de editais | 75% |
| Analise com Gemini | 75% |
| Organizacao no Google Drive | 80% |
| Registro no Google Sheets | 75% |
| Envio para Pipedrive | 60% |
| Notificacoes em chat | Nao auditado neste repositorio |
| Frontend/dashboard citado no README | Nao encontrado no workspace atual |

## 3. Estrutura principal do projeto

Arquivos e pastas principais encontrados:

| Caminho | Funcao |
| --- | --- |
| `collectors/boletins.py` | Fluxo principal de login, coleta, download, analise com IA, Drive e planilha |
| `services/gemini_service.py` | Servico de comunicacao com Gemini, cache e fallback de modelos |
| `services/gemini_queue.py` | Fila simples para controlar tentativas e intervalo entre chamadas ao Gemini |
| `services/drive_service.py` | Criacao de pastas e upload de arquivos no Google Drive |
| `services/sheets_update_service.py` | Servico antigo/simplificado de atualizacao de planilha |
| `inputData/inputDataPipedrive.py` | Script separado para importar aprovados da planilha para o Pipedrive |
| `logs/ultimo_boletim.json` | Checkpoint do ultimo boletim processado |
| `logs/coleta_log.json` | Historico de execucao/coleta |
| `requirements-dev.txt` | Dependencias Python do projeto |
| `README.md` | Descricao geral do projeto, incluindo partes ainda nao presentes no workspace atual |

## 4. Fluxo principal implementado

### 4.1 Login no portal de licitacoes

O arquivo `collectors/boletins.py` realiza login automatico no portal ConLicitacao usando Playwright.

O sistema:

- Abre o navegador em modo headless.
- Acessa a pagina inicial do portal.
- Clica em "Acessar Conta".
- Preenche email e senha a partir do arquivo de credenciais local.
- Aguarda a autenticacao.
- Mantem os cookies da sessao para usar nas chamadas seguintes.

Essa etapa e essencial porque os endpoints de boletins e arquivos dependem de sessao autenticada.

### 4.2 Extracao de boletins

A funcao de extracao acessa o calendario de boletins e procura eventos no componente visual do FullCalendar.

O codigo coleta IDs de boletins encontrados no HTML, filtra IDs validos e retorna a lista ordenada.

O sistema tambem possui controle incremental por checkpoint. O arquivo `logs/ultimo_boletim.json` guarda o ultimo boletim processado, evitando reprocessar tudo desde o inicio.

Tambem existe checkpoint por licitacao em `logs/licitacoes_processadas.json`. Cada licitacao so entra nesse arquivo depois de ser gravada na planilha, permitindo retomar uma execucao interrompida sem repetir o que ja foi concluido.

Ultimo checkpoint encontrado no projeto:

```json
{
  "ultimo_id": 140827322,
  "data_processamento": "2026-04-23T10:21:10.509097"
}
```

### 4.3 Consulta das licitacoes do boletim

Depois de identificar boletins novos, o sistema ativa o boletim via pagina HTML e consulta a API JSON:

```text
/boletins/{id}/biddings.json
```

Para cada licitacao encontrada, o codigo extrai campos como:

- ID do boletim.
- ID da licitacao.
- Cidade.
- Estado.
- Edital.
- Link/site do edital.
- Itens.
- Descricao.
- Valor estimado.
- Data e hora de abertura.
- Data e hora de prazo.

Esses dados sao usados depois para montar as linhas da planilha, nomear pastas no Drive e criar oportunidades comerciais.

### 4.4 Download dos editais

Para cada licitacao, o sistema procura arquivos do tipo `edital.zip`.

Quando encontra:

1. Monta a URL completa do arquivo.
2. Usa os cookies autenticados do Playwright dentro de uma sessao `requests`.
3. Baixa o arquivo para a pasta `downloads/{boletim_id}/{bidding_id}`.
4. Se o arquivo for ZIP, extrai os arquivos internos.
5. Remove o ZIP original depois da extracao.
6. Retorna a lista de arquivos extraidos.

Depois disso, o sistema procura um PDF principal entre os arquivos extraidos para enviar ao Gemini.

## 5. Analise com Gemini

O servico `services/gemini_service.py` e responsavel por enviar o PDF do edital para o Gemini.

O sistema:

- Le o PDF em bytes.
- Calcula hash MD5 do arquivo.
- Verifica se ja existe resposta em cache.
- Se houver cache, reutiliza a resposta anterior.
- Se nao houver cache, envia o PDF para o Gemini.
- Usa temperatura `0.0` para respostas mais deterministicas.
- Limita a resposta a `5000` tokens.
- Tenta modelos em fallback quando necessario.
- Salva a resposta em `cache_gemini`.

Modelos configurados atualmente:

```text
gemini-3-flash-preview
gemini-2.0-flash
gemini-2.5-flash
```

O servico tambem identifica o status da licitacao a partir da resposta:

- Se encontrar `APROVADO` e nao encontrar `REPROVADO`, classifica como `SIM`.
- Caso contrario, classifica como `NAO`.

## 6. Prompt GERED

O prompt principal esta dentro de `collectors/boletins.py`, na variavel `PROMPT_GERED`.

Esse prompt transforma o Gemini em um agente especialista em licitacoes publicas da area da saude.

O projeto tambem possui uma memoria operacional em `memory/gemini_memoria.md`. Esse arquivo pode ser editado manualmente com correcoes, regras aprendidas e exemplos de erro/acerto. Quando existe conteudo nesse arquivo, ele e anexado automaticamente ao prompt antes de cada analise.

Ele pede uma analise estruturada em blocos:

### Bloco 1 - Dados cadastrais

Extrai informacoes basicas do edital:

- Ata/editorial.
- Objeto da disputa.
- Data de publicacao.
- Data e horario da disputa.
- Valor bruto.
- Unidade de disputa.
- Valor maximo por unidade.
- Instituicao contratante.
- Tipo de contratante.
- Local de prestacao do servico.
- Municipio e UF.

### Bloco 2 - Exigencias tecnicas

Extrai e classifica:

- Especialidades medicas exigidas.
- Qualificacoes tecnicas medicas.
- Exigencias do edital.
- Riscos de interpretacao.
- Horas e quantitativos.
- Valores por especialidade.

### Bloco 3 - Contexto externo

Autoriza pesquisa externa em fontes oficiais para avaliar contexto municipal:

- Populacao estimada.
- Numero de medicos.
- Medicos por mil habitantes.
- Faculdades de medicina proximas.
- Municipio polo mais proximo.

### Bloco 4 - Requisitos criticos

Verifica pontos importantes para decisao:

- Garantia exigida.
- Qualificacao economica.
- Antecipacao de pagamentos.
- Apresentacao dos profissionais.
- Visita tecnica.
- Qualificacoes tecnicas exigidas para a empresa.

### Bloco 5 - Telemedicina

Executado apenas quando o objeto envolver telemedicina, telessaude ou laudos a distancia.

Analisa:

- Propriedade da plataforma.
- Certificacao SBIS/CFM.
- Sistema de telemedicina.
- Integracao com sistemas do SUS.
- Assinatura digital.
- Fornecimento de equipamentos.
- Infraestrutura de conectividade e suporte.

No final, o prompt exige que a resposta indique se a licitacao foi aprovada ou reprovada.

### Como ensinar novas correcoes ao Gemini

Quando uma analise vier errada, registre no arquivo `memory/gemini_memoria.md`:

- O que o Gemini interpretou errado.
- Qual era a interpretacao correta.
- Uma regra objetiva para proximas analises.

Exemplo:

```text
### Correcao 2026-04-28 - Valor anual e mensal

Erro identificado:
- O Gemini tratou valor mensal como valor total da licitacao.

Correcao esperada:
- Quando o edital informar valor mensal e prazo contratual, calcular/identificar tambem o valor total do contrato.

Regra para proximas analises:
- Diferenciar valor mensal, valor unitario e valor global. Se houver prazo em meses, informar claramente qual valor foi encontrado.
```

## 7. Fila e controle de chamadas ao Gemini

O arquivo `services/gemini_queue.py` implementa uma fila simples.

Ela:

- Chama o servico principal do Gemini.
- Aguarda um intervalo entre chamadas.
- Repete a tentativa se ocorrer erro.
- Retorna status `ERRO` quando todas as tentativas falham.

No fluxo principal, a fila esta configurada com delay de 15 segundos entre analises.

## 8. Organizacao no Google Drive

O arquivo `services/drive_service.py` cuida da integracao com Google Drive.

O sistema trabalha com um Shared Drive configurado no codigo.

Para cada edital analisado:

- Se aprovado, cria ou usa uma pasta `APROVADOS`.
- Se reprovado, cria ou usa uma pasta `REPROVADOS`.
- Dentro dessa pasta, cria uma subpasta especifica da licitacao.
- Faz upload dos arquivos do edital.
- Gera e sobe um arquivo `resumo_gemini.txt` com a resposta da IA.
- Retorna o link da pasta e o link do TXT.

O nome da pasta da licitacao segue este padrao:

```text
ANO MES - MUNICIPIO - UF - ORGAO - OBJETO
```

## 9. Registro no Google Sheets

O fluxo principal conecta a uma planilha Google usando uma conta de servico.

A planilha recebe os dados das licitacoes e tambem os resultados da IA. O fluxo atual usa duas abas com o mesmo padrao de cabecalho:

- `aprovados`: recebe licitacoes com `aprovado_ia = SIM`.
- `reprovados`: recebe licitacoes com `aprovado_ia = NAO` ou erro de analise.

Colunas consideradas no fluxo atual:

| Coluna | Campo |
| --- | --- |
| 1 | boletim_id |
| 2 | idconlicitacao / bidding_id |
| 3 | orgao_cidade |
| 4 | orgao_estado |
| 5 | edital |
| 6 | edital_site |
| 7 | itens |
| 8 | descricao |
| 9 | valor_estimado |
| 10 | datahora_abertura |
| 11 | datahora_prazo |
| 12 | data_coleta |
| 13 | aprovado_ia |
| 14 | link_drive_edital |
| 15 | importado_pipedrive |
| 16 | resumo_ia |

O sistema evita duplicidade verificando os IDs ja existentes na coluna 2 das duas abas.

Quando uma licitacao e processada, a nova linha e inserida diretamente na aba correta com status da IA, link da pasta do Drive e link do TXT com resumo do Gemini.

A gravacao agora e incremental: a licitacao e inserida na planilha assim que termina o processamento, e em seguida o ID e salvo no checkpoint de licitacoes processadas.

## 10. Regra atual para aprovados e reprovados

O comportamento atual e:

### Licitacao aprovada pela IA

- Vai para a aba `aprovados`.
- Vai para o Google Drive na pasta `APROVADOS`.
- Recebe link da pasta do Drive.
- Recebe link do resumo Gemini.
- Fica apta para envio ao Pipedrive.

### Licitacao reprovada pela IA

- Vai para a aba `reprovados`.
- Vai para o Google Drive na pasta `REPROVADOS`.
- Recebe link da pasta do Drive.
- Recebe link do resumo Gemini.
- Nao e enviada ao Pipedrive pelo script atual.

### Licitacao com erro na IA

- O status pode retornar como `ERRO`.
- O upload para Drive e ignorado no fluxo atual.
- A linha ainda pode ser adicionada aos resultados, dependendo do ponto da execucao.

## 11. Integracao com Pipedrive

O envio para o Pipedrive esta implementado em `inputData/inputDataPipedrive.py`, mas ainda separado do fluxo principal.

Esse script:

1. Conecta em uma planilha Google.
2. Le todas as linhas.
3. Ignora licitacoes ja marcadas como importadas.
4. Ignora licitacoes nao aprovadas pela IA.
5. Busca no Pipedrive se ja existe deal com o ID da licitacao.
6. Se ja existir, marca a linha como importada.
7. Se nao existir, cria um novo deal.
8. Atualiza campos personalizados do deal.
9. Cria uma nota no deal com o campo `resumo_ia`.
10. Marca a linha como importada no Google Sheets.

Dados enviados/atualizados no Pipedrive:

- Titulo do deal.
- Pipeline.
- Etapa.
- ID da licitacao.
- Numero/nome do edital.
- Data de abertura.
- Valor estimado.
- Nota com resumo da IA.

Ponto importante: o Pipedrive esta funcionalmente encaminhado, mas ainda precisa ser melhor integrado e padronizado com o restante do projeto.

## 12. Logs e historico

O projeto possui arquivos de log em `logs`.

O arquivo `logs/coleta_log.json` registra execucoes anteriores, incluindo:

- Inicio da coleta.
- Inicio e conclusao do login.
- Extracao de boletins.
- Quantidade de boletins encontrados.
- Status de processamento de licitacoes.

O arquivo `logs/ultimo_boletim.json` guarda o ultimo boletim processado e permite continuidade incremental.

O arquivo `logs/licitacoes_processadas.json` guarda IDs de licitacoes ja concluidas. Em uma nova execucao, o coletor pula IDs que ja estejam nesse checkpoint ou que ja existam nas abas `aprovados` e `reprovados`.

## 13. Dependencias principais

As dependencias estao listadas em `requirements-dev.txt`.

Principais bibliotecas usadas:

- `requests` para requisicoes HTTP.
- `beautifulsoup4` para parsing HTML, embora o uso atual principal seja Playwright e regex.
- `playwright` para login e navegacao autenticada.
- `google-api-python-client` para Google Drive.
- `google-auth` e bibliotecas relacionadas para autenticacao Google.
- `google-genai` para Gemini.
- `gspread` para Google Sheets, embora nao esteja listado explicitamente no arquivo de dependencias.
- `pytest`, `black`, `flake8` e `mypy` para desenvolvimento e qualidade.

## 14. Pontos de atencao encontrados

### 14.1 Credenciais e tokens

Existe token/API key sensivel escrito diretamente em codigo no script do Pipedrive. O ideal e mover isso para variaveis de ambiente ou arquivo de credenciais fora do versionamento.

Tambem e recomendavel revisar se algum arquivo de credenciais esta sendo versionado ou exposto.

### 14.2 Organizacao das abas da planilha

O fluxo principal usa a planilha por ID e distribui as linhas entre as abas `aprovados` e `reprovados`.

O script do Pipedrive le somente a aba `aprovados`, mantendo fora do CRM as licitacoes reprovadas pela IA.

### 14.3 Caminhos de credenciais diferentes

O coletor principal usa:

```text
credentials/google_service_account.json
credentials/credentials.json
```

O script do Pipedrive usa:

```text
credentials.json
```

Essa diferenca pode quebrar execucoes em outros ambientes ou quando o projeto for organizado para producao.

### 14.4 README desatualizado em relacao ao workspace

O README descreve um frontend React, dashboard, CSV e layout Kanban. No workspace atual, esses arquivos de frontend nao foram encontrados.

O backend atual trabalha principalmente com Google Sheets, Drive, Gemini e Pipedrive, nao com CSV como saida principal.

### 14.5 Servico antigo de Sheets

O arquivo `services/sheets_update_service.py` parece ser uma versao anterior/simplificada da atualizacao de planilha. Ele nao contempla todos os campos usados pelo fluxo principal, como o link do TXT.

### 14.6 Ausencia de testes automatizados reais

Apesar de existirem dependencias de teste no `requirements-dev.txt`, nao foram encontrados arquivos de teste no workspace atual.

## 15. O que falta para deixar o projeto mais pronto

Para transformar o projeto em uma automacao mais robusta, os proximos passos recomendados sao:

1. Integrar o envio ao Pipedrive no fluxo principal ou criar um orquestrador unico.
2. Criar um orquestrador unico para rodar coleta, analise e importacao Pipedrive na sequencia.
3. Mover tokens e chaves para variaveis de ambiente.
4. Adicionar `.env.example` ou documentacao de configuracao sem segredos.
5. Atualizar o README para refletir o estado real do projeto.
6. Adicionar testes para funcoes criticas, como classificacao da IA, conversao de valores, formatacao de datas e prevencao de duplicidade.
7. Melhorar tratamento de erros quando a IA retorna `ERRO`.
8. Registrar logs em arquivo durante a execucao atual, nao apenas imprimir no console.
9. Validar se o resumo salvo no Pipedrive deve ser o texto da IA ou apenas o link do TXT.
10. Decidir se o frontend/dashboard ainda faz parte do escopo ou se o Google Sheets sera a interface principal.

## 16. Conclusao

O projeto ja possui uma base forte de automacao comercial. Ele coleta licitacoes, baixa documentos, analisa editais com IA, separa aprovados e reprovados, organiza arquivos no Drive e registra tudo em planilha.

O fluxo mais importante ja existe. O que falta agora e consolidar: integrar melhor o Pipedrive, padronizar configuracoes, proteger credenciais, limpar arquivos antigos, atualizar a documentacao e definir se o dashboard/frontend sera retomado ou removido do escopo.

Com esses ajustes, o projeto pode evoluir de uma automacao funcional para uma esteira comercial confiavel e mais facil de operar no dia a dia.
