import logging
from config import supabase_client

logger = logging.getLogger(__name__)

def _check_client():
    if not supabase_client:
        logger.error("Supabase client não está inicializado (verifique o .env).")
        return False
    return True

def get_or_create_user(telegram_id: int, first_name: str):
    """Verifica se o usuário existe pelo ID do Telegram. Se não, o cadastra automaticamente."""
    if not _check_client(): return None
    try:
        response = supabase_client.table("users").select("*").eq("telegram_id", telegram_id).execute()
        if response.data:
            return response.data[0] # Retorna o usuário existente
        
        # Se vazio, cadastra
        new_user = {"telegram_id": telegram_id, "first_name": first_name}
        resp_insert = supabase_client.table("users").insert(new_user).execute()
        return resp_insert.data[0]
    except Exception as e:
        logger.error(f"Erro ao buscar/criar usuário: {e}")
        return None

def get_user_uuid_from_telegram(telegram_id_str: str):
    """Obtém o UUID customizado da tabela users a partir do Telegram ID."""
    if not _check_client(): return None
    try:
        response = supabase_client.table("users").select("id").eq("telegram_id", int(telegram_id_str)).execute()
        if response.data:
            return response.data[0]['id']
    except Exception as e:
        logger.error(f"Erro ao buscar UUID do usuário: {e}")
    return None

def create_user(telegram_id: int, first_name: str):
    """Cadastra o usuário."""
    if not _check_client(): return None
    try:
        new_user = {"telegram_id": telegram_id, "first_name": first_name}
        resp_insert = supabase_client.table("users").insert(new_user).execute()
        return resp_insert.data[0]
    except Exception as e:
        logger.error(f"Erro ao criar usuário: {e}")
        return None

# ==========================================
# FASE 3: ENTRADA DE PEÇAS
# ==========================================
def add_inventory(user_id: str, category: str, specs: dict, quantity: int = 1):
    """Adiciona uma peça ou um lote no estoque do técnico."""
    if not _check_client(): return False
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return False
    try:
        data = {
            "user_id": uuid,
            "category": category,
            "specs": specs,
            "quantity": quantity
        }
        supabase_client.table("inventory").insert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar peça: {e}")
        return False

def get_user_inventory(user_id: str):
    """Busca todo o estoque atual do técnico."""
    if not _check_client(): return []
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return []
    try:
        response = supabase_client.table("inventory").select("*").eq("user_id", uuid).gt("quantity", 0).execute()
        return response.data
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
        # Busca a quantidade atual
        item_resp = supabase_client.table("inventory").select("quantity").eq("id", inventory_id).execute()
        if not item_resp.data: return False
        
        current_qty = item_resp.data[0]["quantity"]
        new_qty = current_qty - quantity_used
        
        if new_qty <= 0:
            supabase_client.table("inventory").delete().eq("id", inventory_id).execute()
        else:
            supabase_client.table("inventory").update({"quantity": new_qty}).eq("id", inventory_id).execute()
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
        data = {
            "user_id": uuid,
            "client_name": client_name,
            "installation_date": install_date,
            "category_used": category_used,
            "specs_used": specs_used,
            "inventory_id": inventory_id
        }
        supabase_client.table("installations").insert(data).execute()
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
        data = {
            "user_id": uuid,
            "client_name": client_name,
            "category": category,
            "specs_removed": specs,
            "status": "PENDING_RETURN"
        }
        supabase_client.table("returns_to_hq").insert(data).execute()
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
        response = supabase_client.table("returns_to_hq").select("*").eq("user_id", uuid).eq("status", "PENDING_RETURN").execute()
        return response.data
    except Exception as e:
        logger.error(f"Erro ao buscar sucatas pendentes: {e}")
        return []

def dispatch_returns(user_id: str, dispatch_date: str):
    """Dá baixa em TODAS as peças pendentes do técnico, informando a data de envio."""
    if not _check_client(): return False
    uuid = get_user_uuid_from_telegram(user_id)
    if not uuid: return False
    try:
        data = {
            "status": "DISPATCHED",
            "dispatched_date": dispatch_date
        }
        # Atualiza todos os itens do técnico que estavam pendentes
        supabase_client.table("returns_to_hq").update(data).eq("user_id", uuid).eq("status", "PENDING_RETURN").execute()
        return True
    except Exception as e:
        logger.error(f"Erro ao despachar sucatas: {e}")
        return False
