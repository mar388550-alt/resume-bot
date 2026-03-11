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
    kb.add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="back_main"))
    return kb


def back_resume_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("◀️ Назад — ввести резюме заново", callback_data="start_flow"))
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


@bot.message_handler(commands=["start"])
def start(message):
    cid = message.chat.id
    user_states[cid] = None
    user_data[cid] = {"agreed": False}
    bot.send_message(
        cid,
        "👋 Привет!\n\n"
        "Я помогу адаптировать твоё резюме под конкретную вакансию и оптимизировать под ATS-проверку работодателя.\n\n"
        "Для продолжения необходимо принять условия использования:",
        reply_markup=agree_kb()
    )


@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа.")
        return
    price_text = f"{admin_settings['price']}₽" if admin_settings["price"] > 0 else "Бесплатно"
    bot.send_message(
        message.chat.id,
        f"⚙️ Админ панель\n\n"
        f"💰 Цена: {price_text}\n"
        f"📢 Реклама: {'Включена' if admin_settings['ad_active'] else 'Выключена'}\n"
        f"🎫 Тикетов: {len(support_tickets)}\n"
        f"👥 Пользователей: {len(user_data)}",
        reply_markup=admin_kb()
    )


@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    cid = call.message.chat.id
    data = call.data
    logger.info(f"Callback {data} from {cid}")

    if data == "agree":
        user_data.setdefault(cid, {})["agreed"] = True
        try:
            bot.edit_message_text(
                "✅ Условия приняты!\n\n"
                "Я адаптирую твоё резюме под конкретную вакансию:\n"
                "• Добавлю ключевые слова\n"
                "• Оптимизирую под ATS-проверку\n"
                "• Усилю соответствие требованиям",
                cid, call.message.message_id,
                reply_markup=main_kb()
            )
        except:
            bot.send_message(cid, "🏠 Главное меню:", reply_markup=main_kb())

    elif data == "back_main":
        user_states[cid] = None
        try:
            bot.edit_message_text("🏠 Главное меню:", cid, call.message.message_id, reply_markup=main_kb())
        except:
            bot.send_message(cid, "🏠 Главное меню:", reply_markup=main_kb())

    elif data == "info":
        try:
            bot.edit_message_text(
                "ℹ️ Информация\n\n"
                "🤖 Бот оптимизации резюме\n\n"
                "Адаптирует резюме под конкретную вакансию с учётом ATS-систем.\n\n"
                f"📧 Поддержка: {SUPPORT_EMAIL}",
                cid, call.message.message_id,
                reply_markup=info_kb()
            )
        except:
            bot.send_message(cid, f"ℹ️ Информация\n\n📧 Поддержка: {SUPPORT_EMAIL}", reply_markup=info_kb())

    elif data == "support":
        try:
            bot.edit_message_text(
                f"🆘 Поддержка\n\n"
                f"📧 Email: {SUPPORT_EMAIL}\n\n"
                f"Или отправьте вопрос прямо здесь — мы ответим в ближайшее время:",
                cid, call.message.message_id,
                reply_markup=support_kb()
            )
        except:
            bot.send_message(cid, f"🆘 Поддержка\n\n📧 {SUPPORT_EMAIL}", reply_markup=support_kb())

    elif data == "write_support":
        user_states[cid] = "writing_support"
        bot.send_message(cid, "✉️ Напишите ваш вопрос:\n\nМы ответим на email или в боте.", reply_markup=back_main_kb())

    elif data == "start_flow":
        if not user_data.get(cid, {}).get("agreed"):
            bot.send_message(cid, "⚠️ Сначала примите условия.", reply_markup=agree_kb())
            bot.answer_callback_query(call.id)
            return
        user_states[cid] = "waiting_resume"
        user_data.setdefault(cid, {})["resume"] = ""
        bot.send_message(
            cid,
            "📄 Шаг 1 из 2 — Резюме\n\nОтправь своё резюме:\n• Вставь текст\n• Или прикрепи .txt файл",
            reply_markup=back_main_kb()
        )

    elif data == "admin_back":
        if cid == ADMIN_ID:
            price_text = f"{admin_settings['price']}₽" if admin_settings["price"] > 0 else "Бесплатно"
            try:
                bot.edit_message_text(
                    f"⚙️ Админ панель\n\n💰 Цена: {price_text}\n📢 Реклама: {'Вкл' if admin_settings['ad_active'] else 'Выкл'}",
                    cid, call.message.message_id, reply_markup=admin_kb()
                )
            except:
                pass

    elif data == "admin_price":
        if cid == ADMIN_ID:
            user_states[cid] = "admin_set_price"
            bot.send_message(cid, "💰 Введите цену в рублях (0 = бесплатно):", reply_markup=back_main_kb())

    elif data == "admin_ad":
        if cid == ADMIN_ID:
            text = admin_settings["ad_text"] or "Текст не задан"
            try:
                bot.edit_message_text(
                    f"📢 Управление рекламой\n\nТекущий текст:\n{text}",
                    cid, call.message.message_id, reply_markup=admin_ad_kb()
                )
            except:
                pass

    elif data == "admin_ad_toggle":
        if cid == ADMIN_ID:
            admin_settings["ad_active"] = not admin_settings["ad_active"]
            status = "включена ✅" if admin_settings["ad_active"] else "выключена ❌"
            bot.answer_callback_query(call.id, f"Реклама {status}")
            text = admin_settings["ad_text"] or "Текст не задан"
            try:
                bot.edit_message_text(
                    f"📢 Управление рекламой\n\nТекущий текст:\n{text}",
                    cid, call.message.message_id, reply_markup=admin_ad_kb()
                )
            except:
                pass

    elif data == "admin_ad_text":
        if cid == ADMIN_ID:
            user_states[cid] = "admin_set_ad"
            bot.send_message(cid, "✏️ Введите текст рекламы:", reply_markup=back_main_kb())

    elif data == "admin_tickets":
        if cid == ADMIN_ID:
            if not support_tickets:
                bot.send_message(cid, "🎫 Тикетов нет.", reply_markup=admin_kb())
            else:
                for uid, ticket in list(support_tickets.items())[-10:]:
                    kb = telebot.types.InlineKeyboardMarkup()
                    kb.add(telebot.types.InlineKeyboardButton(f"✉️ Ответить", callback_data=f"reply_{uid}"))
                    bot.send_message(cid, f"🎫 Тикет от {uid}:\n\n{ticket}", reply_markup=kb)

    elif data.startswith("reply_"):
        if cid == ADMIN_ID:
            target_id = int(data.split("_")[1])
            user_states[cid] = f"replying_{target_id}"
            bot.send_message(cid, f"✉️ Введите ответ пользователю {target_id}:", reply_markup=back_main_kb())

    elif data == "admin_stats":
        if cid == ADMIN_ID:
            bot.answer_callback_query(call.id, f"👥 {len(user_data)} пользователей, 🎫 {len(support_tickets)} тикетов")

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
    bot.send_message(cid, "✅ Резюме получено!\n\n📋 Шаг 2 из 2 — Вакансия\n\nТеперь вставь текст вакансии:", reply_markup=back_resume_kb())


