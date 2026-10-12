import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, CommandHandler, filters

from database.queries import add_inventory
from bot.handlers import show_main_menu, invalid_input
from bot.ocr_service import extract_text_from_bytes, parse_label_info

logger = logging.getLogger(__name__)

def format_mac_address(mac_input: str) -> str:
    """Limpa a entrada e formata o MAC address com dois pontos."""
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', mac_input).upper()
    # Adiciona os dois pontos a cada 2 caracteres, caso a string seja válida
    return ':'.join(cleaned[i:i+2] for i in range(0, len(cleaned), 2))

# Estados da conversa
(
    CHOOSE_CATEGORY,
    CATRACA_PLACA, CATRACA_SN, CATRACA_MAC,
    LEITOR_MODELO, LEITOR_SN, LEITOR_MAC,
    FONTE_MARCA, FONTE_VOLTAGEM, FONTE_CORRENTE, FONTE_QTD,
    ANTENA_TIPO, ANTENA_MODELO, ANTENA_QTD
) = range(14)

async def start_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ponto de entrada para adicionar peça"""
    query = update.callback_query
    await query.answer()

    from database.queries import get_or_create_user
    if query.from_user:
        get_or_create_user(query.from_user.id, query.from_user.first_name)

    keyboard = [
        [InlineKeyboardButton("Catraca Facial", callback_data="catraca")],
        [InlineKeyboardButton("Leitor Facial", callback_data="leitor")],
        [InlineKeyboardButton("Fonte de Alimentação", callback_data="fonte")],
        [InlineKeyboardButton("Placa de Antenas", callback_data="antena")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Selecione a categoria da peça que deseja adicionar:",
        reply_markup=reply_markup
    )
    return CHOOSE_CATEGORY

async def handle_category_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data

    if category == "cancel":
        await query.edit_message_text("Operação cancelada.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    context.user_data['add_category'] = category
    context.user_data['add_specs'] = {}

    if category == "catraca":
        await query.edit_message_text("Você selecionou *Catraca Facial*.\n\nDigite a *Versão da Placa* (ou envie uma *foto* da etiqueta):", parse_mode="Markdown")
        return CATRACA_PLACA
    elif category == "leitor":
        await query.edit_message_text("Você selecionou *Leitor Facial*.\n\nDigite o *Modelo* do Leitor (ou envie uma *foto* da etiqueta):", parse_mode="Markdown")
        return LEITOR_MODELO
    elif category == "fonte":
        await query.edit_message_text("Você selecionou *Fonte de Alimentação*.\n\nDigite a *Marca*:", parse_mode="Markdown")
        return FONTE_MARCA
    elif category == "antena":
        keyboard = [
            [InlineKeyboardButton("AM", callback_data="AM"),
             InlineKeyboardButton("RF", callback_data="RF"),
             InlineKeyboardButton("EM", callback_data="EM")]
        ]
        await query.edit_message_text("Você selecionou *Placa de Antenas*.\n\nQual o *Tipo* de Antena?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return ANTENA_TIPO

# --- Fluxo: Catraca Facial ---
async def catraca_placa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto da etiqueta...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        
        placa = parsed.get("modelo") or parsed.get("marca") or "Catraca Facial"
        context.user_data['add_specs']['versao_placa'] = placa
        
        sn = parsed.get("numero_serie")
        mac = parsed.get("mac_address")
        
        if sn:
            context.user_data['add_specs']['numero_serie'] = sn
            if mac:
                context.user_data['add_specs']['mac_address'] = mac
                msg = f"✅ *Foto lida com sucesso!*\n🔹 *Placa/Modelo:* `{placa}`\n🔹 *Nº Série:* `{sn}`\n🔹 *MAC:* `{mac}`\n\nFinalizando cadastro..."
                await update.message.reply_text(msg, parse_mode="Markdown")
                return await finish_add_item(update, context, quantity=1)
            else:
                msg = f"✅ *Dados identificados:*\n🔹 *Placa/Modelo:* `{placa}`\n🔹 *Nº Série:* `{sn}`\n\nDigite o *MAC Address* (ou envie foto do MAC):"
                await update.message.reply_text(msg, parse_mode="Markdown")
                return CATRACA_MAC
        else:
            await update.message.reply_text(f"✅ Placa identificada: `{placa}`\n\nDigite o *Número de Série* (ou envie foto da etiqueta):", parse_mode="Markdown")
            return CATRACA_SN
    else:
        context.user_data['add_specs']['versao_placa'] = update.message.text
        await update.message.reply_text("Digite o *Número de Série* (ou envie uma *foto* da etiqueta):", parse_mode="Markdown")
        return CATRACA_SN

async def catraca_sn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto da etiqueta...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        
        sn = parsed.get("numero_serie")
        mac = parsed.get("mac_address")
        modelo = parsed.get("modelo") or parsed.get("marca")
        if modelo and not context.user_data['add_specs'].get('versao_placa'):
            context.user_data['add_specs']['versao_placa'] = modelo
        elif not context.user_data['add_specs'].get('versao_placa'):
            context.user_data['add_specs']['versao_placa'] = "Catraca Facial"
        
        if sn:
            context.user_data['add_specs']['numero_serie'] = sn
            msg = f"✅ Número de Série identificado: `{sn}`\n"
            if mac:
                context.user_data['add_specs']['mac_address'] = mac
                msg += f"✅ MAC Address também identificado: `{mac}`\n\nFinalizando cadastro..."
                await update.message.reply_text(msg, parse_mode="Markdown")
                return await finish_add_item(update, context, quantity=1)
            else:
                msg += "Digite o *MAC Address* (ou envie uma foto do MAC):"
                await update.message.reply_text(msg, parse_mode="Markdown")
                return CATRACA_MAC
        else:
            detalhe = f"\n\n📄 _Texto detectado:_ `{parsed.get('raw_text', '')[:120]}`" if parsed.get('raw_text') else ""
            await update.message.reply_text(f"⚠️ Não consegui identificar o Número de Série na imagem com clareza.{detalhe}\nPor favor, digite o *Número de Série* manualmente:", parse_mode="Markdown")
            return CATRACA_SN
    else:
        context.user_data['add_specs']['numero_serie'] = update.message.text
        await update.message.reply_text("Digite o *MAC Address* (ou envie uma foto):", parse_mode="Markdown")
        return CATRACA_MAC

async def catraca_mac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto do MAC...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        mac = parsed.get("mac_address")
        if mac:
            context.user_data['add_specs']['mac_address'] = mac
            await update.message.reply_text(f"✅ MAC Address identificado: `{mac}`", parse_mode="Markdown")
            return await finish_add_item(update, context, quantity=1)
        else:
            await update.message.reply_text("⚠️ Não consegui identificar o MAC Address na foto.\nPor favor, digite o *MAC Address* manualmente:", parse_mode="Markdown")
            return CATRACA_MAC
    else:
        mac_formatado = format_mac_address(update.message.text)
        context.user_data['add_specs']['mac_address'] = mac_formatado
        return await finish_add_item(update, context, quantity=1)

# --- Fluxo: Leitor Facial ---
async def leitor_modelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto da etiqueta...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        
        modelo = parsed.get("modelo")
        sn = parsed.get("numero_serie")
        mac = parsed.get("mac_address")
        
        if modelo:
            context.user_data['add_specs']['modelo'] = modelo
        if sn:
            context.user_data['add_specs']['numero_serie'] = sn
        if mac:
            context.user_data['add_specs']['mac_address'] = mac

        if modelo and sn:
            if mac:
                msg = f"✅ *Foto lida com sucesso!*\n🔹 *Modelo:* `{modelo}`\n🔹 *Nº Série:* `{sn}`\n🔹 *MAC:* `{mac}`\n\nFinalizando cadastro..."
                await update.message.reply_text(msg, parse_mode="Markdown")
                return await finish_add_item(update, context, quantity=1)
            else:
                msg = f"✅ *Dados identificados:*\n🔹 *Modelo:* `{modelo}`\n🔹 *Nº Série:* `{sn}`\n\nDigite o *MAC Address* (ou envie foto do MAC):"
                await update.message.reply_text(msg, parse_mode="Markdown")
                return LEITOR_MAC
        elif modelo and not sn:
            await update.message.reply_text(f"✅ *Modelo identificado:* `{modelo}`\n\nDigite o *Número de Série* (ou envie foto da etiqueta):", parse_mode="Markdown")
            return LEITOR_SN
        elif sn and not modelo:
            await update.message.reply_text(f"✅ *Número de Série identificado:* `{sn}`\n\nDigite o *Modelo* do Leitor:", parse_mode="Markdown")
            return LEITOR_MODELO
        else:
            detalhe = f"\n\n📄 _Texto detectado:_ `{parsed.get('raw_text', '')[:120]}`" if parsed.get('raw_text') else ""
            await update.message.reply_text(f"⚠️ Não consegui identificar os dados na foto.{detalhe}\nPor favor, digite o *Modelo* do leitor manualmente:", parse_mode="Markdown")
            return LEITOR_MODELO
    else:
        context.user_data['add_specs']['modelo'] = update.message.text
        await update.message.reply_text("Digite o *Número de Série* (ou envie uma *foto* da etiqueta):", parse_mode="Markdown")
        return LEITOR_SN

async def leitor_sn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto da etiqueta...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        
        sn = parsed.get("numero_serie")
        mac = parsed.get("mac_address")
        modelo = parsed.get("modelo")
        
        if modelo and not context.user_data['add_specs'].get('modelo'):
            context.user_data['add_specs']['modelo'] = modelo
        elif not context.user_data['add_specs'].get('modelo'):
            context.user_data['add_specs']['modelo'] = "Leitor Facial"
        
        if sn:
            context.user_data['add_specs']['numero_serie'] = sn
            msg = f"✅ Número de Série identificado: `{sn}`\n"
            if mac:
                context.user_data['add_specs']['mac_address'] = mac
                msg += f"✅ MAC Address também identificado: `{mac}`\n\nFinalizando cadastro..."
                await update.message.reply_text(msg, parse_mode="Markdown")
                return await finish_add_item(update, context, quantity=1)
            else:
                msg += "Digite o *MAC Address* (ou envie uma foto do MAC):"
                await update.message.reply_text(msg, parse_mode="Markdown")
                return LEITOR_MAC
        else:
            detalhe = f"\n\n📄 _Texto detectado:_ `{parsed.get('raw_text', '')[:120]}`" if parsed.get('raw_text') else ""
            await update.message.reply_text(f"⚠️ Não consegui identificar o Número de Série na imagem com clareza.{detalhe}\nPor favor, digite o *Número de Série* manualmente:", parse_mode="Markdown")
            return LEITOR_SN
    else:
        context.user_data['add_specs']['numero_serie'] = update.message.text
        await update.message.reply_text("Digite o *MAC Address* (ou envie uma foto):", parse_mode="Markdown")
        return LEITOR_MAC

async def leitor_mac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto do MAC...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        mac = parsed.get("mac_address")
        if mac:
            context.user_data['add_specs']['mac_address'] = mac
            await update.message.reply_text(f"✅ MAC Address identificado: `{mac}`", parse_mode="Markdown")
            return await finish_add_item(update, context, quantity=1)
        else:
            await update.message.reply_text("⚠️ Não consegui identificar o MAC Address na foto.\nPor favor, digite o *MAC Address* manualmente:", parse_mode="Markdown")
            return LEITOR_MAC
    else:
        mac_formatado = format_mac_address(update.message.text)
        context.user_data['add_specs']['mac_address'] = mac_formatado
        return await finish_add_item(update, context, quantity=1)

# --- Fluxo: Fonte de Alimentação ---
async def fonte_marca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_specs']['marca'] = update.message.text
    await update.message.reply_text("Qual a *Voltagem*?", parse_mode="Markdown")
    return FONTE_VOLTAGEM

async def fonte_voltagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_specs']['voltagem'] = update.message.text
    await update.message.reply_text("Qual a *Corrente*?", parse_mode="Markdown")
    return FONTE_CORRENTE

async def fonte_corrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_specs']['corrente'] = update.message.text
    await update.message.reply_text("Quantas fontes você recebeu?", parse_mode="Markdown")
    return FONTE_QTD

async def fonte_qtd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Por favor, digite um número válido para a quantidade:")
        return FONTE_QTD
    return await finish_add_item(update, context, quantity=qty)

# --- Fluxo: Placa de Antenas ---
async def antena_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['add_specs']['tipo'] = query.data
    await query.edit_message_text(f"Tipo selecionado: {query.data}\n\nDigite o *Modelo* da placa:", parse_mode="Markdown")
    return ANTENA_MODELO

async def antena_modelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_specs']['modelo'] = update.message.text
    await update.message.reply_text("Quantas placas você recebeu?", parse_mode="Markdown")
    return ANTENA_QTD

async def antena_qtd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Por favor, digite um número válido para a quantidade:")
        return ANTENA_QTD
    return await finish_add_item(update, context, quantity=qty)

# --- Finalização ---
async def finish_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE, quantity: int):
    user = update.effective_user
    user_id = str(user.id)
    first_name = user.first_name or "Técnico"
    category = context.user_data.get('add_category', 'peça')
    specs = context.user_data.get('add_specs', {})

    logger.info(f"finish_add_item: user_id={user_id}, category={category}, specs={specs}, quantity={quantity}")
    success = add_inventory(user_id, category, specs, quantity, first_name=first_name)

    if success:
        text = "✅ *Peça adicionada com sucesso!*"
    else:
        text = "❌ *Erro ao adicionar peça.* Tente novamente."

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")

    # Limpar dados do usuário para essa operação
    context.user_data.pop('add_category', None)
    context.user_data.pop('add_specs', None)

    # Volta ao menu
    await show_main_menu(update, context)
    return ConversationHandler.END

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada.")
    await show_main_menu(update, context)
    return ConversationHandler.END

# Constrói o ConversationHandler para ser usado no main.py
def get_add_item_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_item, pattern="^menu_add_item$")],
        states={
            CHOOSE_CATEGORY: [CallbackQueryHandler(handle_category_choice)],
            
            CATRACA_PLACA: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, catraca_placa)],
            CATRACA_SN: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, catraca_sn)],
            CATRACA_MAC: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, catraca_mac)],
            
            LEITOR_MODELO: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, leitor_modelo)],
            LEITOR_SN: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, leitor_sn)],
            LEITOR_MAC: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, leitor_mac)],
            
            FONTE_MARCA: [MessageHandler(filters.TEXT & ~filters.COMMAND, fonte_marca)],
            FONTE_VOLTAGEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, fonte_voltagem)],
            FONTE_CORRENTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, fonte_corrente)],
            FONTE_QTD: [MessageHandler(filters.TEXT & ~filters.COMMAND, fonte_qtd)],
            
            ANTENA_TIPO: [CallbackQueryHandler(antena_tipo, pattern="^(AM|RF|EM)$")],
            ANTENA_MODELO: [MessageHandler(filters.TEXT & ~filters.COMMAND, antena_modelo)],
            ANTENA_QTD: [MessageHandler(filters.TEXT & ~filters.COMMAND, antena_qtd)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_add),
            MessageHandler(filters.ALL & ~filters.COMMAND, invalid_input)
        ]
    )
