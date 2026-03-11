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

admin_settings = {
    "price": 0,
    "ad_text": "",
    "ad_active": False
}

support_tickets = {}

PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-08-15-17"
TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-08-15-10"
SUPPORT_EMAIL = "marfor13365@gmail.com"

SYSTEM_PROMPT = """Ты эксперт по оптимизации резюме. Адаптируй резюме под вакансию: добавь ключевые слова, оптимизируй под ATS, усиль соответствие. Сохрани реальные данные. В конце: процент соответствия, что усилено, чего не хватает. Отвечай на языке резюме."""


# ── КЛАВИАТУРЫ ──────────────────────────────────────────

def agree_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("✅ Принимаю условия", callback_data="agree"))
    kb.row(
        telebot.types.InlineKeyboardButton("📄 Политика", url=PRIVACY_URL),
        telebot.types.InlineKeyboardButton("📋 Соглашение", url=TERMS_URL)
    )
    return kb

def main_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Оптимизировать резюме", callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton("ℹ️ Информация", callback_data="info"))
    kb.add(telebot.types.InlineKeyboardButton("🆘 Поддержка", callback_data="support"))
    return kb

def info_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.row(
        telebot.types.InlineKeyboardButton("📄 Политика", url=PRIVACY_URL),
        telebot.types.InlineKeyboardButton("📋 Соглашение", url=TERMS_URL)
    )
    kb.add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="back_main"))
    return kb

def support_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("✉️ Отправить вопрос", callback_data="write_support"))
    kb.add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="back_main"))
    return kb

def back_main_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("◀️ Назад в меню", callback_data="back_main"))
    return kb

def back_resume_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("◀️ Ввести резюме заново", callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_main"))
    return kb

def result_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🔄 Оптимизировать ещё раз", callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_main"))
    return kb

def admin_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("💰 Установить цену", callback_data="admin_price"))
    kb.add(telebot.types.InlineKeyboardButton("📢 Управление рекламой", callback_data="admin_ad"))
    kb.add(telebot.types.InlineKeyboardButton("🎫 Тикеты поддержки", callback_data="admin_tickets"))
    kb.add(telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    return kb

def admin_ad_kb():
    status = "✅ Вкл" if admin_settings["ad_active"] else "❌ Выкл"
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(f"Реклама: {status}", callback_data="admin_ad_toggle"))
    kb.add(telebot.types.InlineKeyboardButton("✏️ Изменить текст", callback_data="admin_ad_text"))
    kb.add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
    return kb


# ── КОМАНДЫ ─────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def start(message):
    cid = message.chat.id
    user_states[cid] = None
    user_data[cid] = {"agreed": False}
    bot.send_message(
        cid,
        "👋 Привет!\n\n"
        "Я адаптирую твоё резюме под конкретную вакансию и оптимизирую под ATS-проверку работодателя.\n\n"
        "Для продолжения необходимо принять условия использования:",
        reply_markup=agree_kb()
    )

