import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

async def invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("⚠️ Entrada inválida. Por favor, utilize os botões acima ou digite a informação solicitada corretamente.\nPara sair, clique em Cancelar ou digite /cancel")
    return None

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Monta e exibe o menu principal interativo do bot."""
    
    # Criando os botões de acordo com o nosso PRD
    keyboard = [
        [
            InlineKeyboardButton("📥 Nova Peça", callback_data="menu_add_item"),
            InlineKeyboardButton("📤 Usar Peça", callback_data="menu_use_item")
        ],
        [
            InlineKeyboardButton("📦 Meu Estoque", callback_data="menu_view_stock"),
            InlineKeyboardButton("🚗 Meu Porta-Malas", callback_data="menu_view_trunk")
        ],
        [
            InlineKeyboardButton("🚚 Devolver Matriz (RMA)", callback_data="menu_rma")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🔧 *Gerenciamento de Kit Técnico*\n\n"
        "O que você deseja fazer agora?"
    )

    # Se a chamada veio de uma mensagem (ex: /start)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    # Se a chamada veio de um clique de botão que está voltando ao menu
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def get_product_group_name(item: dict) -> str:
    """Retorna o nome amigável do modelo ou tipo de produto para agrupamento."""
    cat = (item.get('category') or '').lower()
    specs = item.get('specs') or {}
    if cat == 'leitor':
        return specs.get('modelo') or 'Leitor Facial'
    elif cat == 'catraca':
        return specs.get('versao_placa') or 'Catraca Facial'
    elif cat == 'fonte':
        marca = specs.get('marca', '').strip()
        volt = specs.get('voltagem', '').strip()
        txt = f"Fonte {marca} {volt}".strip()
        return txt if txt else "Fonte de Alimentação"
    elif cat == 'antena':
        tipo = specs.get('tipo', '').strip()
        mod = specs.get('modelo', '').strip()
        txt = f"Antena {tipo} {mod}".strip()
        return txt if txt else "Placa de Antena"
    return cat.capitalize() or "Outros"

async def show_stock_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe os tipos de produtos no estoque do técnico como botões interativos."""
    from database.queries import get_user_inventory
    user = update.effective_user
    user_id = str(user.id)
    inventory = get_user_inventory(user_id)

    if not inventory:
        text = "📦 *Meu Estoque*\n\nSeu estoque está vazio no momento."
        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return

    # Agrupa por tipo de produto (modelo / placa / fonte)
    grouped = {}
    for item in inventory:
        grp = get_product_group_name(item)
        grouped.setdefault(grp, []).append(item)

    group_names = sorted(list(grouped.keys()))
    context.user_data['stock_group_names'] = group_names

    keyboard = []
    for idx, grp_name in enumerate(group_names):
        items = grouped[grp_name]
        total_qty = sum(i.get('quantity', 1) for i in items)

        icon = "📱" if any(w in grp_name.lower() for w in ["face", "leitor", "facial"]) else (
               "🚪" if any(w in grp_name.lower() for w in ["block", "catraca", "placa"]) else (
               "⚡" if "fonte" in grp_name.lower() else "📡"
        ))
        btn_text = f"{icon} {grp_name} ({total_qty} unid.)"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"stk_g_{idx}")])

    keyboard.append([InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "📦 *Meu Estoque*\n\nSelecione um *tipo de produto* para ver os dispositivos disponíveis:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_stock_group_items(update: Update, context: ContextTypes.DEFAULT_TYPE, group_idx: int):
    """Exibe os dispositivos individuais pertencentes ao tipo selecionado."""
    from database.queries import get_user_inventory
    user = update.effective_user
    user_id = str(user.id)
    inventory = get_user_inventory(user_id)
    group_names = context.user_data.get('stock_group_names', [])

    if group_idx >= len(group_names):
        return await show_stock_categories(update, context)

    grp_name = group_names[group_idx]
    items_in_group = [i for i in inventory if get_product_group_name(i) == grp_name]

    if not items_in_group:
        return await show_stock_categories(update, context)

    keyboard = []
    for item in items_in_group:
        cat = (item.get('category') or '').lower()
        specs = item.get('specs') or {}
        qty = item.get('quantity', 1)

        if cat in ['leitor', 'catraca']:
            sn = specs.get('numero_serie', 'S/N N/A')
            mac = specs.get('mac_address')
            if mac:
                mac_suffix = f" (MAC: {mac})"
            else:
                mac_suffix = ""
            label = f"🔹 NS: {sn}{mac_suffix}"
        else:
            label = f"🔹 Lote com {qty} unidade(s)"

        keyboard.append([InlineKeyboardButton(label, callback_data=f"stk_i_{item['id']}")])

    keyboard.append([InlineKeyboardButton("⬅️ Voltar aos Tipos", callback_data="menu_view_stock")])
    keyboard.append([InlineKeyboardButton("🏠 Menu Principal", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"📦 *Meu Estoque > {grp_name}*\n\nSelecione um dispositivo para ver detalhes ou usar:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_stock_item_details(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: str):
    """Exibe os detalhes de um item específico e opções 'Usar peça' ou 'Voltar'."""
    from database.queries import get_user_inventory
    user = update.effective_user
    user_id = str(user.id)
    inventory = get_user_inventory(user_id)
    item = next((i for i in inventory if str(i['id']) == item_id), None)

    if not item:
        text = "⚠️ Peça não encontrada no estoque (pode ter sido já utilizada)."
        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Estoque", callback_data="menu_view_stock")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        return

    cat = (item.get('category') or '').lower()
    specs = item.get('specs') or {}
    qty = item.get('quantity', 1)
    grp_name = get_product_group_name(item)

    group_names = context.user_data.get('stock_group_names', [])
    grp_idx = group_names.index(grp_name) if grp_name in group_names else None
    back_callback = f"stk_g_{grp_idx}" if grp_idx is not None else "menu_view_stock"

    text = "📦 *Detalhes do Equipamento*\n\n"
    if cat == "leitor":
        text += f"🔹 *Categoria:* Leitor Facial\n"
        text += f"🔹 *Modelo:* `{specs.get('modelo', 'N/A')}`\n"
        text += f"🔹 *Número de Série:* `{specs.get('numero_serie', 'N/A')}`\n"
        if specs.get('mac_address'):
            text += f"🔹 *MAC Address:* `{specs['mac_address']}`\n"
    elif cat == "catraca":
        text += f"🔹 *Categoria:* Catraca Facial\n"
        text += f"🔹 *Versão da Placa/Modelo:* `{specs.get('versao_placa', 'N/A')}`\n"
        text += f"🔹 *Número de Série:* `{specs.get('numero_serie', 'N/A')}`\n"
        if specs.get('mac_address'):
            text += f"🔹 *MAC Address:* `{specs['mac_address']}`\n"
    elif cat == "fonte":
        text += f"🔹 *Categoria:* Fonte de Alimentação\n"
        text += f"🔹 *Marca:* `{specs.get('marca', 'N/A')}`\n"
        text += f"🔹 *Voltagem / Corrente:* `{specs.get('voltagem', '')} {specs.get('corrente', '')}`\n"
        text += f"🔹 *Quantidade disponível:* {qty} unid.\n"
    elif cat == "antena":
        text += f"🔹 *Categoria:* Placa de Antenas\n"
        text += f"🔹 *Tipo:* `{specs.get('tipo', 'N/A')}`\n"
        text += f"🔹 *Modelo:* `{specs.get('modelo', 'N/A')}`\n"
        text += f"🔹 *Quantidade disponível:* {qty} unid.\n"
    else:
        text += f"🔹 *Categoria:* {cat.capitalize()}\n"
        text += f"🔹 *Quantidade:* {qty} unid.\n"

    text += "\nO que deseja fazer com esta peça?"

    keyboard = [
        [InlineKeyboardButton("📤 Usar Peça", callback_data=f"use_item_direct_{item['id']}")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data=back_callback)],
        [InlineKeyboardButton("🏠 Menu Principal", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe o clique de qualquer botão inline e direciona para o fluxo certo."""
    query = update.callback_query
    
    # É obrigatório 'responder' a query para o Telegram parar de mostrar o ícone de carregamento no botão
    await query.answer() 

    from database.queries import get_or_create_user
    if query.from_user:
        get_or_create_user(query.from_user.id, query.from_user.first_name)
    
    # Roteamento baseado no callback_data do botão
    data = query.data
    
    if data == "menu_view_stock":
        return await show_stock_categories(update, context)
    elif data.startswith("stk_g_"):
        grp_idx = int(data.replace("stk_g_", ""))
        return await show_stock_group_items(update, context, grp_idx)
    elif data.startswith("stk_i_"):
        item_id = data.replace("stk_i_", "")
        return await show_stock_item_details(update, context, item_id)
    elif data == "back_to_menu":
        return await show_main_menu(update, context)
    elif data.startswith("use_item_direct_"):
        from bot.conversation_use import start_use_item
        return await start_use_item(update, context)
    elif data == "menu_view_trunk":
        from database.queries import get_pending_returns
        user_id = str(query.from_user.id)
        returns = get_pending_returns(user_id)
        
        if not returns:
            await query.message.reply_text("🚗 *Meu Porta-Malas*\n\nSeu porta-malas está vazio. Nenhuma sucata aguardando devolução.", parse_mode='Markdown')
        else:
            text = "🚗 *Meu Porta-Malas (Sucatas)*\n\n"
            for item in returns:
                cat = item['category']
                specs = item['specs_removed']
                client = item['client_name']
                
                if cat == "catraca":
                    text += f"🔹 Catraca velha - Placa {specs.get('versao_placa', '')} (NS: {specs.get('numero_serie', '')} | MAC: {specs.get('mac_address', '')})\n   *Cliente:* {client}\n"
                elif cat == "leitor":
                    text += f"🔹 Leitor velho {specs.get('modelo', '')} (NS: {specs.get('numero_serie', '')} | MAC: {specs.get('mac_address', '')})\n   *Cliente:* {client}\n"
                elif cat == "fonte":
                    text += f"🔹 Fonte velha {specs.get('marca', '')} {specs.get('voltagem_corrente', '')}\n   *Cliente:* {client}\n"
                elif cat == "antena":
                    text += f"🔹 Antena velha {specs.get('tipo', '')} - {specs.get('modelo', '')}\n   *Cliente:* {client}\n"
                else:
                    text += f"🔹 {cat.capitalize()} velha\n   *Cliente:* {client}\n"
                text += "\n"
            
            await query.message.reply_text(text, parse_mode='Markdown')
        
        await show_main_menu(update, context)
    elif data in ["menu_add_item", "menu_use_item", "menu_rma"]:
        # Se por algum motivo o callback de entrada na conversa passar direto para este handler:
        if data == "menu_add_item":
            from bot.conversations import start_add_item
            return await start_add_item(update, context)
        elif data == "menu_use_item":
            from bot.conversation_use import start_use_item
            return await start_use_item(update, context)
        elif data == "menu_rma":
            from bot.conversation_rma import start_rma
            return await start_rma(update, context)
    else:
        logger.warning(f"Callback data não reconhecido recebido: {data}")
        await query.message.reply_text("Opção não reconhecida. Use /menu para voltar ao menu principal.")

async def ocr_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite enviar foto diretamente fora dos fluxos para leitura e extração de texto/etiqueta."""
    from bot.ocr_service import extract_text_from_bytes, parse_label_info
    
    if not update.message.photo:
        await update.message.reply_text("Envie uma foto ou imagem para extração de texto.")
        return

    await update.message.reply_text("🔍 *Processando imagem com OCR...*", parse_mode="Markdown")
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    
    raw_text = extract_text_from_bytes(bytes(image_bytes))
    parsed = parse_label_info(raw_text)

    msg = "📷 *Resultado da Leitura de Imagem (OCR)*\n\n"
    if parsed.get("marca"):
        msg += f"🏷️ *Marca:* `{parsed['marca']}`\n"
    if parsed.get("modelo"):
        msg += f"📦 *Modelo:* `{parsed['modelo']}`\n"
    if parsed.get("numero_serie"):
        msg += f"🔢 *Número de Série (S/N):* `{parsed['numero_serie']}`\n"
    if parsed.get("mac_address"):
        msg += f"🌐 *MAC Address:* `{parsed['mac_address']}`\n"

    msg += "\n📄 *Texto Completo Detectado:*\n"
    msg += f"```\n{raw_text if raw_text else '(Nenhum texto legível encontrado)'}\n```"

    await update.message.reply_text(msg, parse_mode="Markdown")
