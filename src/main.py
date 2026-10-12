from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN, logger

# Importando o menu e o gerenciador de botões
from bot.handlers import show_main_menu, button_click_handler

from database.queries import get_or_create_user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /start, dá as boas-vindas e chama o menu principal."""
    user = update.effective_user
    
    # Registra ou busca o usuário no banco
    db_user = get_or_create_user(user.id, user.first_name)
    if db_user:
        logger.info(f"Usuário processado: {db_user.get('first_name', user.first_name)} (ID: {user.id})")
        
    await update.message.reply_text(
        f"Olá, {user.first_name}! 👋\n"
        "Bem-vindo ao Bot de Gerenciamento de Kit Técnico."
    )
    
    # Chama o menu logo em seguida
    await show_main_menu(update, context)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /menu abrindo o menu interativo."""
    await show_main_menu(update, context)

async def post_init(application):
    """Registra a lista de comandos no botão de menu do Telegram."""
    commands = [
        BotCommand("menu", "Abrir o menu principal"),
        BotCommand("start", "Reiniciar o atendimento"),
        BotCommand("ocr", "Ler texto ou etiqueta de foto"),
        BotCommand("cancel", "Cancelar operação atual")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands configurados com sucesso no menu do Telegram.")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não encontrado! Verifique seu arquivo .env.")
        return

    logger.info("Inicializando o bot...")
    
    # Constrói a aplicação do bot com o token e post_init
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Registra os comandos básicos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    
    # Registra o escutador de cliques nos botões (CallbackQueryHandler)
    # A ordem importa: primeiro os ConversationHandlers (mais específico), depois os callbacks genéricos
    from bot.conversations import get_add_item_conversation
    from bot.conversation_use import get_use_item_conversation
    from bot.conversation_rma import get_rma_conversation
    from bot.handlers import ocr_photo_command
    from telegram.ext import filters, MessageHandler
    app.add_handler(get_add_item_conversation())
    app.add_handler(get_use_item_conversation())
    app.add_handler(get_rma_conversation())
    app.add_handler(CommandHandler("ocr", ocr_photo_command))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, ocr_photo_command))
    app.add_handler(CallbackQueryHandler(button_click_handler))

    # Mantém o bot rodando e escutando mensagens
    logger.info("Bot online! Pressione Ctrl+C para desligar.")
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    app.run_polling()

if __name__ == '__main__':
    main()
