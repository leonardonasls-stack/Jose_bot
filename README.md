# Bot de Gerenciamento de Kit Técnico 🤖🔧

Um bot do Telegram desenvolvido em Python para auxiliar técnicos de campo no gerenciamento de seu estoque de peças, registro de instalações em clientes e devolução de equipamentos recolhidos (RMA) para a matriz.

## 🌟 Funcionalidades

O sistema é focado em 4 módulos principais, acessados através de um menu interativo no Telegram:

1. **📥 Nova Peça (Entrada de Estoque)**
   * Permite adicionar novos equipamentos ao estoque do técnico (porta-malas).
   * Suporta equipamentos **Serializados** (Catraca Facial, Leitor Facial - capturando NS, MAC, etc) e **Lotes** (Fontes, Placas de Antenas - capturando especificações e quantidades).

2. **📤 Usar Peça (Baixa e Recolhimento)**
   * Registra a instalação de uma peça nova em um cliente.
   * Deduz o item do estoque automaticamente.
   * Solicita as informações da **peça velha (sucata)** retirada no local e a adiciona à lista de recolhimento do técnico.

3. **📦 Meu Estoque (Consulta)**
   * Exibe um resumo rápido de todas as peças e quantidades atualmente em posse do técnico.

4. **🚚 Devolver Matriz (RMA)**
   * Lista todas as sucatas que o técnico tem no porta-malas aguardando despacho.
   * Registra a data de despacho, limpando o porta-malas virtual e informando a matriz.

## 🛠️ Stack Tecnológica

* **Linguagem:** Python 3.11+
* **Framework do Bot:** `python-telegram-bot` (Assíncrono, gerenciamento de menus e máquinas de estado).
* **Banco de Dados:** PostgreSQL (local ou em contêiner Docker).
* **Ambiente:** `python-dotenv` para variáveis de ambiente.

## 📂 Estrutura do Projeto

```text
/
├── src/                     # Código-fonte principal
│   ├── main.py              # Ponto de entrada (inicializa o bot)
│   ├── config.py            # Configurações e conexão com Supabase
│   ├── database/
│   │   └── queries.py       # Interações e queries com o banco de dados
│   └── bot/
│       ├── handlers.py      # Callbacks de botões e menu principal
│       ├── conversations.py # Fluxo de adicionar peça
│       ├── conversation_use.py  # Fluxo de dar baixa e recolher sucata
│       ├── conversation_rma.py  # Fluxo de despacho para a matriz
│       └── conversation_auth.py # Autenticação
├── schema.sql               # Estrutura das tabelas do banco de dados
├── requirements.txt         # Dependências Python
├── PLANO_IMPLEMENTACAO.md   # Documentação de arquitetura e fluxos
└── .env.example             # Template de variáveis de ambiente
```

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
* Um token de Bot do Telegram (obtido via [BotFather](https://t.me/BotFather))
* **Opção 1:** [Docker](https://docs.docker.com/get-docker/) e Docker Compose (Recomendado)
* **Opção 2:** Python 3.11+ e PostgreSQL local

### 2. Configuração Inicial

1. Clone o repositório:
   ```bash
   git clone https://github.com/leonardonasls-stack/Jose_bot.git
   cd Jose_bot
   ```

2. Configure as variáveis de ambiente:
   * Copie o arquivo `.env.example` para `.env`
   * Preencha seu token do Telegram e o código de acesso:
     ```env
     TELEGRAM_BOT_TOKEN=seu_token_aqui
     DATABASE_URL=postgresql://postgres:postgres@db:5432/bot_db  # Mantenha assim para usar com Docker
     ACCESS_CODE=123456
     ```

### 3. Execução com Docker (Recomendado) 🐳

A forma mais simples de rodar o bot e o banco de dados é usando o Docker Compose. O script `schema.sql` será executado automaticamente na primeira inicialização do banco.

```bash
docker-compose up -d
```

Pronto! O bot já está rodando em segundo plano. Você pode verificar os logs com:
```bash
docker-compose logs -f bot
```

### 4. Execução Local sem Docker (Alternativa)

Se preferir não usar Docker, você precisará ter um banco de dados PostgreSQL rodando localmente.

1. Crie um banco de dados e execute o script `schema.sql` para criar as tabelas.
2. Altere o `DATABASE_URL` no seu `.env` para apontar para o seu banco local:
   ```env
   DATABASE_URL=postgresql://seu_usuario:sua_senha@localhost:5432/nome_do_banco
   ```
3. Crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   # No Windows:
   .\venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```
4. Instale as dependências e execute:
   ```bash
   pip install -r requirements.txt
   python src/main.py
   ```

### 5. Iniciar o Uso
Abra o Telegram, procure pelo seu bot e envie o comando `/start`. Digite o `ACCESS_CODE` configurado no seu `.env` para se autenticar.
