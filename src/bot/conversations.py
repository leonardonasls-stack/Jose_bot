import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, CommandHandler, filters

from database.queries import add_inventory
from bot.handlers import show_main_menu, invalid_input
from bot.ocr_service import extract_text_from_bytes, parse_label_info

logger = logging.getLogger(__name__)

def format_mac_address(mac_input: str) -> str:
    """Limpa a entrada e formata o MAC address com dois pontos se tiver 12 caracteres hexadecimais."""
    if not mac_input or mac_input.strip().lower() in ['-', 'n/a', 'na', 'sem mac', 'nenhum', 'none', 'pular']:
        return "N/A"
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', mac_input).upper()
    if len(cleaned) == 12:
        return ':'.join(cleaned[i:i+2] for i in range(0, 12, 2))
    return mac_input.strip()

# Estados da conversa
(
    CHOOSE_CATEGORY,
    CATRACA_PLACA, CATRACA_SN, CATRACA_MAC,
    LEITOR_MODELO, LEITOR_SN, LEITOR_MAC,
    FONTE_MARCA, FONTE_VOLTAGEM, FONTE_CORRENTE, FONTE_QTD,
    ANTENA_TIPO, ANTENA_MODELO, ANTENA_QTD,
    CONFIRM_ADD,
    CORRECT_SN,
    CORRECT_MAC
) = range(17)

def build_confirmation_text_and_markup(category: str, specs: dict, quantity: int = 1):
    category_names = {
        "catraca": "Catraca Facial",
        "leitor": "Leitor Facial",
        "fonte": "Fonte de Alimentação",
        "antena": "Placa de Antenas"
    }
    cat_display = category_names.get(category, category.title())

    text = f"📋 *Confirmação dos Dados do Cadastro*\n\n"
    text += f"📦 *Categoria:* {cat_display}\n"

    if category == "catraca":
        placa = specs.get('versao_placa', 'Catraca Facial')
        sn = specs.get('numero_serie', 'N/D')
        mac = specs.get('mac_address', 'N/D')
        text += f"🔹 *Placa / Versão:* `{placa}`\n"
        text += f"🔢 *Nº de Série:* `{sn}`\n"
        text += f"🌐 *MAC Address:* `{mac}`\n"
    elif category == "leitor":
        modelo = specs.get('modelo', 'Leitor Facial')
        sn = specs.get('numero_serie', 'N/D')
        mac = specs.get('mac_address', 'N/D')
        text += f"🔹 *Modelo:* `{modelo}`\n"
        text += f"🔢 *Nº de Série:* `{sn}`\n"
        text += f"🌐 *MAC Address:* `{mac}`\n"
    elif category == "fonte":
        text += f"🔹 *Marca:* `{specs.get('marca', 'N/D')}`\n"
        text += f"⚡ *Voltagem:* `{specs.get('voltagem', 'N/D')}`\n"
        text += f"🔌 *Corrente:* `{specs.get('corrente', 'N/D')}`\n"
    elif category == "antena":
        text += f"📡 *Tipo:* `{specs.get('tipo', 'N/D')}`\n"
        text += f"🔹 *Modelo:* `{specs.get('modelo', 'N/D')}`\n"

    text += f"📊 *Quantidade:* `{quantity}`\n\n"

    if category in ["catraca", "leitor"]:
        text += (
            "⚠️ *Atenção:* Verifique se o *Nº de Série* e o *MAC* estão completos e corretos antes de salvar.\n\n"
            "Caso algum dado esteja incompleto, utilize os botões de correção abaixo:"
        )
    else:
        text += "Deseja confirmar o cadastro desta peça no estoque?"

    buttons = [
        [InlineKeyboardButton("✅ Confirmar e Cadastrar", callback_data="confirm_save")]
    ]

    edit_row = []
    if category in ["catraca", "leitor"]:
        edit_row.append(InlineKeyboardButton("✏️ Corrigir Nº Série", callback_data="confirm_edit_sn"))
        edit_row.append(InlineKeyboardButton("✏️ Corrigir MAC", callback_data="confirm_edit_mac"))
    if edit_row:
        buttons.append(edit_row)

    buttons.append([InlineKeyboardButton("🔄 Repetir Operação", callback_data="confirm_retry")])
    buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="confirm_cancel")])

    return text, InlineKeyboardMarkup(buttons)

