import os
import time
import logging
from config import get_db_connection

logger = logging.getLogger(__name__)

MIGRATION_STATEMENTS = [
    # Garante que as colunas essenciais existam mesmo se a tabela já tiver sido criada em versões antigas
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT;",
    "ALTER TABLE inventory ADD COLUMN IF NOT EXISTS specs JSONB DEFAULT '{}'::jsonb;",
    "ALTER TABLE inventory ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1;",
    "ALTER TABLE installations ADD COLUMN IF NOT EXISTS specs_used JSONB;",
    "ALTER TABLE returns_to_hq ADD COLUMN IF NOT EXISTS specs_removed JSONB;",
    "ALTER TABLE returns_to_hq ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'PENDING_RETURN';",
    "ALTER TABLE returns_to_hq ADD COLUMN IF NOT EXISTS dispatched_date DATE;"
]

def find_schema_sql_path() -> str:
    """Busca o arquivo schema.sql em caminhos comuns do projeto e contêiner."""
    candidate_paths = [
        # 1. Raiz do projeto a partir deste arquivo (src/database/init_db.py -> ../../schema.sql)
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql")),
        # 2. Diretório padrão de trabalho do Docker (/app/schema.sql)
        "/app/schema.sql",
        # 3. Diretório de execução atual
        os.path.abspath("schema.sql")
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return ""

def init_db(max_retries: int = 5, retry_interval: float = 2.0) -> bool:
    """
    Executa na inicialização do bot (a cada deploy):
    1. Aguarda e conecta ao banco de dados PostgreSQL.
    2. Executa schema.sql para criar tabelas, extensões e índices faltantes.
    3. Executa migrações idempotentes de colunas.
    """
    logger.info("Iniciando verificação e atualização do banco de dados...")

    conn = None
    for attempt in range(1, max_retries + 1):
        conn = get_db_connection()
        if conn:
            break
        logger.warning(f"Tentativa {attempt}/{max_retries}: Banco de dados ainda não disponível. Aguardando {retry_interval}s...")
        time.sleep(retry_interval)

    if not conn:
        logger.error("❌ Não foi possível conectar ao PostgreSQL após múltiplas tentativas. Inicialização do banco abortada.")
        return False

    try:
        schema_path = find_schema_sql_path()
        if schema_path and os.path.exists(schema_path):
            logger.info(f"Lendo script de estrutura do banco de dados em: {schema_path}")
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            with conn.cursor() as cur:
                cur.execute(schema_sql)
            logger.info("✅ Estrutura do schema.sql aplicada com sucesso!")
        else:
            logger.warning("Arquivo schema.sql não foi localizado fisicamente. Aplicando migrações diretas...")

        # Aplica migrações idempotentes adicionais
        with conn.cursor() as cur:
            for stmt in MIGRATION_STATEMENTS:
                try:
                    cur.execute(stmt)
                except Exception as stmt_err:
                    logger.debug(f"Aviso na migração ({stmt}): {stmt_err}")

        logger.info("✅ Banco de dados atualizado e sincronizado com sucesso!")
        return True
    except Exception as e:
        logger.exception(f"Erro ao inicializar e sincronizar o banco de dados: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
