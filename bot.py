from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from openai import OpenAI
import psycopg2
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_PARAMS = {
    "dbname": "AblGpt",
    "user": "postgres",
    "host": "localhost",
    "port": "5432"
}

client = OpenAI(api_key=OPENAI_API_KEY)
CREATOR_NAME = "Абылай"

# Функция для сохранения сообщений в БД
def save_message(user_id, username, message, role):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (user_id, username, message, role) VALUES (%s, %s, %s, %s)",
                    (user_id, username, message, role))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при сохранении сообщения: {e}")

# Функция загрузки истории сообщений из БД
def get_chat_history(user_id, limit=5):
    """Загружает последние `limit` сообщений пользователя из базы данных."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("""
            SELECT role, message FROM messages 
            WHERE user_id = %s 
            ORDER BY id DESC 
            LIMIT %s
        """, (user_id, limit))
        messages = cur.fetchall()
        cur.close()
        conn.close()

        # Преобразуем историю в формат, понятный OpenAI
        history = [{"role": role, "content": text} for role, text in reversed(messages)]
        return history
    except Exception as e:
        print(f"Ошибка при загрузке истории чата: {e}")
        return []

# Очистка старых сообщений (если их становится слишком много)
def cleanup_old_messages(user_id, max_messages=50):
    """Удаляет самые старые сообщения, если их больше `max_messages`."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM messages 
            WHERE user_id = %s 
            AND id NOT IN (
                SELECT id FROM messages 
                WHERE user_id = %s 
                ORDER BY id DESC 
                LIMIT %s
            )
        """, (user_id, user_id, max_messages))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при очистке сообщений: {e}")

# Команда /start
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    save_message(user.id, user.username, "Команда /start", "user")
    await update.message.reply_text("Привет! Я AblGpt. Чем могу помочь?")

# Функция запроса к GPT
def get_gpt_response(user_id, user_message):
    try:
        chat_history = get_chat_history(user_id)  # Загружаем историю чата
        chat_history.append({"role": "user", "content": user_message})  # Добавляем новый вопрос

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=chat_history  # Отправляем историю вместе с новым вопросом
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка OpenAI: {str(e)}"

# Обработчик текстовых сообщений
async def handle_messages(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return  # Игнорируем сообщения без текста (например, фото, видео)

    user = update.message.from_user
    user_message = update.message.text
    save_message(user.id, user.username, user_message, "user")
    cleanup_old_messages(user.id)  # Очищаем старые сообщения, если их стало слишком много

    if CREATOR_NAME.lower() in user_message.lower():
        bot_reply = f"{CREATOR_NAME} — мой создатель! ❤️"
    else:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
        await asyncio.sleep(2)
        bot_reply = get_gpt_response(user.id, user_message)  # Учитываем историю чата

    save_message(user.id, "AblGpt", bot_reply, "assistant")
    await update.message.reply_text(bot_reply, quote=True, parse_mode="MARKDOWN")

# Запуск бота
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("Бот запущен...")

    try:
        app.run_polling()
    except Exception as e:
        print(f"Ошибка в работе бота: {e}")
    finally:
        print("Бот остановлен.")

if __name__ == "__main__":
    main()