async def prompt_confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE, quantity: int = 1):
    context.user_data['add_quantity'] = quantity
    category = context.user_data.get('add_category', 'peça')
    specs = context.user_data.get('add_specs', {})

    text, reply_markup = build_confirmation_text_and_markup(category, specs, quantity)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

    return CONFIRM_ADD

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
    context.user_data['add_quantity'] = 1

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
                return await prompt_confirm_add(update, context, quantity=1)
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
            if mac:
                context.user_data['add_specs']['mac_address'] = mac
                return await prompt_confirm_add(update, context, quantity=1)
            else:
                msg = f"✅ Número de Série identificado: `{sn}`\n\nDigite o *MAC Address* (ou envie uma foto do MAC):"
                await update.message.reply_text(msg, parse_mode="Markdown")
                return CATRACA_MAC
        else:
            detalhe = f"\n\n📄 _Texto detectado:_ `{parsed.get('raw_text', '')[:120]}`" if parsed.get('raw_text') else ""
            await update.message.reply_text(f"⚠️ Não consegui identificar o Número de Série na imagem com clareza.{detalhe}\nPor favor, digite o *Número de Série* manualmente:", parse_mode="Markdown")
            return CATRACA_SN
    else:
        context.user_data['add_specs']['numero_serie'] = update.message.text.strip()
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
            return await prompt_confirm_add(update, context, quantity=1)
        else:
            await update.message.reply_text("⚠️ Não consegui identificar o MAC Address na foto.\nPor favor, digite o *MAC Address* manualmente:", parse_mode="Markdown")
            return CATRACA_MAC
    else:
        mac_formatado = format_mac_address(update.message.text)
        context.user_data['add_specs']['mac_address'] = mac_formatado
        return await prompt_confirm_add(update, context, quantity=1)

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
                return await prompt_confirm_add(update, context, quantity=1)
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
            if mac:
                context.user_data['add_specs']['mac_address'] = mac
                return await prompt_confirm_add(update, context, quantity=1)
            else:
                msg = f"✅ Número de Série identificado: `{sn}`\n\nDigite o *MAC Address* (ou envie uma foto do MAC):"
                await update.message.reply_text(msg, parse_mode="Markdown")
                return LEITOR_MAC
        else:
            detalhe = f"\n\n📄 _Texto detectado:_ `{parsed.get('raw_text', '')[:120]}`" if parsed.get('raw_text') else ""
            await update.message.reply_text(f"⚠️ Não consegui identificar o Número de Série na imagem com clareza.{detalhe}\nPor favor, digite o *Número de Série* manualmente:", parse_mode="Markdown")
            return LEITOR_SN
    else:
        context.user_data['add_specs']['numero_serie'] = update.message.text.strip()
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
            return await prompt_confirm_add(update, context, quantity=1)
        else:
            await update.message.reply_text("⚠️ Não consegui identificar o MAC Address na foto.\nPor favor, digite o *MAC Address* manualmente:", parse_mode="Markdown")
            return LEITOR_MAC
    else:
        mac_formatado = format_mac_address(update.message.text)
        context.user_data['add_specs']['mac_address'] = mac_formatado
        return await prompt_confirm_add(update, context, quantity=1)

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
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Por favor, digite um número inteiro positivo para a quantidade:")
        return FONTE_QTD
    return await prompt_confirm_add(update, context, quantity=qty)

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
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Por favor, digite um número inteiro positivo para a quantidade:")
        return ANTENA_QTD
    return await prompt_confirm_add(update, context, quantity=qty)

