import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, CommandHandler, filters

from database.queries import get_pending_returns, dispatch_returns, get_or_create_user
from bot.handlers import show_main_menu, invalid_input

logger = logging.getLogger(__name__)

(RMA_CONFIRM, RMA_DATE) = range(2)

async def start_rma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if user:
        get_or_create_user(user.id, user.first_name)

    user_id = str(user.id)
    pending_items = get_pending_returns(user_id)

    if not pending_items:
        text = "Você não possui nenhuma sucata aguardando despacho no momento. Seu porta-malas está zerado! 🎉"
        await query.edit_message_text(text)
        await show_main_menu(update, context)
        return ConversationHandler.END

    # Monta a listagem de sucatas
    text = f"Você tem *{len(pending_items)}* peças no porta-malas aguardando envio:\n\n"
    for item in pending_items:
        cat = item['category']
        specs = item.get('specs_removed', {})
        if cat in ["catraca", "leitor"]:
            text += f"- {cat.capitalize()} (NS: {specs.get('numero_serie', 'N/A')})\n"
        elif cat == "fonte":
            text += f"- Fonte (Marca: {specs.get('marca', 'N/A')})\n"
        elif cat == "antena":
            text += f"- Antena {specs.get('tipo', '')} (Modelo: {specs.get('modelo', 'N/A')})\n"
            
    text += "\nDeseja despachar *todas* as peças pendentes agora?"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Sim", callback_data="rma_sim"),
            InlineKeyboardButton("❌ Não", callback_data="rma_nao")
        ]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return RMA_CONFIRM

async def rma_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "rma_nao":
        await query.edit_message_text("Despacho cancelado.")
        await show_main_menu(update, context)
        return ConversationHandler.END
        
    # Se sim, pergunta a data
    keyboard = [[InlineKeyboardButton("Hoje", callback_data="hoje")]]
    await query.edit_message_text(
        "Legal! Qual a *Data do Despacho*?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return RMA_DATE

async def rma_date_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = datetime.datetime.now().strftime("%d/%m/%Y")
    return await finish_rma(update, context, date_str)

async def rma_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text
    return await finish_rma(update, context, date_str)

async def finish_rma(update: Update, context: ContextTypes.DEFAULT_TYPE, dispatch_date: str):
    user_id = str(update.effective_user.id)
    
    success = dispatch_returns(user_id, dispatch_date)
    
    if success:
        text = f"✅ *Despacho concluído!*\nTodas as sucatas foram marcadas como despachadas na data: {dispatch_date}.\nSeu porta-malas está limpo!"
    else:
        text = "❌ *Erro ao despachar sucatas.*"
        
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        
    await show_main_menu(update, context)
    return ConversationHandler.END

async def cancel_rma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("Operação cancelada.")
    elif update.message:
        await update.message.reply_text("Operação cancelada.")
    await show_main_menu(update, context)
    return ConversationHandler.END

def get_rma_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_rma, pattern="^menu_rma$")],
        states={
            RMA_CONFIRM: [CallbackQueryHandler(rma_confirm)],
            RMA_DATE: [
                CallbackQueryHandler(rma_date_btn, pattern="^hoje$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rma_date_text)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_rma),
            CommandHandler("menu", cancel_rma),
            CommandHandler("start", cancel_rma),
            CallbackQueryHandler(cancel_rma, pattern="^(cancel|rma_confirm_no)$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, invalid_input)
        ],
        allow_reentry=True
    )
