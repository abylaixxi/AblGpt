import os
import asyncio
from dotenv import load_dotenv
from uuid import uuid4
from openai import OpenAI
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    InlineQueryHandler, CallbackContext, filters
)
from telegram.constants import ChatAction

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = f"https://ablgpt.onrender.com/{TELEGRAM_TOKEN}"

# Подключение к OpenRouter через OpenAI SDK
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "https://ablgpt.onrender.com",
        "X-Title": "AblGpt"
    }
)

# История общения
user_chat_history = {}

# Начальное системное сообщение
SYSTEM_PROMPT = {
    "role": "system",
    "content": "Ты AblGpt — умный и дружелюбный Telegram-бот. Всегда представляйся как AblGpt, если спрашивают имя."
}

# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Я AblGpt. Чем могу помочь?")

# Получение ответа от GPT через OpenRouter
def get_gpt_response(user_id: int, user_message: str) -> str:
    try:
        user_chat_history.setdefault(user_id, [SYSTEM_PROMPT.copy()])
        user_chat_history[user_id].append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_chat_history[user_id],
            max_tokens=1000,
        )

        bot_reply = response.choices[0].message.content.strip()
        user_chat_history[user_id].append({"role": "assistant", "content": bot_reply})

        # Ограничим историю, чтобы она не стала слишком длинной
        if len(user_chat_history[user_id]) > 20:
            user_chat_history[user_id] = [SYSTEM_PROMPT.copy()] + user_chat_history[user_id][-18:]

        return bot_reply
    except Exception as e:
        return f"Ошибка GPT: {e}"

# Обработка обычных сообщений
async def handle_messages(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    user_message = update.message.text.strip()

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(1)

    bot_reply = await asyncio.to_thread(get_gpt_response, user_id, user_message)
    await update.message.reply_text(bot_reply)

# Обработка упоминаний в группах
async def mention_handler(update: Update, context: CallbackContext):
    message = update.message
    if not message or not message.text:
        return

    bot_username = context.bot.username
    if f"@{bot_username}" in message.text:
        await message.reply_text(f"Привет, {message.from_user.first_name}! Я AblGpt. Чем могу помочь?")

# Inline-режим
async def inline_query(update: Update, context: CallbackContext):
    query = update.inline_query.query
    if not query:
        return

    user_id = update.inline_query.from_user.id
    try:
        gpt_response = await asyncio.to_thread(get_gpt_response, user_id, query)
        result = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Ответ от AblGpt",
                input_message_content=InputTextMessageContent(gpt_response)
            )
        ]
        await update.inline_query.answer(result)
    except Exception as e:
        print(f"Ошибка inline: {e}")

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
        print(f"Ошибка запуска: {e}")

if __name__ == "__main__":
    main()
