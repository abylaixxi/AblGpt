from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters, CallbackContext
from openai import OpenAI
import asyncio
import os
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = f"https://ablgpt.onrender.com/{TELEGRAM_TOKEN}"  # Правильный Webhook URL

client = OpenAI(api_key=OPENAI_API_KEY)
CREATOR_NAME = "Абылай"

# Команда /start
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    await update.message.reply_text("Привет! Я AblGpt. Чем могу помочь?")

# Функция запроса к GPT
def get_gpt_response(user_message):
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": user_message}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка OpenAI: {str(e)}"

# Обработчик текстовых сообщений
async def handle_messages(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return  

    user_message = update.message.text
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    await asyncio.sleep(2)
    bot_reply = get_gpt_response(user_message)
    
    await update.message.reply_text(bot_reply, quote=True, parse_mode="MARKDOWN")

# Обработчик упоминания бота в группе
async def mention_handler(update: Update, context: CallbackContext):
    message = update.message
    bot_username = context.bot.username

    if f"@{bot_username}" in message.text:
        await message.reply_text(f"Привет, {message.from_user.first_name}! Ты меня звал? 😊")

# Inline-режим (@username в любом чате)
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
        # Webhook правильно настраивается на Render
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