# --- Confirmação e Correção ---
async def handle_confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "confirm_save":
        quantity = context.user_data.get('add_quantity', 1)
        return await finish_add_item(update, context, quantity=quantity)

    elif action == "confirm_edit_sn":
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Voltar à Confirmação", callback_data="confirm_back")]
        ])
        await query.edit_message_text(
            "✏️ *Correção do Número de Série*\n\n"
            "Por favor, digite o *Número de Série completo* (ou envie uma nova foto focada na etiqueta):",
            parse_mode="Markdown",
            reply_markup=cancel_kb
        )
        return CORRECT_SN

    elif action == "confirm_edit_mac":
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Voltar à Confirmação", callback_data="confirm_back")]
        ])
        await query.edit_message_text(
            "✏️ *Correção do MAC Address*\n\n"
            "Por favor, digite o *MAC Address* (ou envie uma foto focada no MAC):",
            parse_mode="Markdown",
            reply_markup=cancel_kb
        )
        return CORRECT_MAC

    elif action == "confirm_retry":
        category = context.user_data.get('add_category')
        context.user_data['add_specs'] = {}
        context.user_data['add_quantity'] = 1

        if category == "catraca":
            await query.edit_message_text(
                "🔄 *Reiniciando cadastro de Catraca Facial.*\n\n"
                "Digite a *Versão da Placa* (ou envie uma *foto* da etiqueta):",
                parse_mode="Markdown"
            )
            return CATRACA_PLACA
        elif category == "leitor":
            await query.edit_message_text(
                "🔄 *Reiniciando cadastro de Leitor Facial.*\n\n"
                "Digite o *Modelo* do Leitor (ou envie uma *foto* da etiqueta):",
                parse_mode="Markdown"
            )
            return LEITOR_MODELO
        elif category == "fonte":
            await query.edit_message_text(
                "🔄 *Reiniciando cadastro de Fonte de Alimentação.*\n\n"
                "Digite a *Marca*:",
                parse_mode="Markdown"
            )
            return FONTE_MARCA
        elif category == "antena":
            keyboard = [
                [InlineKeyboardButton("AM", callback_data="AM"),
                 InlineKeyboardButton("RF", callback_data="RF"),
                 InlineKeyboardButton("EM", callback_data="EM")]
            ]
            await query.edit_message_text(
                "🔄 *Reiniciando cadastro de Placa de Antenas.*\n\n"
                "Qual o *Tipo* de Antena?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ANTENA_TIPO
        else:
            keyboard = [
                [InlineKeyboardButton("Catraca Facial", callback_data="catraca")],
                [InlineKeyboardButton("Leitor Facial", callback_data="leitor")],
                [InlineKeyboardButton("Fonte de Alimentação", callback_data="fonte")],
                [InlineKeyboardButton("Placa de Antenas", callback_data="antena")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
            ]
            await query.edit_message_text(
                "Selecione a categoria da peça que deseja adicionar:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CHOOSE_CATEGORY

    elif action == "confirm_cancel":
        context.user_data.pop('add_category', None)
        context.user_data.pop('add_specs', None)
        context.user_data.pop('add_quantity', None)
        await query.edit_message_text("Operação cancelada.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    elif action == "confirm_back":
        quantity = context.user_data.get('add_quantity', 1)
        return await prompt_confirm_add(update, context, quantity=quantity)

async def handle_correct_sn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto para identificar o Nº de Série...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        sn = parsed.get("numero_serie")
        mac = parsed.get("mac_address")
        if sn:
            context.user_data['add_specs']['numero_serie'] = sn
            if mac and not context.user_data['add_specs'].get('mac_address'):
                context.user_data['add_specs']['mac_address'] = mac
            await update.message.reply_text(f"✅ *Nº de Série atualizado para:* `{sn}`", parse_mode="Markdown")
            quantity = context.user_data.get('add_quantity', 1)
            return await prompt_confirm_add(update, context, quantity=quantity)
        else:
            cancel_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Voltar à Confirmação", callback_data="confirm_back")]
            ])
            await update.message.reply_text(
                "⚠️ Não consegui identificar o Número de Série na foto com clareza.\n"
                "Por favor, digite o *Número de Série* manualmente:",
                parse_mode="Markdown",
                reply_markup=cancel_kb
            )
            return CORRECT_SN
    else:
        sn = update.message.text.strip()
        context.user_data['add_specs']['numero_serie'] = sn
        await update.message.reply_text(f"✅ *Nº de Série atualizado para:* `{sn}`", parse_mode="Markdown")
        quantity = context.user_data.get('add_quantity', 1)
        return await prompt_confirm_add(update, context, quantity=quantity)

async def handle_correct_mac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto para identificar o MAC Address...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        mac = parsed.get("mac_address")
        if mac:
            context.user_data['add_specs']['mac_address'] = mac
            await update.message.reply_text(f"✅ *MAC Address atualizado para:* `{mac}`", parse_mode="Markdown")
            quantity = context.user_data.get('add_quantity', 1)
            return await prompt_confirm_add(update, context, quantity=quantity)
        else:
            cancel_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Voltar à Confirmação", callback_data="confirm_back")]
            ])
            await update.message.reply_text(
                "⚠️ Não consegui identificar o MAC Address na foto.\n"
                "Por favor, digite o *MAC Address* manualmente:",
                parse_mode="Markdown",
                reply_markup=cancel_kb
            )
            return CORRECT_MAC
    else:
        mac = format_mac_address(update.message.text.strip())
        context.user_data['add_specs']['mac_address'] = mac
        await update.message.reply_text(f"✅ *MAC Address atualizado para:* `{mac}`", parse_mode="Markdown")
        quantity = context.user_data.get('add_quantity', 1)
        return await prompt_confirm_add(update, context, quantity=quantity)

