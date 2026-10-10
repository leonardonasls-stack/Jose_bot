# Plano de Implementação - Bot de Gerenciamento de Kit Técnico

Este documento descreve a arquitetura, as ferramentas e o cronograma de desenvolvimento do bot de Telegram para gerenciamento de estoque técnico.

## 🛠️ 1. Linguagem e Stack Tecnológica
* **Linguagem:** Python 3.11+
* **Framework do Bot:** `python-telegram-bot` (Biblioteca robusta e assíncrona, ideal para gerenciar menus e fluxos de conversa).
* **Banco de Dados / Backend:** SDK oficial do `supabase` (PostgreSQL).
* **Gerenciamento de Ambiente:** `python-dotenv` (Para ler chaves do arquivo `.env`).

## 📂 2. Organização de Pastas do Projeto
A arquitetura do projeto foi pensada para manter o código modular e escalável:

```text
/
├── .env                     # Variáveis de ambiente locais (Não comitar)
├── .env.example             # Exemplo de variáveis para novos desenvolvedores
├── .gitignore               # Arquivos ignorados pelo Git
├── requirements.txt         # Dependências do Python
├── schema.sql               # Backup do esquema do banco de dados
├── PLANO_IMPLEMENTACAO.md   # Este arquivo
└── src/                     # Código-fonte principal
    ├── main.py              # Ponto de entrada que inicializa e roda o bot
    ├── config.py            # Carrega variáveis do .env e inicializa conexão Supabase
    ├── database/            # Camada de comunicação com o banco de dados
    │   └── queries.py       # Funções SQL/Supabase (insert_user, get_inventory, etc.)
    └── bot/                 # Lógica de interface do Telegram
        ├── handlers.py      # Respostas simples e menus inline
        └── conversations.py # Máquinas de estado para formulários longos (ex: dar baixa)
```

## 🚀 3. Fases de Desenvolvimento (Roadmap)

### Fase 1: Configuração Básica e Fundação
- [x] Criar arquitetura de pastas e arquivos de ambiente.
- [x] Definir e criar esquema SQL no Supabase.
- [x] Criar `requirements.txt` e instalar dependências (`pip install`).
- [x] Configurar o cliente do Supabase (`config.py`).
- [x] Criar o "esqueleto" do bot (`main.py`) rodando e respondendo a `/start`.

### Fase 2: Autenticação e Menu Principal
- [x] No comando `/start`, verificar se o usuário já existe na tabela `users`.
- [x] Se não existir, cadastrar o `telegram_id` e nome automaticamente.
- [x] Exibir o Menu Principal (com botões: "📥 Nova Peça", "📤 Usar Peça", "📦 Meu Estoque", "🚚 Devolver Matriz").

### Fase 3: Módulo de Entrada de Peças (Estoque)
- [x] Criar fluxo para Adicionar Peça.
- [x] Separar lógica: "Peça Serializada" (pede MAC/NS, salva qtd 1) vs "Peça em Lote" (pede especificações gerais e quantidade).
- [x] Salvar no banco na tabela `inventory`.

### Fase 4: Módulo de Baixa (Uso no Cliente)
- [x] Fluxo para listar as peças disponíveis no momento da baixa.
- [x] Perguntar Nome do Cliente e Data de Instalação.
- [x] Perguntar as especificações técnicas da **peça velha** que foi retirada (dinâmico por tipo de peça).
- [x] Subtrair saldo de `inventory`, criar registro em `installations` e inserir peça velha em `returns_to_hq`.

### Fase 5: Módulo de RMA (Devolução para a Matriz)
- [x] Comando para listar as peças recolhidas (status PENDING_RETURN).
- [x] Fluxo de "Despachar Sucata": Bot pede a **Data do Despacho**.
- [x] Atualizar no banco os itens para o status DISPATCHED e incluir a data.

## 🗣️ 4. Detalhamento dos Fluxos de Conversação

### Fluxo: 📥 Nova Peça (Entrada de Estoque)
Este fluxo utiliza a máquina de estados (`ConversationHandler`) para guiar o técnico de forma dinâmica.

**Gatilho:** Clique no botão "📥 Nova Peça" no menu principal.
**Pergunta 1 (Estado: Categoria):** "Qual equipamento você está adicionando?" 
*(Botões: `[Catraca Facial]` `[Leitor Facial]` `[Fonte]` `[Placa de Antena]`)*

**Ramificações (Dinâmico):**

* **A) Catraca Facial (Serializada)**
  * Pergunta: "Digite a *Versão da Placa*:"
  * Pergunta: "Digite o *Número de Série*:"
  * Pergunta: "Digite o *MAC Address*:"
  * *Finalização:* Registra `quantity = 1` no banco.

* **B) Leitor Facial (Serializada)**
  * Pergunta: "Digite o *Modelo* do Leitor:"
  * Pergunta: "Digite o *Número de Série*:"
  * Pergunta: "Digite o *MAC Address*:"
  * *Finalização:* Registra `quantity = 1` no banco.

* **C) Fonte de Alimentação (Lote)**
  * Pergunta: "Digite a *Marca*:"
  * Pergunta: "Qual a *Voltagem*?"
  * Pergunta: "Qual a *Corrente*?"
  * Pergunta: "Quantas fontes você recebeu?"
  * *Finalização:* Registra `quantity = valor informado` no banco.

* **D) Placa de Antenas (Lote)**
  * Pergunta: "Qual o *Tipo* de Antena?" *(Botões: `[AM]` `[RF]` `[EM]`)*
  * Pergunta: "Digite o *Modelo* da placa:"
  * Pergunta: "Quantas placas você recebeu?"
  * *Finalização:* Registra `quantity = valor informado` no banco.

### Fluxo: 📤 Usar Peça (Baixa e Recolhimento)
**Gatilho:** Clique no botão "📤 Usar Peça" no menu.
* **Pergunta 1 (Cliente):** "Qual o Nome do Cliente onde o serviço foi realizado?"
* **Pergunta 2 (Data):** "Qual a Data do serviço?" *(Possui botão rápido `[ Hoje ]`)*
* **Pergunta 3 (Uso do Estoque):** "Qual equipamento NOVO do seu estoque você instalou?"
  *(Bot consulta o banco e exibe botões apenas do que o técnico tem)*
  * *Se serializado (Catraca/Leitor):* Bot lista os NS/MACs disponíveis para escolha exata.
  * *Se lote (Fonte/Antena):* Bot pergunta a quantidade instalada.
* **Ação 1:** Bot deduz do `inventory` e registra na tabela `installations`.
* **Pergunta 4 (Sucata):** O bot faz o questionário dinâmico da categoria escolhida (ex: MAC, Modelo, Versão) para coletar os dados da **peça velha** retirada.
* **Ação 2:** Salva a sucata na tabela `returns_to_hq` com status `PENDING_RETURN`.

### Fluxo: 🚚 Devolver Matriz (RMA)
**Gatilho:** Clique no botão "🚚 Devolver Matriz".
* **Ação 1:** Bot consulta e imprime um resumo de todas as peças velhas no porta-malas do técnico.
* **Pergunta 1:** "Deseja despachar todas essas peças para a matriz agora?" *(Botões: `[Sim]` `[Não]`)*
* **Pergunta 2 (Se Sim):** "Qual foi a Data do Despacho? (Ex: DD/MM/AAAA)" *(Possui botão rápido `[ Hoje ]`)*
* **Ação Final:** Atualiza tudo em `returns_to_hq` para `DISPATCHED` salvando a data (gatilho de reposição).
