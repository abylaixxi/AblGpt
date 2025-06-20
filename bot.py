from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters, CallbackContext
from openai import OpenAI
import asyncio
import os
from dotenv import load_dotenv
from uuid import uuid4

# Загрузка переменных окружения из .env файла
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = f"https://ablgpt.onrender.com/{TELEGRAM_TOKEN}"  # Webhook URL

client = OpenAI(api_key=OPENAI_API_KEY)
CREATOR_NAME = "Абылай"

# История чатов и ошибки
user_chat_history = {}
bot_errors = {}

# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Я AblGpt. Чем могу помочь?")

# Функция обращения к OpenAI
def get_gpt_response(user_message):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # заменили с gpt-4-turbo
            messages=[{"role": "user", "content": user_message}]
        )
        return response.choices[0].message.content
    except Exception as e:
        bot_errors[user_message] = str(e)
        return f"Ошибка OpenAI: {str(e)}"

# Обработка входящих сообщений
async def handle_messages(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    user_id = user.id
    user_message = update.message.text.lower().strip()

    if user_id not in user_chat_history:
        user_chat_history[user_id] = []

    last_bot_responses = user_chat_history[user_id][-5:]

    if len(user_message) < 3 and last_bot_responses and "Привет!" in last_bot_responses[-1]:
        return

    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    await asyncio.sleep(2)

    bot_reply = get_gpt_response(user_message)

    if bot_reply in last_bot_responses:
        bot_reply = f"Я уже так отвечал. Попробую по-другому:\n\n{get_gpt_response(user_message + ' (по-другому)')}"

    user_chat_history[user_id].append(bot_reply)

    await update.message.reply_text(
        bot_reply,
        parse_mode="MARKDOWN",
        reply_to_message_id=update.message.message_id
    )

# Обработка упоминания бота в группах
async def mention_handler(update: Update, context: CallbackContext):
    message = update.message
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

# Запуск бота
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
