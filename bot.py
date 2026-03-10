import os
import re
import logging
from flask import Flask, request
import telebot
from groq import Groq

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8714473531:AAHKRRN8TOSL2PSa2KphQiLXakW5VH2VaIg"
GROQ_API_KEY = "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"
ADMIN_ID = 8103332892
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "")

bot = telebot.TeleBot(BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

user_states = {}
user_data = {}

SYSTEM_PROMPT = """Ты — эксперт по карьерному консультированию и оптимизации резюме.

Твоя задача — адаптировать резюме кандидата под конкретную вакансию так, чтобы:

1. ATS-оптимизация — резюме прошло автоматическую проверку работодателя:
   - Включи ключевые слова и фразы из вакансии
   - Используй стандартные заголовки разделов
   - Релевантные навыки вынеси на первый план

2. Соответствие требованиям — выдели и усиль навыки важные для этой должности

3. Переформулировка опыта — адаптируй описание опыта под язык вакансии

4. Сохрани все реальные данные кандидата — ничего не выдумывай

5. В конце дай краткий анализ:
   - Примерный процент соответствия вакансии
   - Что было усилено
   - Чего не хватает (если есть)

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
    user_states[message.chat.id] = None
    user_data[message.chat.id] = {}
    bot.send_message(
        message.chat.id,
        "👋 Привет!\n\n"
        "Я адаптирую твоё резюме под конкретную вакансию:\n"
        "• Добавлю нужные ключевые слова\n"
        "• Оптимизирую под ATS-проверку работодателя\n"
        "• Усилю соответствие требованиям\n\n"
        "Нажми кнопку чтобы начать 👇",
        reply_markup=main_kb()
    )


@bot.message_handler(commands=["stats"])
def stats(message):
    if message.chat.id == ADMIN_ID:
        total = len(user_data)
        bot.send_message(message.chat.id, f"📊 Статистика:\nПользователей в сессии: {total}")
    else:
        bot.send_message(message.chat.id, "⛔ Нет доступа.")


@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    cid = call.message.chat.id
    if call.data == "how":
        bot.send_message(
            cid,
            "📖 Как работает бот:\n\n"
            "1️⃣ Отправляешь своё резюме (текст или .txt файл)\n"
            "2️⃣ Вставляешь текст вакансии\n"
            "3️⃣ ИИ адаптирует резюме под эту вакансию\n"
            "4️⃣ Получаешь готовое оптимизированное резюме\n\n"
            "✅ Резюме проходит ATS-фильтры работодателей\n"
            "✅ Ключевые слова из вакансии вписаны органично\n"
            "✅ Твои реальные данные сохраняются"
        )
    elif call.data == "start_flow":
        user_states[cid] = "waiting_resume"
        user_data[cid] = {}
        bot.send_message(
            cid,
            "📄 Шаг 1 из 2 — Резюме\n\n"
            "Отправь своё резюме:\n"
            "• Просто вставь текст резюме\n"
            "• Или прикрепи .txt файл",
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
        bot.send_message(cid, "⚠️ Пока поддерживается только .txt формат. Скопируй текст и отправь как сообщение.")
        return
    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    user_data[cid]["resume"] = downloaded.decode("utf-8")
    user_states[cid] = "waiting_vacancy"
    bot.send_message(
        cid,
        "✅ Резюме получено!\n\n"
        "📋 Шаг 2 из 2 — Вакансия\n\n"
        "Теперь вставь текст вакансии:",
        reply_markup=cancel_kb()
    )


@bot.message_handler(content_types=["text"])
def text_handler(message):
    cid = message.chat.id
    text = message.text
    state = user_states.get(cid)

    if text.startswith("/"):
        return

    if state == "waiting_resume":
        if len(text) < 50:
            bot.send_message(cid, "⚠️ Текст слишком короткий. Отправь полное резюме.")
            return
        user_data[cid]["resume"] = text
        user_states[cid] = "waiting_vacancy"
        bot.send_message(
            cid,
            "✅ Резюме получено!\n\n"
            "📋 Шаг 2 из 2 — Вакансия\n\n"
            "Теперь вставь текст вакансии:",
            reply_markup=cancel_kb()
        )

    elif state == "waiting_vacancy":
        if re.match(r'https?://\S+', text.strip()):
            bot.send_message(
                cid,
                "🔗 Автоматическое чтение ссылок недоступно.\n\n"
                "Скопируй текст вакансии со страницы и отправь сюда.",
                reply_markup=cancel_kb()
            )
            return
        if len(text) < 30:
            bot.send_message(cid, "⚠️ Текст вакансии слишком короткий. Вставь полный текст.")
            return

        resume = user_data[cid].get("resume", "")
        user_states[cid] = None

        bot.send_message(cid, "⏳ Анализирую и оптимизирую резюме... Это займёт 15-30 секунд.")

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": (
                        f"РЕЗЮМЕ КАНДИДАТА:\n{resume}\n\n"
                        f"{'='*50}\n\n"
                        f"ВАКАНСИЯ:\n{text}\n\n"
                        "Адаптируй резюме под эту вакансию."
                    )}
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

            bot.send_message(
                cid,
                "💡 Хочешь оптимизировать под другую вакансию?",
                reply_markup=main_kb()
            )

        except Exception as e:
            logging.error(f"Error: {e}")
            bot.send_message(cid, "❌ Ошибка. Попробуй ещё раз.", reply_markup=main_kb())

    else:
        bot.send_message(cid, "Нажми кнопку чтобы начать 👇", reply_markup=main_kb())


@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/")
def index():
    return "Bot is running!", 200


if __name__ == "__main__":
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL + "/" + BOT_TOKEN)
        logging.info(f"Webhook set to {WEBHOOK_URL}/{BOT_TOKEN}")
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
    else:
        logging.info("No RENDER_EXTERNAL_URL, starting polling...")
        bot.remove_webhook()
        bot.polling(none_stop=True)
