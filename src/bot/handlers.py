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
        from database.queries import get_user_inventory
        user_id = str(query.from_user.id)
        inventory = get_user_inventory(user_id)
        
        if not inventory:
            await query.message.reply_text("📦 *Meu Estoque*\n\nSeu estoque está vazio.", parse_mode='Markdown')
        else:
            text = "📦 *Meu Estoque*\n\n"
            for item in inventory:
                cat = item['category']
                specs = item['specs']
                qty = item['quantity']
                
                if cat == "catraca":
                    text += f"🔹 Catraca - Placa {specs.get('versao_placa', '')} (NS: {specs.get('numero_serie', '')} | MAC: {specs.get('mac_address', '')})\n"
                elif cat == "leitor":
                    text += f"🔹 Leitor {specs.get('modelo', '')} (NS: {specs.get('numero_serie', '')} | MAC: {specs.get('mac_address', '')})\n"
                elif cat == "fonte":
                    text += f"🔹 Fonte {specs.get('marca', '')} {specs.get('voltagem', '')} {specs.get('corrente', '')} ({qty} unid.)\n"
                elif cat == "antena":
                    text += f"🔹 Antena {specs.get('tipo', '')} - {specs.get('modelo', '')} ({qty} unid.)\n"
                else:
                    text += f"🔹 {cat.capitalize()} ({qty} unid.)\n"
            
            await query.message.reply_text(text, parse_mode='Markdown')
        
        # Voltar ao menu principal depois
        await show_main_menu(update, context)
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
