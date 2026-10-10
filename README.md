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
* **Banco de Dados:** PostgreSQL (via **Supabase** SDK).
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
* Python 3.11 ou superior
* Um token de Bot do Telegram (obtido via [BotFather](https://t.me/BotFather))
* Uma conta no [Supabase](https://supabase.com/) com um projeto criado.

### 2. Configuração do Banco de Dados
No painel do seu projeto no Supabase, abra o SQL Editor e execute o conteúdo do arquivo `schema.sql` para criar as tabelas necessárias (`users`, `inventory`, `installations`, `returns_to_hq`).

### 3. Instalação e Execução

1. Clone o repositório:
   ```bash
   git clone https://github.com/leonardonasls-stack/Jose_bot.git
   cd Jose_bot
   ```

2. Crie e ative um ambiente virtual (recomendado):
   ```bash
   python -m venv venv
   # No Windows:
   .\venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente:
   * Copie o arquivo `.env.example` para `.env`
   * Preencha as credenciais:
     ```env
     TELEGRAM_BOT_TOKEN=seu_token_aqui
     SUPABASE_URL=sua_url_do_supabase
     SUPABASE_KEY=sua_anon_key_do_supabase
     ```

5. Execute o bot:
   ```bash
   python src/main.py
   ```

6. Abra o Telegram, procure pelo seu bot e envie o comando `/start`.
