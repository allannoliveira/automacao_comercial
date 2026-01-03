# Monitor de Licitações Médicas

Sistema completo para **coleta, processamento e visualização de licitações médicas**, com foco em **automação**, **análise de dados** e **visualização moderna em dashboard**.

O projeto é dividido em **Backend (automação e extração de dados)** e **Frontend (visualização e análise)**, funcionando de forma integrada via arquivos CSV.

---

## 🎯 Objetivo do Projeto

O objetivo deste projeto é:

- Automatizar a **coleta de licitações públicas** relacionadas à área da saúde
- Filtrar licitações com base em **palavras-chave médicas**
- Organizar os dados de forma estruturada
- Disponibilizar um **painel visual moderno**, semelhante a ferramentas como Jira/Kanban
- Facilitar a **análise comercial e estratégica** de oportunidades

---

## 🧠 Visão Geral da Arquitetura

[ Site de Licitações ]
↓
[ Backend Python ]

Login automático

Coleta de boletins

Consumo de API JSON

Filtros por regex

Geração de CSV
↓
[ CSV estruturado ]
↓
[ Frontend React ]

Leitura automática do CSV

Dashboard visual

Cards estilo Kanban

Métricas e totais

markdown
Copiar código

---

## ⚙️ Backend — Automação e Coleta de Dados

### 📌 Tecnologias Utilizadas

- **Python 3**
- **Playwright**
- **Requests**
- **BeautifulSoup**
- **Regex**
- **CSV**
- **JSON**

---

### 🔐 Funcionalidades do Backend

- Login automático no portal de licitações usando **Playwright**
- Captura de cookies de sessão autenticada
- Extração dinâmica dos **boletins de licitação**
- Consumo da API:
/boletins/{id}/biddings.json

markdown
Copiar código
- Filtro inteligente usando **regex médica**
- Extração de dados como:
- ID da licitação
- Número do edital
- Cidade / Estado
- Data de abertura
- Valor estimado
- Descrição completa
- Persistência em **CSV**
- Controle de execução incremental via **checkpoint**

---

### 📄 Estrutura do CSV Gerado

```csv
boletim_id,bidding_id,edital,data_abertura,valor_estimado,cidade,estado,descricao,situacao,prazo,data_coleta
Esse CSV é a ponte entre o backend e o frontend.

🎨 Frontend — Visualização e Dashboard
📌 Tecnologias Utilizadas
React (Vite)

JavaScript (ES6+)

Tailwind CSS

PapaParse (leitura de CSV)

HTML5 / CSS3

🖥️ Funcionalidades do Frontend
Leitura automática do CSV (sem upload manual)

Dashboard centralizado e responsivo

Exibição de métricas:

Total de licitações

Valor estimado total

Layout moderno com:

Cards estilo Kanban / Jira

Grid responsivo

Cada licitação exibida em um card independente, contendo:

ID da licitação

Edital

Localidade

Data de abertura

Valor estimado

Ação para visualizar descrição

📐 Layout e UX
Cards organizados em grid responsivo

Espaçamento consistente

Visual escuro profissional

Interface focada em leitura e análise

Estrutura preparada para:

Filtros

Status

Colunas Kanban

Evolução para SaaS

🧩 Estrutura do Frontend
css
Copiar código
src/
├── components/
│   ├── Header.jsx
│   ├── Stats.jsx
│   ├── LicitacoesBoard.jsx
│   ├── LicitacaoCard.jsx
├── App.jsx
├── index.css
├── main.jsx
🚀 Como Executar o Projeto
Backend
bash
Copiar código
python teste.py
Isso irá:

Executar a automação

Atualizar o CSV com novas licitações

Frontend
bash
Copiar código
npm install
npm run dev
O frontend irá:

Ler automaticamente o CSV

Renderizar os dados em tempo de execução

📈 Possíveis Evoluções
Backend como API REST (FastAPI / Flask)

Banco de dados (PostgreSQL / MySQL)

Atualização em tempo real

Filtros avançados

Drag & drop Kanban

Autenticação

Deploy em nuvem

Transformar em produto SaaS

🏁 Conclusão
Este projeto resolve um problema real de forma automatizada, escalável e visualmente profissional, unindo:

Automação de dados

Processamento inteligente

Interface moderna

Foco comercial e estratégico

É uma base sólida tanto para uso interno quanto para evolução como produto.

Desenvolvido com foco em qualidade, automação e escalabilidade.
