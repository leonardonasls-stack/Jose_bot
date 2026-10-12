import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env (na raiz do projeto)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ACCESS_CODE = os.getenv("ACCESS_CODE", "123456")  # Código padrão se não estiver no .env

# Configuração global de Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_db_conn = None

def get_db_connection():
    """Inicializa e retorna uma conexão com o PostgreSQL, reconectando se estiver fechada ou inativa."""
    global _db_conn
    if not DATABASE_URL:
        logger.warning("DATABASE_URL ausente. O banco não funcionará até configurar o .env.")
        return None

    # Verifica se a conexão existente ainda está viva
    if _db_conn is not None:
        try:
            if not _db_conn.closed:
                # Ping rápido para verificar se a conexão não caiu por timeout de inatividade
                with _db_conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return _db_conn
        except Exception as ping_err:
            logger.warning(f"Conexão com PostgreSQL inativa ou fechada ({ping_err}). Reconectando...")
            try:
                _db_conn.close()
            except Exception:
                pass
            _db_conn = None

    try:
        _db_conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        _db_conn.autocommit = True
        logger.info("Conexão com o banco de dados PostgreSQL estabelecida com sucesso.")
        return _db_conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

class DBConnProxy:
    """Proxy transparente que garante conexão ativa para qualquer chamada a db_conn."""
    def __getattr__(self, name):
        conn = get_db_connection()
        if not conn:
            raise psycopg2.OperationalError("Não foi possível conectar ao banco de dados.")
        return getattr(conn, name)

    def __bool__(self):
        return get_db_connection() is not None

# Instância com reconexão automática para uso nas consultas
db_conn = DBConnProxy()
