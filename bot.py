import os
import telegram
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from flask import Flask, request
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = "8714473531:AAEBWs9cavggug5daa0-HGbJ8TI6tzo64zU"

bot = telegram.Bot(token=BOT_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

def start(update, context):
    update.message.reply_text('Привет! Я бот для резюме. Отправь мне своё резюме в формате PDF.')

def handle_document(update, context):
    update.message.reply_text('Резюме получено! Я передал его HR-специалисту.')

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.document, handle_document))

@app.route('/')
def index():
    return "Бот работает!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
