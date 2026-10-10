from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

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
            InlineKeyboardButton("🚚 Devolver Matriz", callback_data="menu_rma")
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
                cat = item['category'].capitalize()
                specs = item['specs']
                qty = item['quantity']
                
                if cat.lower() in ["catraca", "leitor"]:
                    text += f"🔹 {cat} (NS: {specs.get('numero_serie', 'N/A')})\n"
                else:
                    text += f"🔹 {cat} - {specs.get('marca', specs.get('modelo', ''))} ({qty} unid.)\n"
            
            await query.message.reply_text(text, parse_mode='Markdown')
        
        # Voltar ao menu principal depois
        await show_main_menu(update, context)
    else:
        await query.message.reply_text("Opção desconhecida.")
