import os
import logging
from flask import Flask, request
import telebot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8714473531:AAHKRRN8TOSL2PSa2KphQiLXakW5VH2VaIg")
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Простейший обработчик
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "✅ Бот работает! Твоё сообщение: " + message.text)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def index():
    return "Минимальный бот запущен!", 200

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"https://resume-bot-a82h.onrender.com/{BOT_TOKEN}")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
