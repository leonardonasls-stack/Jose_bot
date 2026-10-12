import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, CommandHandler, filters

from database.queries import get_user_inventory, use_inventory_item, register_installation, add_return_to_hq
from bot.handlers import show_main_menu, invalid_input
from bot.conversations import format_mac_address
from bot.ocr_service import extract_text_from_bytes, parse_label_info

logger = logging.getLogger(__name__)

# Estados da conversa
(
    USE_CLIENT_NAME,
    USE_DATE,
    USE_CHOOSE_ITEM,
    USE_ITEM_QTD,
    USE_OLD_INFO_1,
    USE_OLD_INFO_2,
    USE_OLD_INFO_3
) = range(7)

async def start_use_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ponto de entrada para dar baixa em peça"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Você escolheu *📤 Usar Peça*.\n\nQual o *Nome do Cliente* onde o serviço foi realizado?",
        parse_mode="Markdown"
    )
    # Limpa estado anterior
    context.user_data['use_data'] = {}
    return USE_CLIENT_NAME

async def use_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['use_data']['client_name'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("Hoje", callback_data="hoje")]]
    await update.message.reply_text(
        "Qual a *Data do serviço*?", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return USE_DATE

async def use_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['use_data']['install_date'] = update.message.text
    return await prompt_inventory(update, context)

async def use_date_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    import datetime
    context.user_data['use_data']['install_date'] = datetime.datetime.now().strftime("%d/%m/%Y")
    return await prompt_inventory(update, context)

async def prompt_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    inventory = get_user_inventory(user_id)
    
    if not inventory:
        text = "Seu estoque está vazio. Não é possível dar baixa."
        if update.message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        await show_main_menu(update, context)
        return ConversationHandler.END

    keyboard = []
    # Cria botoes com os itens
    for item in inventory:
        cat = item['category']
        specs = item['specs']
        qty = item['quantity']
        
        # Cria label do botão
        if cat == "catraca":
            label = f"Catraca - Placa {specs.get('versao_placa', '')} (NS: {specs.get('numero_serie', '')})"
        elif cat == "leitor":
            label = f"Leitor {specs.get('modelo', '')} (NS: {specs.get('numero_serie', '')})"
        elif cat == "fonte":
            label = f"Fonte {specs.get('marca', '')} {specs.get('voltagem', '')} ({qty}x)"
        elif cat == "antena":
            label = f"Antena {specs.get('tipo', '')} - {specs.get('modelo', '')} ({qty}x)"
        else:
            label = f"{cat.capitalize()} ({qty}x)"
            
        # O callback_data precisa ser curto (limite 64 bytes do telegram), passamos o ID
        keyboard.append([InlineKeyboardButton(label, callback_data=f"inv_{item['id']}")])
        
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_use")])
    
    text = "Qual equipamento *NOVO* do seu estoque você instalou?"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    context.user_data['use_data']['inventory_list'] = inventory
    return USE_CHOOSE_ITEM

async def handle_choose_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "cancel_use":
        await query.edit_message_text("Operação cancelada.")
        await show_main_menu(update, context)
        return ConversationHandler.END
        
    if data.startswith("inv_"):
        item_id = data.replace("inv_", "")
        inventory = context.user_data['use_data']['inventory_list']
        selected_item = next((i for i in inventory if str(i['id']) == item_id), None)
        
        if not selected_item:
            await query.edit_message_text("Item não encontrado no estoque.")
            await show_main_menu(update, context)
            return ConversationHandler.END
            
        context.user_data['use_data']['selected_item'] = selected_item
        cat = selected_item['category']
        
        if cat in ["fonte", "antena"]:
            await query.edit_message_text(f"Quantas unidades de {cat.capitalize()} você instalou?", parse_mode="Markdown")
            return USE_ITEM_QTD
        else:
            context.user_data['use_data']['quantity_used'] = 1
            return await prompt_old_info_1(update, context)

async def use_item_qtd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Por favor, digite um número válido para a quantidade:")
        return USE_ITEM_QTD
        
    selected_item = context.user_data['use_data']['selected_item']
    if qty > selected_item['quantity']:
        await update.message.reply_text(f"Você só possui {selected_item['quantity']} no estoque! Digite novamente:")
        return USE_ITEM_QTD
        
    context.user_data['use_data']['quantity_used'] = qty
    return await prompt_old_info_1(update, context)

async def prompt_old_info_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_item = context.user_data['use_data']['selected_item']
    cat = selected_item['category']
    context.user_data['use_data']['old_specs'] = {}
    
    text = "Vamos registrar a *sucata* retirada.\n\n"
    if cat == "catraca":
        text += "Digite a *Versão da Placa* velha:"
    elif cat == "leitor":
        text += "Digite o *Modelo* do Leitor velho:"
    elif cat == "fonte":
        text += "Digite a *Marca* da Fonte velha:"
    elif cat == "antena":
        text += "Qual o *Tipo* da Antena velha? (Ex: AM, RF, EM)"
        
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    return USE_OLD_INFO_1

async def handle_old_info_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = context.user_data['use_data']['selected_item']['category']
    text_input = update.message.text
    
    if cat == "catraca":
        context.user_data['use_data']['old_specs']['versao_placa'] = text_input
        await update.message.reply_text("Digite o *Número de Série* velho (ou envie uma *foto* da etiqueta):", parse_mode="Markdown")
        return USE_OLD_INFO_2
    elif cat == "leitor":
        context.user_data['use_data']['old_specs']['modelo'] = text_input
        await update.message.reply_text("Digite o *Número de Série* velho (ou envie uma *foto* da etiqueta):", parse_mode="Markdown")
        return USE_OLD_INFO_2
    elif cat == "fonte":
        context.user_data['use_data']['old_specs']['marca'] = text_input
        await update.message.reply_text("Qual a *Voltagem* e *Corrente* da velha? (ex: 12V 2A)", parse_mode="Markdown")
        return USE_OLD_INFO_2
    elif cat == "antena":
        context.user_data['use_data']['old_specs']['tipo'] = text_input
        await update.message.reply_text("Digite o *Modelo* da placa velha:", parse_mode="Markdown")
        return USE_OLD_INFO_2

async def handle_old_info_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = context.user_data['use_data']['selected_item']['category']
    
    if cat in ["catraca", "leitor"]:
        if update.message.photo:
            await update.message.reply_text("🔍 *Analisando foto da etiqueta da sucata...*", parse_mode="Markdown")
            photo_file = await update.message.photo[-1].get_file()
            image_bytes = await photo_file.download_as_bytearray()
            parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
            
            sn = parsed.get("numero_serie")
            mac = parsed.get("mac_address")
            
            if sn:
                context.user_data['use_data']['old_specs']['numero_serie'] = sn
                msg = f"✅ Número de Série velho identificado: `{sn}`\n"
                if mac:
                    context.user_data['use_data']['old_specs']['mac_address'] = mac
                    msg += f"✅ MAC Address velho também identificado: `{mac}`\n\nFinalizando baixa..."
                    await update.message.reply_text(msg, parse_mode="Markdown")
                    return await finish_use_item(update, context)
                else:
                    msg += "Digite o *MAC Address* velho (ou envie uma foto):"
                    await update.message.reply_text(msg, parse_mode="Markdown")
                    return USE_OLD_INFO_3
            else:
                await update.message.reply_text("⚠️ Não identifiquei o Número de Série na imagem.\nPor favor, digite o *Número de Série* manualmente:", parse_mode="Markdown")
                return USE_OLD_INFO_2
        else:
            context.user_data['use_data']['old_specs']['numero_serie'] = update.message.text
            await update.message.reply_text("Digite o *MAC Address* velho (ou envie uma foto):", parse_mode="Markdown")
            return USE_OLD_INFO_3
    elif cat == "fonte":
        context.user_data['use_data']['old_specs']['voltagem_corrente'] = update.message.text
        return await finish_use_item(update, context)
    elif cat == "antena":
        context.user_data['use_data']['old_specs']['modelo'] = update.message.text
        return await finish_use_item(update, context)

async def handle_old_info_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("🔍 *Analisando foto do MAC da sucata...*", parse_mode="Markdown")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        parsed = parse_label_info(extract_text_from_bytes(bytes(image_bytes)))
        mac = parsed.get("mac_address")
        if mac:
            context.user_data['use_data']['old_specs']['mac_address'] = mac
            await update.message.reply_text(f"✅ MAC Address velho identificado: `{mac}`", parse_mode="Markdown")
            return await finish_use_item(update, context)
        else:
            await update.message.reply_text("⚠️ Não consegui identificar o MAC Address na foto.\nPor favor, digite o *MAC Address* manualmente:", parse_mode="Markdown")
            return USE_OLD_INFO_3
    else:
        mac_formatado = format_mac_address(update.message.text)
        context.user_data['use_data']['old_specs']['mac_address'] = mac_formatado
        return await finish_use_item(update, context)

async def finish_use_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    use_data = context.user_data['use_data']
    user_id = str(update.effective_user.id)
    
    item = use_data['selected_item']
    
    # 1. Deduct from inventory
    success_use = use_inventory_item(item['id'], use_data['quantity_used'])
    
    # 2. Register installation
    if success_use:
        success_inst = register_installation(
            user_id=user_id,
            client_name=use_data['client_name'],
            install_date=use_data['install_date'],
            category_used=item['category'],
            specs_used=item['specs'],
            inventory_id=item['id']
        )
        
        # 3. Insert sucata into returns_to_hq
        success_ret = add_return_to_hq(
            user_id=user_id,
            client_name=use_data['client_name'],
            category=item['category'],
            specs=use_data['old_specs']
        )
        
        await update.message.reply_text("✅ *Baixa efetuada com sucesso!*\nEstoque atualizado e sucata registrada no porta-malas.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ *Erro ao dar baixa no estoque.*", parse_mode="Markdown")
        
    context.user_data.pop('use_data', None)
    await show_main_menu(update, context)
    return ConversationHandler.END

async def cancel_use(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada.")
    await show_main_menu(update, context)
    return ConversationHandler.END

def get_use_item_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_use_item, pattern="^menu_use_item$")],
        states={
            USE_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, use_client_name)],
            USE_DATE: [
                CallbackQueryHandler(use_date_btn, pattern="^hoje$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, use_date_text)
            ],
            USE_CHOOSE_ITEM: [CallbackQueryHandler(handle_choose_item)],
            USE_ITEM_QTD: [MessageHandler(filters.TEXT & ~filters.COMMAND, use_item_qtd)],
            USE_OLD_INFO_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_old_info_1)],
            USE_OLD_INFO_2: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_old_info_2)],
            USE_OLD_INFO_3: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_old_info_3)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_use),
            MessageHandler(filters.ALL & ~filters.COMMAND, invalid_input)
        ]
    )
