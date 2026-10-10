import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from database.queries import get_user, create_user, login_supabase, check_auth_session
from bot.handlers import show_main_menu, invalid_input

logger = logging.getLogger(__name__)

WAIT_FOR_EMAIL, WAIT_FOR_PASSWORD = range(2)

async def start_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /start. Verifica se já está autenticado."""
    user = update.effective_user
    
    # Se já houver sessão no bot (memória)
    if check_auth_session():
        db_user = get_user(user.id)
        if db_user:
            logger.info(f"Usuário logado: {db_user.get('first_name', user.first_name)} (ID: {user.id})")
            await update.message.reply_text(
                f"Olá, de volta, {user.first_name}! 👋\n"
                "Bem-vindo ao Bot de Gerenciamento de Kit Técnico."
            )
            await show_main_menu(update, context)
            return ConversationHandler.END
            
    # Primeiro acesso ou sem sessão
    await update.message.reply_text(
        f"Olá, {user.first_name}! 👋\n\n"
        "Este é um sistema restrito. Por favor, digite o seu *Email* do Supabase para se autenticar:",
        parse_mode="Markdown"
    )
    return WAIT_FOR_EMAIL

async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['auth_email'] = update.message.text.strip()
    await update.message.reply_text("Ótimo. Agora digite a sua *Senha*:")
    return WAIT_FOR_PASSWORD

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = context.user_data.get('auth_email')
    password = update.message.text.strip()
    user = update.effective_user
    
    # Tenta logar no Supabase
    success = login_supabase(email, password)
    
    if success:
        # Autenticado com sucesso, cadastra no banco customizado
        db_user = get_user(user.id)
        if not db_user:
            create_user(user.id, user.first_name)
            
        await update.message.reply_text("✅ *Autenticado com sucesso!* Conta registrada.", parse_mode="Markdown")
        await show_main_menu(update, context)
        context.user_data.pop('auth_email', None)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ *Credenciais incorretas ou erro de login.* Digite seu *Email* novamente para tentar de novo:", parse_mode="Markdown")
        return WAIT_FOR_EMAIL

def get_auth_conversation():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_auth)],
        states={
            WAIT_FOR_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)],
            WAIT_FOR_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)]
        },
        fallbacks=[
            CommandHandler("start", start_auth),
            MessageHandler(filters.ALL & ~filters.COMMAND, invalid_input)
        ]
    )
