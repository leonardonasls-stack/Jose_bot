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

def get_db_connection():
    """Inicializa e retorna uma conexão com o PostgreSQL."""
    if not DATABASE_URL:
        logger.warning("DATABASE_URL ausente. O banco não funcionará até configurar o .env.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Instância global para uso nas consultas
db_conn = get_db_connection()