@bot.message_handler(commands=["admin"])
def admin_cmd(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа.")
        return
    price_text = f"{admin_settings['price']}₽" if admin_settings["price"] > 0 else "Бесплатно"
    ad_status = "Включена ✅" if admin_settings["ad_active"] else "Выключена ❌"
    ad_text = admin_settings["ad_text"] or "не задан"
    bot.send_message(
        message.chat.id,
        f"⚙️ Админ панель\n\n"
        f"💰 Цена: {price_text}\n"
        f"📢 Реклама: {ad_status}\n"
        f"📝 Текст: {ad_text}\n"
        f"🎫 Тикетов: {len(support_tickets)}\n"
        f"👥 Пользователей: {len(user_data)}",
        reply_markup=admin_kb()
    )


# ── CALLBACK ─────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    cid = call.message.chat.id
    data = call.data

    # AGREE
    if data == "agree":
        user_data.setdefault(cid, {})["agreed"] = True
        try:
            bot.edit_message_text(
                "✅ Условия приняты!\n\n"
                "Выбери действие:",
                cid, call.message.message_id,
                reply_markup=main_kb()
            )
        except:
            bot.send_message(cid, "🏠 Главное меню:", reply_markup=main_kb())

    # ГЛАВНОЕ МЕНЮ
    elif data == "back_main":
        user_states[cid] = None
        try:
            bot.edit_message_text("🏠 Главное меню:", cid, call.message.message_id, reply_markup=main_kb())
        except:
            bot.send_message(cid, "🏠 Главное меню:", reply_markup=main_kb())

    # ИНФОРМАЦИЯ
    elif data == "info":
        try:
            bot.edit_message_text(
                f"ℹ️ Информация\n\n"
                f"🤖 Бот оптимизации резюме\n\n"
                f"Адаптирует резюме под вакансию с учётом ATS-систем.\n\n"
                f"📧 Поддержка: {SUPPORT_EMAIL}",
                cid, call.message.message_id,
                reply_markup=info_kb()
            )
        except:
            bot.send_message(cid, f"ℹ️ Поддержка: {SUPPORT_EMAIL}", reply_markup=info_kb())

    # ПОДДЕРЖКА
    elif data == "support":
        try:
            bot.edit_message_text(
                f"🆘 Поддержка\n\n"
                f"📧 Email: {SUPPORT_EMAIL}\n\n"
                f"Или отправьте вопрос прямо здесь:",
                cid, call.message.message_id,
                reply_markup=support_kb()
            )
        except:
            bot.send_message(cid, f"🆘 {SUPPORT_EMAIL}", reply_markup=support_kb())

    elif data == "write_support":
        user_states[cid] = "writing_support"
        bot.send_message(cid, "✉️ Напишите ваш вопрос:", reply_markup=back_main_kb())

    # СТАРТ ФЛОУ
    elif data == "start_flow":
        if not user_data.get(cid, {}).get("agreed"):
            bot.send_message(cid, "⚠️ Сначала примите условия.", reply_markup=agree_kb())
            try: bot.answer_callback_query(call.id)
            except: pass
            return
        user_states[cid] = "waiting_resume"
        user_data.setdefault(cid, {})["resume"] = ""
        bot.send_message(
            cid,
            "📄 Шаг 1 из 2 — Резюме\n\n"
            "Отправь своё резюме:\n• Вставь текст\n• Или прикрепи .txt файл",
            reply_markup=back_main_kb()
        )

    # АДМИН — НАЗАД
    elif data == "admin_back":
        if cid == ADMIN_ID:
            price_text = f"{admin_settings['price']}₽" if admin_settings["price"] > 0 else "Бесплатно"
            ad_status = "Включена ✅" if admin_settings["ad_active"] else "Выключена ❌"
            try:
                bot.edit_message_text(
                    f"⚙️ Админ панель\n\n"
                    f"💰 Цена: {price_text}\n"
                    f"📢 Реклама: {ad_status}\n"
                    f"📝 Текст: {admin_settings['ad_text'] or 'не задан'}",
                    cid, call.message.message_id,
                    reply_markup=admin_kb()
                )
            except:
                pass

    # АДМИН — ЦЕНА
    elif data == "admin_price":
        if cid == ADMIN_ID:
            user_states[cid] = "admin_set_price"
            bot.send_message(cid, "💰 Введите цену в рублях (0 = бесплатно):", reply_markup=back_main_kb())

    # АДМИН — РЕКЛАМА
    elif data == "admin_ad":
        if cid == ADMIN_ID:
            ad_text = admin_settings["ad_text"] or "Текст не задан"
            try:
                bot.edit_message_text(
                    f"📢 Управление рекламой\n\nТекущий текст:\n{ad_text}",
                    cid, call.message.message_id,
                    reply_markup=admin_ad_kb()
                )
            except:
                bot.send_message(cid, f"📢 Реклама\n\n{ad_text}", reply_markup=admin_ad_kb())

    elif data == "admin_ad_toggle":
        if cid == ADMIN_ID:
            admin_settings["ad_active"] = not admin_settings["ad_active"]
            status = "включена ✅" if admin_settings["ad_active"] else "выключена ❌"
            try: bot.answer_callback_query(call.id, f"Реклама {status}")
            except: pass
            ad_text = admin_settings["ad_text"] or "Текст не задан"
            try:
                bot.edit_message_text(
                    f"📢 Управление рекламой\n\nТекущий текст:\n{ad_text}",
                    cid, call.message.message_id,
                    reply_markup=admin_ad_kb()
                )
            except:
                pass
            return

    elif data == "admin_ad_text":
        if cid == ADMIN_ID:
            user_states[cid] = "admin_set_ad"
            bot.send_message(cid, "✏️ Введите текст рекламы (появится после каждого результата):", reply_markup=back_main_kb())

    # АДМИН — ТИКЕТЫ
    elif data == "admin_tickets":
        if cid == ADMIN_ID:
            if not support_tickets:
                bot.send_message(cid, "🎫 Тикетов нет.", reply_markup=admin_kb())
            else:
                for uid, ticket in list(support_tickets.items())[-10:]:
                    kb = telebot.types.InlineKeyboardMarkup()
                    kb.add(telebot.types.InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{uid}"))
                    bot.send_message(cid, f"🎫 Тикет от {uid}:\n\n{ticket}", reply_markup=kb)

    elif data.startswith("reply_"):
        if cid == ADMIN_ID:
            target_id = int(data.split("_")[1])
            user_states[cid] = f"replying_{target_id}"
            bot.send_message(cid, f"✉️ Введите ответ пользователю {target_id}:", reply_markup=back_main_kb())

    # АДМИН — СТАТИСТИКА
    elif data == "admin_stats":
        if cid == ADMIN_ID:
            try:
                bot.answer_callback_query(call.id, f"👥 {len(user_data)} польз. | 🎫 {len(support_tickets)} тикетов")
            except:
                pass
            return

    try:
        bot.answer_callback_query(call.id)
    except:
        pass


# ── ДОКУМЕНТЫ ────────────────────────────────────────────

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
    bot.send_message(cid,
        "✅ Резюме получено!\n\n📋 Шаг 2 из 2 — Вакансия\n\nТеперь вставь текст вакансии:",
        reply_markup=back_resume_kb()
    )


# ── ТЕКСТ ────────────────────────────────────────────────

@bot.message_handler(content_types=["text"])
def text_handler(message):
    cid = message.chat.id
    text = message.text
    state = user_states.get(cid)

    if text.startswith("/"):
        return

    # Поддержка
    if state == "writing_support":
        support_tickets[cid] = text
        user_states[cid] = None
        bot.send_message(cid,
            f"✅ Вопрос отправлен!\n\nОтветим на {SUPPORT_EMAIL} или напрямую в боте.",
            reply_markup=main_kb()
        )
        if ADMIN_ID:
            try:
                bot.send_message(ADMIN_ID, f"🎫 Новый тикет от {cid}:\n\n{text}")
            except:
                pass
        return

    # Ответ админа пользователю
    if state and state.startswith("replying_") and cid == ADMIN_ID:
        target_id = int(state.split("_")[1])
        try:
            bot.send_message(target_id, f"📨 Ответ от поддержки:\n\n{text}", reply_markup=main_kb())
            bot.send_message(cid, "✅ Ответ отправлен!", reply_markup=admin_kb())
            support_tickets.pop(target_id, None)
        except Exception as e:
            bot.send_message(cid, f"❌ Ошибка: {e}")
        user_states[cid] = None
        return

    # Установка цены
    if state == "admin_set_price" and cid == ADMIN_ID:
        try:
            price = int(text)
            admin_settings["price"] = price
            price_text = f"{price}₽" if price > 0 else "Бесплатно"
            bot.send_message(cid, f"✅ Цена установлена: {price_text}", reply_markup=admin_kb())
        except:
            bot.send_message(cid, "❌ Введите число.", reply_markup=admin_kb())
        user_states[cid] = None
        return

    # Установка текста рекламы
    if state == "admin_set_ad" and cid == ADMIN_ID:
        admin_settings["ad_text"] = text
        admin_settings["ad_active"] = True
        bot.send_message(cid,
            f"✅ Текст рекламы сохранён и включён!\n\nПредпросмотр:\n\n📢 {text}",
            reply_markup=admin_kb()
        )
        user_states[cid] = None
        return

    # Проверка согласия
    if not user_data.get(cid, {}).get("agreed"):
        bot.send_message(cid, "⚠️ Сначала примите условия использования.", reply_markup=agree_kb())
        return

    # Резюме
    if state == "waiting_resume":
        if len(text) < 50:
            bot.send_message(cid, "⚠️ Текст слишком короткий. Отправь полное резюме.")
            return
        user_data[cid]["resume"] = text
        user_states[cid] = "waiting_vacancy"
        bot.send_message(cid,
            "✅ Резюме получено!\n\n📋 Шаг 2 из 2 — Вакансия\n\nТеперь вставь текст вакансии:",
            reply_markup=back_resume_kb()
        )

    # Вакансия
    elif state == "waiting_vacancy":
        if re.match(r'https?://\S+', text.strip()):
            bot.send_message(cid, "🔗 Ссылки не поддерживаются.\nСкопируй текст вакансии и отправь сюда.", reply_markup=back_resume_kb())
            return
        if len(text) < 30:
            bot.send_message(cid, "⚠️ Текст вакансии слишком короткий.", reply_markup=back_resume_kb())
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

            # Отправляем результат
            if len(result) > 3800:
                bot.send_message(cid, "✅ Оптимизированное резюме:")
                for i in range(0, len(result), 3800):
                    bot.send_message(cid, result[i:i+3800])
            else:
                bot.send_message(cid, f"✅ Оптимизированное резюме:\n\n{result}")

            # Реклама после результата
            if admin_settings["ad_active"] and admin_settings["ad_text"]:
                bot.send_message(cid, f"📢 {admin_settings['ad_text']}")

            # Кнопки назад после результата
            bot.send_message(cid, "💡 Что хочешь сделать дальше?", reply_markup=result_kb())

        except Exception as e:
            logger.error(f"Groq error: {e}")
            bot.send_message(cid, "❌ Ошибка при обработке. Попробуй ещё раз.", reply_markup=main_kb())

    else:
        bot.send_message(cid, "🏠 Главное меню:", reply_markup=main_kb())


# ── WEBHOOK ──────────────────────────────────────────────

@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running!", 200
