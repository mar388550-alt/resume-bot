import os
import re
import logging
from flask import Flask, request
import telebot
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

user_states = {}
user_data = {}

SYSTEM_PROMPT = """Ты — эксперт по карьерному консультированию и оптимизации резюме.
Адаптируй резюме под вакансию: добавь ключевые слова, оптимизируй под ATS, усиль соответствие.
Сохрани реальные данные. В конце дай анализ: процент соответствия, что усилено, чего не хватает.
Отвечай на том языке на котором написано резюме."""


def main_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Начать оптимизацию", callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton("❓ Как это работает", callback_data="how"))
    return kb


def cancel_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


@bot.message_handler(commands=["start"])
def start(message):
    logger.info(f"Start from {message.chat.id}")
    user_states[message.chat.id] = None
    user_data[message.chat.id] = {}
    bot.send_message(
        message.chat.id,
        "👋 Привет!\n\nЯ адаптирую твоё резюме под конкретную вакансию и оптимизирую под ATS-проверку.\n\nНажми кнопку чтобы начать 👇",
        reply_markup=main_kb()
    )


@bot.message_handler(commands=["stats"])
def stats(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, f"📊 Пользователей: {len(user_data)}")
    else:
        bot.send_message(message.chat.id, "⛔ Нет доступа.")


@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    cid = call.message.chat.id
    logger.info(f"Callback {call.data} from {cid}")
    if call.data == "how":
        bot.send_message(cid,
            "📖 Как работает:\n\n"
            "1️⃣ Отправляешь резюме (текст или .txt)\n"
            "2️⃣ Вставляешь текст вакансии\n"
            "3️⃣ ИИ адаптирует резюме\n"
            "4️⃣ Получаешь оптимизированное резюме\n\n"
            "✅ Проходит ATS-фильтры\n"
            "✅ Ключевые слова из вакансии\n"
            "✅ Реальные данные сохраняются"
        )
    elif call.data == "start_flow":
        user_states[cid] = "waiting_resume"
        user_data[cid] = {}
        bot.send_message(cid,
            "📄 Шаг 1 из 2 — Резюме\n\nОтправь своё резюме текстом или .txt файлом:",
            reply_markup=cancel_kb()
        )
    elif call.data == "cancel":
        user_states[cid] = None
        user_data[cid] = {}
        bot.send_message(cid, "❌ Отменено.", reply_markup=main_kb())
    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=["document"])
def doc_handler(message):
    cid = message.chat.id
    if user_states.get(cid) != "waiting_resume":
        return
    doc = message.document
    if not doc.file_name.endswith(".txt"):
        bot.send_message(cid, "⚠️ Только .txt формат. Скопируй текст и отправь как сообщение.")
        return
    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    user_data[cid]["resume"] = downloaded.decode("utf-8")
    user_states[cid] = "waiting_vacancy"
    bot.send_message(cid, "✅ Резюме получено!\n\n📋 Шаг 2 из 2\n\nТеперь вставь текст вакансии:", reply_markup=cancel_kb())


@bot.message_handler(content_types=["text"])
def text_handler(message):
    cid = message.chat.id
    text = message.text
    state = user_states.get(cid)
    logger.info(f"Message from {cid}, state={state}, text={text[:30]}")

    if text.startswith("/"):
        return

    if state == "waiting_resume":
        if len(text) < 50:
            bot.send_message(cid, "⚠️ Текст слишком короткий. Отправь полное резюме.")
            return
        user_data[cid]["resume"] = text
        user_states[cid] = "waiting_vacancy"
        bot.send_message(cid, "✅ Резюме получено!\n\n📋 Шаг 2 из 2\n\nТеперь вставь текст вакансии:", reply_markup=cancel_kb())

    elif state == "waiting_vacancy":
        if re.match(r'https?://\S+', text.strip()):
            bot.send_message(cid, "🔗 Ссылки не поддерживаются.\nСкопируй текст вакансии и отправь сюда.", reply_markup=cancel_kb())
            return
        if len(text) < 30:
            bot.send_message(cid, "⚠️ Текст вакансии слишком короткий.")
            return

        resume = user_data[cid].get("resume", "")
        user_states[cid] = None
        bot.send_message(cid, "⏳ Анализирую и оптимизирую резюме... 15-30 секунд.")

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"РЕЗЮМЕ:\n{resume}\n\n{'='*40}\n\nВАКАНСИЯ:\n{text}\n\nАдаптируй резюме."}
                ],
                max_tokens=3000,
                temperature=0.5
            )
            result = response.choices[0].message.content
            full = "✅ Оптимизированное резюме:\n\n" + result
            if len(full) > 4000:
                bot.send_message(cid, "✅ Оптимизированное резюме:")
                for i in range(0, len(result), 4000):
                    bot.send_message(cid, result[i:i+4000])
            else:
                bot.send_message(cid, full)
            bot.send_message(cid, "💡 Хочешь оптимизировать под другую вакансию?", reply_markup=main_kb())

        except Exception as e:
            logger.error(f"Groq error: {e}")
            bot.send_message(cid, "❌ Ошибка. Попробуй ещё раз.", reply_markup=main_kb())

    else:
        bot.send_message(cid, "Нажми кнопку чтобы начать 👇", reply_markup=main_kb())


@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("utf-8")
        logger.info(f"Webhook received: {json_str[:100]}")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return "OK", 200


@app.route("/")
def index():
    return "Bot is running!", 200