@bot.message_handler(content_types=["text"])
def text_handler(message):
    cid = message.chat.id
    text = message.text
    state = user_states.get(cid)
    logger.info(f"Message from {cid}, state={state}")

    if text.startswith("/"):
        return

    # Поддержка
    if state == "writing_support":
        support_tickets[cid] = text
        user_states[cid] = None
        bot.send_message(cid,
            f"✅ Ваш вопрос отправлен!\n\n"
            f"Мы ответим на {SUPPORT_EMAIL} или напрямую в боте.\n\n"
            f"Спасибо за обращение!",
            reply_markup=main_kb()
        )
        if ADMIN_ID:
            bot.send_message(ADMIN_ID, f"🎫 Новый тикет от {cid}:\n\n{text}")
        return

    # Ответ админа
    if state and state.startswith("replying_"):
        if cid == ADMIN_ID:
            target_id = int(state.split("_")[1])
            try:
                bot.send_message(target_id, f"📨 Ответ от поддержки:\n\n{text}", reply_markup=main_kb())
                bot.send_message(cid, "✅ Ответ отправлен!", reply_markup=admin_kb())
                if target_id in support_tickets:
                    del support_tickets[target_id]
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
            bot.send_message(cid, "❌ Введите число.")
        user_states[cid] = None
        return

    # Установка рекламы
    if state == "admin_set_ad" and cid == ADMIN_ID:
        admin_settings["ad_text"] = text
        bot.send_message(cid, "✅ Текст рекламы сохранён!", reply_markup=admin_kb())
        user_states[cid] = None
        return

    # Основной флоу
    if not user_data.get(cid, {}).get("agreed"):
        bot.send_message(cid, "⚠️ Сначала примите условия.", reply_markup=agree_kb())
        return

    if state == "waiting_resume":
        if len(text) < 50:
            bot.send_message(cid, "⚠️ Текст слишком короткий. Отправь полное резюме.")
            return
        user_data[cid]["resume"] = text
        user_states[cid] = "waiting_vacancy"
        bot.send_message(cid, "✅ Резюме получено!\n\n📋 Шаг 2 из 2 — Вакансия\n\nТеперь вставь текст вакансии:", reply_markup=back_resume_kb())

    elif state == "waiting_vacancy":
        if re.match(r'https?://\S+', text.strip()):
            bot.send_message(cid, "🔗 Ссылки не поддерживаются.\nСкопируй текст вакансии и отправь сюда.", reply_markup=back_resume_kb())
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

            # Показать рекламу если активна
            if admin_settings["ad_active"] and admin_settings["ad_text"]:
                bot.send_message(cid, f"📢 {admin_settings['ad_text']}")

            bot.send_message(cid, "💡 Хочешь оптимизировать под другую вакансию?", reply_markup=main_kb())

        except Exception as e:
            logger.error(f"Groq error: {e}")
            bot.send_message(cid, "❌ Ошибка. Попробуй ещё раз.", reply_markup=main_kb())

    else:
        bot.send_message(cid, "🏠 Главное меню:", reply_markup=main_kb())


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
