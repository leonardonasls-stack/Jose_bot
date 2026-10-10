import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from database.queries import get_or_create_user
from bot.handlers import show_main_menu, invalid_input
from config import ACCESS_CODE

logger = logging.getLogger(__name__)

WAIT_FOR_CODE = 0

async def start_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /start. Verifica se já está autenticado."""
    user = update.effective_user
    
    # Verifica se já há sessão no bot (memória)
    if context.user_data.get('authenticated'):
        db_user = get_or_create_user(user.id, user.first_name)
        if db_user:
            logger.info(f"Usuário logado: {db_user.get('first_name', user.first_name)} (ID: {user.id})")
            await update.message.reply_text(
                f"Olá de volta, {user.first_name}! 👋\n"
                "Bem-vindo ao Bot de Gerenciamento de Kit Técnico."
            )
            await show_main_menu(update, context)
            return ConversationHandler.END
            
    # Primeiro acesso ou sem sessão
    await update.message.reply_text(
        f"Olá, {user.first_name}! 👋\n\n"
        "Este é um sistema restrito. Por favor, digite o *Código de Acesso* para se autenticar:",
        parse_mode="Markdown"
    )
    return WAIT_FOR_CODE

async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user = update.effective_user
    
    if code == ACCESS_CODE:
        # Autenticado com sucesso, cadastra no banco
        db_user = get_or_create_user(user.id, user.first_name)
        context.user_data['authenticated'] = True
            
        await update.message.reply_text("✅ *Autenticado com sucesso!* Conta registrada.", parse_mode="Markdown")
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ *Código incorreto.* Digite o *Código de Acesso* novamente para tentar de novo:", parse_mode="Markdown")
        return WAIT_FOR_CODE

def get_auth_conversation():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_auth)],
        states={
            WAIT_FOR_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)]
        },
        fallbacks=[
            CommandHandler("start", start_auth),
            MessageHandler(filters.ALL & ~filters.COMMAND, invalid_input)
        ]
    )
