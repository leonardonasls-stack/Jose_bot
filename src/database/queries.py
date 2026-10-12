import logging
import json
from config import db_conn
from database.init_db import init_db

logger = logging.getLogger(__name__)

def _check_client():
    if not db_conn:
        logger.error("Conexão com o banco de dados não está disponível (verifique o .env).")
        return False
    return True

def get_or_create_user(telegram_id: int, first_name: str):
    """Verifica se o usuário existe pelo ID do Telegram. Se não, o cadastra automaticamente."""
    if not _check_client(): return None
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (telegram_id, first_name) VALUES (%s, %s) "
                "ON CONFLICT (telegram_id) DO UPDATE SET first_name = EXCLUDED.first_name "
                "RETURNING *",
                (telegram_id, first_name or "Técnico")
            )
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Erro ao buscar/criar usuário: {e}")
        return None

def get_user_uuid_from_telegram(telegram_id_str: str, first_name: str = "Técnico"):
    """Obtém o UUID customizado da tabela users a partir do Telegram ID. Cria o usuário se não existir."""
    if not _check_client():
        logger.error("get_user_uuid_from_telegram: Banco de dados indisponível.")
        return None
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE telegram_id = %s", (int(telegram_id_str),))
            row = cur.fetchone()
            if row:
                return row['id']

            # Se não existir na tabela users, cadastra agora mesmo para não barrar o fluxo!
            logger.info(f"Usuário Telegram ID {telegram_id_str} não encontrado no banco. Criando registro...")
            cur.execute(
                "INSERT INTO users (telegram_id, first_name) VALUES (%s, %s) "
                "ON CONFLICT (telegram_id) DO UPDATE SET first_name = EXCLUDED.first_name "
                "RETURNING id",
                (int(telegram_id_str), first_name)
            )
            created_row = cur.fetchone()
            if created_row:
                return created_row['id']
    except Exception as e:
        logger.error(f"Erro ao buscar/criar UUID do usuário {telegram_id_str}: {e}")
    return None

def create_user(telegram_id: int, first_name: str):
    """Cadastra o usuário."""
    return get_or_create_user(telegram_id, first_name)

# ==========================================
# FASE 3: ENTRADA DE PEÇAS
# ==========================================
def add_inventory(user_id: str, category: str, specs: dict, quantity: int = 1, first_name: str = "Técnico"):
    """Adiciona uma peça ou um lote no estoque do técnico."""
    if not _check_client():
        logger.error("add_inventory: Falha na conexão com o banco de dados.")
        return False

    uuid = get_user_uuid_from_telegram(user_id, first_name)
    if not uuid:
        logger.error(f"add_inventory: Não foi possível obter ou criar UUID para o usuário Telegram {user_id}.")
        return False

    try:
        specs_json = json.dumps(specs) if isinstance(specs, dict) else str(specs or "{}")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO inventory (user_id, category, specs, quantity) VALUES (%s, %s, %s, %s)",
                (uuid, category, specs_json, quantity)
            )
        logger.info(f"Peça adicionada ao estoque com sucesso: user={user_id}, category={category}, specs={specs}, qty={quantity}")
        return True
    except Exception as e:
        logger.exception(f"Erro ao adicionar peça ao banco de dados: {e}")
        return False

def get_user_inventory(user_id: str):
    """Busca todo o estoque atual do técnico."""
    if not _check_client(): return []
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return []
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT * FROM inventory WHERE user_id = %s AND quantity > 0", (uuid,))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Erro ao buscar estoque: {e}")
        return []

# ==========================================
# FASE 4: USO NO CLIENTE E SUCATA
# ==========================================
def use_inventory_item(inventory_id: str, quantity_used: int = 1):
    """Deduz uma quantidade do estoque do técnico. Se zerar, deleta o registro."""
    if not _check_client(): return False
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE id = %s", (inventory_id,))
            item = cur.fetchone()
            if not item: return False
            
            current_qty = item["quantity"]
            new_qty = current_qty - quantity_used
            
            if new_qty <= 0:
                cur.execute("DELETE FROM inventory WHERE id = %s", (inventory_id,))
            else:
                cur.execute("UPDATE inventory SET quantity = %s WHERE id = %s", (new_qty, inventory_id))
        return True
    except Exception as e:
        logger.error(f"Erro ao dar baixa no estoque: {e}")
        return False

def register_installation(user_id: str, client_name: str, install_date: str, category_used: str, specs_used: dict, inventory_id: str = None):
    """Registra o histórico de uso (onde e quando a peça nova foi usada)."""
    if not _check_client(): return False
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return False
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO installations (user_id, client_name, installation_date, category_used, specs_used, inventory_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (uuid, client_name, install_date, category_used, json.dumps(specs_used), inventory_id)
            )
        return True
    except Exception as e:
        logger.error(f"Erro ao registrar instalação: {e}")
        return False

def add_return_to_hq(user_id: str, client_name: str, category: str, specs: dict):
    """Registra a peça velha (sucata) recolhida do cliente no 'porta-malas'."""
    if not _check_client(): return False
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return False
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO returns_to_hq (user_id, client_name, category, specs_removed, status) VALUES (%s, %s, %s, %s, %s)",
                (uuid, client_name, category, json.dumps(specs), "PENDING_RETURN")
            )
        return True
    except Exception as e:
        logger.error(f"Erro ao recolher sucata: {e}")
        return False

# ==========================================
# FASE 5: DEVOLUÇÃO MATRIZ (RMA)
# ==========================================
def get_pending_returns(user_id: str):
    """Retorna todas as peças velhas do técnico que ainda aguardam despacho."""
    if not _check_client(): return []
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return []
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT * FROM returns_to_hq WHERE user_id = %s AND status = 'PENDING_RETURN'", (uuid,))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Erro ao buscar sucatas pendentes: {e}")
        return []

def dispatch_returns(user_id: str, dispatch_date: str):
    """Dá baixa em TODAS as peças pendentes do técnico, informando a data de envio."""
    if not _check_client(): return False
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return False
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE returns_to_hq SET status = 'DISPATCHED', dispatched_date = %s WHERE user_id = %s AND status = 'PENDING_RETURN'",
                (dispatch_date, uuid)
            )
        return True
    except Exception as e:
        logger.error(f"Erro ao despachar sucatas: {e}")
        return False
