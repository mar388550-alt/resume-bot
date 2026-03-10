import os
import logging
import requests
from flask import Flask, request
import telebot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
BOT_TOKEN = "8714473531:AAHKRRN8TOSL2PSa2KphQiLXakW5VH2VaIg"
GROQ_API_KEY = "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"
WEBHOOK_URL = "https://resume-bot-a82h.onrender.com"
ADMIN_ID = 8103332892

# Проверка загрузки переменных
print(f"=== ЗАПУСК БОТА ===")
print(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"WEBHOOK_URL: {WEBHOOK_URL}")
print(f"ADMIN_ID: {ADMIN_ID}")

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

def groq_request(prompt):
    """Отправка запроса к Groq API"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000
    }
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return "Извините, произошла ошибка при обращении к ИИ."

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    bot.reply_to(message, 
        "👋 Привет! Я бот с поддержкой Groq AI.\n\n"
        "Доступные команды:\n"
        "/ask <вопрос> - задать вопрос ИИ\n"
        "/admin - панель администратора"
    )

@bot.message_handler(commands=['ask'])
def ask(message):
    """Обработчик команды /ask"""
    question = message.text.replace('/ask', '', 1).strip()
    if not question:
        bot.reply_to(message, "Пожалуйста, напиши вопрос после команды /ask\nНапример: /ask Что такое резюме?")
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    answer = groq_request(question)
    bot.reply_to(message, f"🤖 {answer}")

@bot.message_handler(commands=['admin'])
def admin(message):
    """Админ-панель (только для администратора)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ У вас нет прав администратора")
        return
    
    bot.reply_to(message,
        "🔧 Панель администратора\n\n"
        "Статистика:\n"
        f"• Ваш ID: {message.from_user.id}\n"
        f"• Бот активен: ✅"
    )

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Обработчик вебхуков от Telegram"""
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def index():
    """Главная страница"""
    return "Bot is running! 🚀", 200

@app.route('/health')
def health():
    """Проверка здоровья"""
    return "OK", 200

if __name__ == '__main__':
    # Удаляем старый вебхук и устанавливаем новый
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print(f"Webhook установлен на: {WEBHOOK_URL}/{BOT_TOKEN}")
    
    # Запускаем Flask-приложение
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
