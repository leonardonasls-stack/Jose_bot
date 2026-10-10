import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega variáveis de ambiente do arquivo .env (na raiz do projeto)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "123456")  # Código padrão se não estiver no .env

# Configuração global de Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    """Inicializa e retorna o cliente do Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Credenciais do Supabase ausentes. O banco não funcionará até configurar o .env.")
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Instância global do banco de dados
supabase_client = get_supabase_client()
