import os
import logging
import requests
from flask import Flask, request
import telebot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8714473531:AAHKRRN8TOSL2PSa2KphQiLXakW5VH2VaIg")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

def groq_request(prompt):
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
    bot.reply_to(message, 
        "👋 Привет! Я бот с поддержкой Groq AI.\n\n"
        "Используй /ask <вопрос> чтобы задать вопрос.")

@bot.message_handler(commands=['ask'])
def ask(message):
    question = message.text.replace('/ask', '', 1).strip()
    if not question:
        bot.reply_to(message, "Пожалуйста, напиши вопрос после команды /ask")
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    answer = groq_request(question)
    bot.reply_to(message, f"🤖 {answer}")

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def index():
    return "Bot is running! 🚀", 200

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"https://resume-bot-a82h.onrender.com/{BOT_TOKEN}")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
