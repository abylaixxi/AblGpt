import os
import asyncio
import html
from uuid import uuid4
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    InlineQueryHandler, CallbackContext, filters
)
from telegram.constants import ChatAction
import openai

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
AIML_API_KEY = os.getenv("AIML_API_KEY")

# Указываем кастомный OpenAI endpoint (AIMLAPI)
openai.api_key = AIML_API_KEY
openai.base_url = "https://api.aimlapi.com/v1"

WEBHOOK_URL = f"https://ablgpt.onrender.com/{TELEGRAM_TOKEN}"  # Webhook URL

# История пользователей и ошибок
CREATOR_NAME = "Абылай"
user_chat_history = {}
bot_errors = {}

# Экранирование HTML
def escape_html(text):
    return html.escape(text)

# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Я AblGpt. Чем могу помочь?")

# Запрос к AIMLAPI (совместим с OpenAI API)
def get_gpt_response(user_message: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # или другой, доступный у тебя на AIMLAPI
            messages=[{"role": "user", "content": user_message}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        bot_errors[user_message] = str(e)
        return f"Ошибка GPT: {str(e)}"

# Ответ на текстовые сообщения
async def handle_messages(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    user_id = user.id
    user_message = update.message.text.strip()

    user_chat_history.setdefault(user_id, [])
    last_bot_responses = user_chat_history[user_id][-5:]

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(1)

    bot_reply = get_gpt_response(user_message)

    if bot_reply in last_bot_responses:
        bot_reply = f"Я уже так отвечал. Попробую по-другому:\n\n{get_gpt_response(user_message + ' (по-другому)')}"

    user_chat_history[user_id].append(bot_reply)

    escaped_reply = escape_html(bot_reply)

    await update.message.reply_text(
        escaped_reply,
        parse_mode="HTML",
        reply_to_message_id=update.message.message_id
    )

# Ответ на упоминание в группе
async def mention_handler(update: Update, context: CallbackContext):
    message = update.message
    if not message or not message.text:
        return

    bot_username = context.bot.username
    if f"@{bot_username}" in message.text:
        await message.reply_text(f"Привет, {message.from_user.first_name}! Ты меня звал? 😊")

# Inline-режим
async def inline_query(update: Update, context: CallbackContext):
    query = update.inline_query.query
    if not query:
        return

    try:
        gpt_response = await asyncio.to_thread(get_gpt_response, query)
        result = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Ответ от GPT",
                input_message_content=InputTextMessageContent(gpt_response)
            )
        ]
        await update.inline_query.answer(result)
    except Exception as e:
        print(f"Ошибка в inline_query: {e}")

# Запуск
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, mention_handler))
    app.add_handler(InlineQueryHandler(inline_query))

    print("Бот запущен...")

    try:
        app.run_webhook(
            listen="0.0.0.0",
            port=8443,
            url_path=TELEGRAM_TOKEN,
            webhook_url=WEBHOOK_URL
        )
    except Exception as e:
        print(f"Ошибка в работе бота: {e}")
    finally:
        print("Бот остановлен.")

if __name__ == "__main__":
    main()