async def confirm_add_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = context.user_data.get('add_category', 'peça')
    specs = context.user_data.get('add_specs', {})
    quantity = context.user_data.get('add_quantity', 1)
    text, reply_markup = build_confirmation_text_and_markup(category, specs, quantity)
    if update.message:
        await update.message.reply_text(
            "⚠️ *Ação necessária:*\nUtilize os botões abaixo para confirmar, corrigir ou repetir a operação:\n\n" + text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    return CONFIRM_ADD

# --- Finalização ---
async def finish_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE, quantity: int = 1):
    user = update.effective_user
    user_id = str(user.id)
    first_name = user.first_name or "Técnico"
    category = context.user_data.get('add_category', 'peça')
    specs = context.user_data.get('add_specs', {})

    logger.info(f"finish_add_item: user_id={user_id}, category={category}, specs={specs}, quantity={quantity}")
    success = add_inventory(user_id, category, specs, quantity, first_name=first_name)

    if success:
        text = "✅ *Peça cadastrada com sucesso no seu estoque!*"
    else:
        text = "❌ *Erro ao adicionar peça.* Tente novamente."

    # Limpar dados do usuário para essa operação
    context.user_data.pop('add_category', None)
    context.user_data.pop('add_specs', None)
    context.user_data.pop('add_quantity', None)

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
    menu_text = f"{text}\n\n🔧 *Gerenciamento de Kit Técnico*\nO que você deseja fazer agora?"

    if update.callback_query:
        await update.callback_query.message.edit_text(menu_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(menu_text, reply_markup=reply_markup, parse_mode="Markdown")

    return ConversationHandler.END

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('add_category', None)
    context.user_data.pop('add_specs', None)
    context.user_data.pop('add_quantity', None)
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

            CONFIRM_ADD: [
                CallbackQueryHandler(handle_confirm_add, pattern="^confirm_"),
                MessageHandler(filters.ALL & ~filters.COMMAND, confirm_add_invalid_input)
            ],
            CORRECT_SN: [
                CallbackQueryHandler(handle_confirm_add, pattern="^confirm_"),
                MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_correct_sn)
            ],
            CORRECT_MAC: [
                CallbackQueryHandler(handle_confirm_add, pattern="^confirm_"),
                MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_correct_mac)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_add),
            MessageHandler(filters.ALL & ~filters.COMMAND, invalid_input)
        ]
    )
