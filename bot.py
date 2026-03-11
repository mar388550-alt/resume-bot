import os
import re
import logging
from flask import Flask, request
import telebot
from groq import Groq
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-08-15-17"
TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-08-15-10"
SUPPORT_EMAIL = "marfor13365@gmail.com"

user_states = {}
user_data = {}

# ═══════════════════════════════════════
# TRANSLATIONS
# ═══════════════════════════════════════

T = {
    "ru": {
        "welcome": "👋 Привет!\n\nЯ помогу адаптировать твоё резюме под конкретную вакансию и оптимизировать под ATS-проверку работодателя.\n\nДля продолжения необходимо принять условия использования:",
        "choose_lang": "🌍 Выберите язык / Choose language:",
        "agreed": "✅ Условия приняты!\n\nЯ адаптирую твоё резюме:\n• Добавлю ключевые слова\n• Оптимизирую под ATS-проверку\n• Усилю соответствие требованиям",
        "main_menu": "🏠 Главное меню:",
        "btn_optimize": "🚀 Оптимизировать резюме",
        "btn_info": "ℹ️ Информация",
        "btn_support": "🆘 Поддержка",
        "btn_back": "◀️ Назад",
        "btn_back_menu": "◀️ Назад в меню",
        "btn_back_resume": "◀️ Ввести резюме заново",
        "btn_again": "🔄 Оптимизировать ещё раз",
        "btn_home": "🏠 Главное меню",
        "btn_policy": "📄 Политика",
        "btn_terms": "📋 Соглашение",
        "btn_agree": "✅ Принимаю условия",
        "btn_write_support": "✉️ Написать вопрос",
        "info_text": "ℹ️ Информация\n\n🤖 Бот оптимизации резюме\n\nАдаптирует резюме под конкретную вакансию с учётом ATS-систем.\n\n📧 Поддержка: {email}",
        "support_text": "🆘 Поддержка\n\n📧 Email: {email}\n\nИли напишите вопрос прямо здесь:",
        "write_support": "✉️ Напишите ваш вопрос:",
        "support_sent": "✅ Вопрос отправлен!\n\nОтветим на {email} или в боте. Спасибо!",
        "step1": "📄 Шаг 1 из 2 — Резюме\n\nОтправь своё резюме:\n• Вставь текст\n• Или прикрепи .txt файл",
        "step2": "✅ Резюме получено!\n\n📋 Шаг 2 из 2 — Вакансия\n\nТеперь вставь текст вакансии:",
        "processing": "⏳ Анализирую и оптимизирую резюме... 15-30 секунд.",
        "result_title": "✅ Оптимизированное резюме:",
        "result_next": "💡 Что хочешь сделать дальше?",
        "ad_label": "📢 Реклама",
        "need_agree": "⚠️ Сначала примите условия.",
        "too_short_resume": "⚠️ Текст слишком короткий. Отправь полное резюме.",
        "too_short_vacancy": "⚠️ Слишком короткий текст вакансии.",
        "no_links": "🔗 Ссылки не поддерживаются. Скопируй текст вакансии.",
        "only_txt": "⚠️ Только .txt формат. Скопируй текст и отправь как сообщение.",
        "error": "❌ Ошибка. Попробуй ещё раз.",
        "no_access": "⛔ Нет доступа.",
        "lang_changed": "✅ Язык изменён на Русский",
        "btn_lang": "🌍 Язык / Language",
    },
    "en": {
        "welcome": "👋 Hello!\n\nI'll help you adapt your resume for a specific job vacancy and optimize it for ATS screening.\n\nPlease accept the terms of use to continue:",
        "choose_lang": "🌍 Выберите язык / Choose language:",
        "agreed": "✅ Terms accepted!\n\nI will adapt your resume:\n• Add relevant keywords\n• Optimize for ATS screening\n• Strengthen requirement matching",
        "main_menu": "🏠 Main menu:",
        "btn_optimize": "🚀 Optimize resume",
        "btn_info": "ℹ️ Information",
        "btn_support": "🆘 Support",
        "btn_back": "◀️ Back",
        "btn_back_menu": "◀️ Back to menu",
        "btn_back_resume": "◀️ Re-enter resume",
        "btn_again": "🔄 Optimize again",
        "btn_home": "🏠 Main menu",
        "btn_policy": "📄 Privacy Policy",
        "btn_terms": "📋 Terms of Use",
        "btn_agree": "✅ I accept the terms",
        "btn_write_support": "✉️ Send a question",
        "info_text": "ℹ️ Information\n\n🤖 Resume Optimization Bot\n\nAdapts your resume to a specific vacancy considering ATS systems.\n\n📧 Support: {email}",
        "support_text": "🆘 Support\n\n📧 Email: {email}\n\nOr write your question right here:",
        "write_support": "✉️ Write your question:",
        "support_sent": "✅ Question sent!\n\nWe'll reply to {email} or directly in the bot. Thank you!",
        "step1": "📄 Step 1 of 2 — Resume\n\nSend your resume:\n• Paste the text\n• Or attach a .txt file",
        "step2": "✅ Resume received!\n\n📋 Step 2 of 2 — Vacancy\n\nNow paste the job vacancy text:",
        "processing": "⏳ Analyzing and optimizing resume... 15-30 seconds.",
        "result_title": "✅ Optimized resume:",
        "result_next": "💡 What would you like to do next?",
        "ad_label": "📢 Advertisement",
        "need_agree": "⚠️ Please accept the terms first.",
        "too_short_resume": "⚠️ Text too short. Send your full resume.",
        "too_short_vacancy": "⚠️ Job vacancy text is too short.",
        "no_links": "🔗 Links not supported. Copy the vacancy text and send it here.",
        "only_txt": "⚠️ Only .txt format. Copy the text and send it as a message.",
        "error": "❌ Error. Please try again.",
        "no_access": "⛔ No access.",
        "lang_changed": "✅ Language changed to English",
        "btn_lang": "🌍 Language / Язык",
    }
}

SYSTEM_PROMPT = {
    "ru": "Ты эксперт по оптимизации резюме. Адаптируй резюме под вакансию: добавь ключевые слова, оптимизируй под ATS, усиль соответствие. Сохрани реальные данные. В конце: процент соответствия, что усилено, чего не хватает. Отвечай на языке резюме.",
    "en": "You are a resume optimization expert. Adapt the resume to the vacancy: add keywords, optimize for ATS, strengthen match. Keep all real data. At the end: match percentage, what was strengthened, what is missing. Reply in the language of the resume."
}

# ═══════════════════════════════════════
# DATABASE (PostgreSQL)
# ═══════════════════════════════════════

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            agreed BOOLEAN DEFAULT FALSE,
            lang TEXT DEFAULT 'ru',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            user_id BIGINT PRIMARY KEY,
            message TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    defaults = [("price","0"),("subscription_days","30"),("ad_text",""),("ad_active","0")]
    for key, val in defaults:
        c.execute("INSERT INTO settings (key,value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING", (key, val))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def upsert_user(user_id, agreed=None, lang=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
    if agreed is not None:
        c.execute("UPDATE users SET agreed=%s WHERE user_id=%s", (agreed, user_id))
    if lang is not None:
        c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (lang, user_id))
    conn.commit()
    conn.close()

def get_user_lang(user_id):
    user = get_user(user_id)
    return user["lang"] if user else "ru"

def user_agreed(user_id):
    user = get_user(user_id)
    return user and user["agreed"]

def get_setting(key):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=%s", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO settings (key,value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=%s", (key, str(value), str(value)))
    conn.commit()
    conn.close()

def save_ticket(user_id, message):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO tickets (user_id,message) VALUES (%s,%s) ON CONFLICT (user_id) DO UPDATE SET message=%s, created_at=NOW()", (user_id, message, message))
    conn.commit()
    conn.close()

def get_tickets():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, message FROM tickets ORDER BY created_at DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_ticket(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM tickets WHERE user_id=%s", (user_id,))
    conn.commit()
    conn.close()

def count_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    n = c.fetchone()[0]
    conn.close()
    return n

def count_tickets():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tickets")
    n = c.fetchone()[0]
    conn.close()
    return n

init_db()

# ═══════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════

def t(user_id, key, **kwargs):
    lang = get_user_lang(user_id)
    text = T.get(lang, T["ru"]).get(key, T["ru"].get(key, key))
    return text.format(**kwargs) if kwargs else text

# ═══════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════

def lang_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.row(
        telebot.types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    return kb

def agree_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_agree"), callback_data="agree"))
    kb.row(
        telebot.types.InlineKeyboardButton(t(uid,"btn_policy"), url=PRIVACY_URL),
        telebot.types.InlineKeyboardButton(t(uid,"btn_terms"), url=TERMS_URL)
    )
    return kb

def main_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_optimize"), callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_info"), callback_data="info"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_support"), callback_data="support"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_lang"), callback_data="choose_lang"))
    return kb

def info_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.row(
        telebot.types.InlineKeyboardButton(t(uid,"btn_policy"), url=PRIVACY_URL),
        telebot.types.InlineKeyboardButton(t(uid,"btn_terms"), url=TERMS_URL)
    )
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_back"), callback_data="back_main"))
    return kb

def support_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_write_support"), callback_data="write_support"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_back"), callback_data="back_main"))
    return kb

def back_main_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_back_menu"), callback_data="back_main"))
    return kb

def back_resume_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_back_resume"), callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_home"), callback_data="back_main"))
    return kb

def result_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_again"), callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_home"), callback_data="back_main"))
    return kb

def admin_kb():
    price = get_setting("price")
    days = get_setting("subscription_days")
    ad_active = get_setting("ad_active") == "1"
    price_text = f"{price}₽" if price != "0" else "Бесплатно"
    ad_status = "✅ Вкл" if ad_active else "❌ Выкл"
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(f"💰 Цена: {price_text}", callback_data="admin_price"))
    kb.add(telebot.types.InlineKeyboardButton(f"📅 Дней подписки: {days}", callback_data="admin_days"))
    kb.add(telebot.types.InlineKeyboardButton(f"📢 Реклама: {ad_status}", callback_data="admin_ad_toggle"))
    kb.add(telebot.types.InlineKeyboardButton("✏️ Текст рекламы", callback_data="admin_ad_text"))
    kb.add(telebot.types.InlineKeyboardButton("🎫 Обращения", callback_data="admin_tickets"))
    kb.add(telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    return kb

# ═══════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════

@bot.message_handler(commands=["start"])
def start(message):
    cid = message.chat.id
    user_states[cid] = None
    upsert_user(cid)
    # Сначала выбор языка
    bot.send_message(cid, T["ru"]["choose_lang"], reply_markup=lang_kb())

@bot.message_handler(commands=["admin"])
def admin_cmd(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа.")
        return
    ad_text = get_setting("ad_text") or "не задан"
    bot.send_message(
        message.chat.id,
        f"⚙️ Админ панель\n\n"
        f"💰 Цена: {get_setting('price')}₽\n"
        f"📅 Дней подписки: {get_setting('subscription_days')}\n"
        f"📢 Реклама: {'Включена ✅' if get_setting('ad_active')=='1' else 'Выключена ❌'}\n"
        f"📝 Текст рекламы:\n{ad_text}\n\n"
        f"🎫 Обращений: {count_tickets()}\n"
        f"👥 Пользователей: {count_users()}",
        reply_markup=admin_kb()
    )

@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    cid = call.message.chat.id
    data = call.data
    logger.info(f"CB {data} from {cid}")

    # ── ЯЗЫК ──
    if data in ("lang_ru", "lang_en"):
        lang = data.split("_")[1]
        upsert_user(cid, lang=lang)
        try:
            bot.edit_message_text(T[lang]["choose_lang"], cid, call.message.message_id, reply_markup=lang_kb())
        except: pass
        bot.answer_callback_query(call.id, T[lang]["lang_changed"])
        # После выбора языка — проверяем согласие
        if user_agreed(cid):
            bot.send_message(cid, t(cid,"main_menu"), reply_markup=main_kb(cid))
        else:
            bot.send_message(cid, t(cid,"welcome"), reply_markup=agree_kb(cid))

    elif data == "choose_lang":
        try:
            bot.edit_message_text(t(cid,"choose_lang"), cid, call.message.message_id, reply_markup=lang_kb())
        except:
            bot.send_message(cid, t(cid,"choose_lang"), reply_markup=lang_kb())

    # ── AGREE ──
    elif data == "agree":
        upsert_user(cid, agreed=True)
        try:
            bot.edit_message_text(t(cid,"agreed"), cid, call.message.message_id, reply_markup=main_kb(cid))
        except:
            bot.send_message(cid, t(cid,"main_menu"), reply_markup=main_kb(cid))

    # ── MAIN ──
    elif data == "back_main":
        user_states[cid] = None
        try:
            bot.edit_message_text(t(cid,"main_menu"), cid, call.message.message_id, reply_markup=main_kb(cid))
        except:
            bot.send_message(cid, t(cid,"main_menu"), reply_markup=main_kb(cid))

    elif data == "info":
        try:
            bot.edit_message_text(t(cid,"info_text",email=SUPPORT_EMAIL), cid, call.message.message_id, reply_markup=info_kb(cid))
        except:
            bot.send_message(cid, t(cid,"info_text",email=SUPPORT_EMAIL), reply_markup=info_kb(cid))

    elif data == "support":
        try:
            bot.edit_message_text(t(cid,"support_text",email=SUPPORT_EMAIL), cid, call.message.message_id, reply_markup=support_kb(cid))
        except:
            bot.send_message(cid, t(cid,"support_text",email=SUPPORT_EMAIL), reply_markup=support_kb(cid))

    elif data == "write_support":
        user_states[cid] = "writing_support"
        bot.send_message(cid, t(cid,"write_support"), reply_markup=back_main_kb(cid))

    # ── FLOW ──
    elif data == "start_flow":
        if not user_agreed(cid):
            bot.send_message(cid, t(cid,"need_agree"), reply_markup=agree_kb(cid))
            try: bot.answer_callback_query(call.id)
            except: pass
            return
        user_states[cid] = "waiting_resume"
        user_data.setdefault(cid, {})["resume"] = ""
        bot.send_message(cid, t(cid,"step1"), reply_markup=back_main_kb(cid))

    # ── ADMIN ──
    elif data == "admin_price" and cid == ADMIN_ID:
        user_states[cid] = "admin_set_price"
        bot.send_message(cid, "💰 Введите цену в рублях (0 = бесплатно):", reply_markup=back_main_kb(cid))

    elif data == "admin_days" and cid == ADMIN_ID:
        user_states[cid] = "admin_set_days"
        bot.send_message(cid, f"📅 Сейчас: {get_setting('subscription_days')} дней\n\nВведите новое количество:", reply_markup=back_main_kb(cid))

    elif data == "admin_ad_toggle" and cid == ADMIN_ID:
        current = get_setting("ad_active") == "1"
        set_setting("ad_active", "0" if current else "1")
        status = "выключена ❌" if current else "включена ✅"
        bot.answer_callback_query(call.id, f"Реклама {status}")
        try:
            bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=admin_kb())
        except: pass

    elif data == "admin_ad_text" and cid == ADMIN_ID:
        user_states[cid] = "admin_set_ad"
        bot.send_message(cid, "✏️ Введите текст рекламы (показывается всем после результата):", reply_markup=back_main_kb(cid))

    elif data == "admin_tickets" and cid == ADMIN_ID:
        tickets = get_tickets()
        if not tickets:
            bot.send_message(cid, "🎫 Обращений нет.", reply_markup=admin_kb())
        else:
            bot.send_message(cid, f"🎫 Обращений: {len(tickets)}")
            for uid, msg in tickets:
                kb = telebot.types.InlineKeyboardMarkup()
                kb.add(telebot.types.InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{uid}"))
                bot.send_message(cid, f"От {uid}:\n\n{msg}", reply_markup=kb)

    elif data.startswith("reply_") and cid == ADMIN_ID:
        target_id = int(data.split("_")[1])
        user_states[cid] = f"replying_{target_id}"
        bot.send_message(cid, f"✉️ Введите ответ пользователю {target_id}:", reply_markup=back_main_kb(cid))

    elif data == "admin_stats" and cid == ADMIN_ID:
        bot.answer_callback_query(call.id, f"👥 {count_users()} польз. | 🎫 {count_tickets()} обращений")

    try:
        bot.answer_callback_query(call.id)
    except: pass


@bot.message_handler(content_types=["document"])
def doc_handler(message):
    cid = message.chat.id
    if user_states.get(cid) != "waiting_resume":
        return
    doc = message.document
    if not doc.file_name.endswith(".txt"):
        bot.send_message(cid, t(cid,"only_txt"))
        return
    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    user_data.setdefault(cid, {})["resume"] = downloaded.decode("utf-8")
    user_states[cid] = "waiting_vacancy"
    bot.send_message(cid, t(cid,"step2"), reply_markup=back_resume_kb(cid))


@bot.message_handler(content_types=["text"])
def text_handler(message):
    cid = message.chat.id
    text = message.text
    state = user_states.get(cid)

    if text.startswith("/"):
        return

    if state == "writing_support":
        save_ticket(cid, text)
        user_states[cid] = None
        bot.send_message(cid, t(cid,"support_sent",email=SUPPORT_EMAIL), reply_markup=main_kb(cid))
        try:
            bot.send_message(ADMIN_ID, f"🎫 Новое обращение от {cid}:\n\n{text}")
        except: pass
        return

    if state and state.startswith("replying_") and cid == ADMIN_ID:
        target_id = int(state.split("_")[1])
        try:
            bot.send_message(target_id, f"📨 Ответ от поддержки:\n\n{text}", reply_markup=main_kb(target_id))
            bot.send_message(cid, "✅ Ответ отправлен!", reply_markup=admin_kb())
            delete_ticket(target_id)
        except Exception as e:
            bot.send_message(cid, f"❌ Ошибка: {e}")
        user_states[cid] = None
        return

    if state == "admin_set_price" and cid == ADMIN_ID:
        try:
            set_setting("price", int(text))
            price_text = f"{text}₽" if text != "0" else "Бесплатно"
            bot.send_message(cid, f"✅ Цена: {price_text}", reply_markup=admin_kb())
        except:
            bot.send_message(cid, "❌ Введите число.")
        user_states[cid] = None
        return

    if state == "admin_set_days" and cid == ADMIN_ID:
        try:
            set_setting("subscription_days", int(text))
            bot.send_message(cid, f"✅ Дней подписки: {text}", reply_markup=admin_kb())
        except:
            bot.send_message(cid, "❌ Введите число.")
        user_states[cid] = None
        return

    if state == "admin_set_ad" and cid == ADMIN_ID:
        set_setting("ad_text", text)
        set_setting("ad_active", "1")
        bot.send_message(cid,
            f"✅ Реклама сохранена и включена!\n\nПревью:\n\n━━━━━━━━━━━━━━━\n📢 Реклама\n\n{text}\n━━━━━━━━━━━━━━━",
            reply_markup=admin_kb()
        )
        user_states[cid] = None
        return

    if not user_agreed(cid):
        bot.send_message(cid, t(cid,"need_agree"), reply_markup=agree_kb(cid))
        return

    if state == "waiting_resume":
        if len(text) < 50:
            bot.send_message(cid, t(cid,"too_short_resume"))
            return
        user_data.setdefault(cid, {})["resume"] = text
        user_states[cid] = "waiting_vacancy"
        bot.send_message(cid, t(cid,"step2"), reply_markup=back_resume_kb(cid))

    elif state == "waiting_vacancy":
        if re.match(r'https?://\S+', text.strip()):
            bot.send_message(cid, t(cid,"no_links"), reply_markup=back_resume_kb(cid))
            return
        if len(text) < 30:
            bot.send_message(cid, t(cid,"too_short_vacancy"))
            return

        resume = user_data.get(cid, {}).get("resume", "")
        user_states[cid] = None
        bot.send_message(cid, t(cid,"processing"))

        lang = get_user_lang(cid)
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT[lang]},
                    {"role": "user", "content": f"RESUME:\n{resume}\n\n{'='*40}\n\nVACANCY:\n{text}\n\nAdapt the resume."}
                ],
                max_tokens=3000,
                temperature=0.5
            )
            result = response.choices[0].message.content

            if len(result) > 3800:
                bot.send_message(cid, t(cid,"result_title"))
                for i in range(0, len(result), 3800):
                    bot.send_message(cid, result[i:i+3800])
            else:
                bot.send_message(cid, f"{t(cid,'result_title')}\n\n{result}")

            # Реклама для всех
            ad_active = get_setting("ad_active") == "1"
            ad_text = get_setting("ad_text")
            if ad_active and ad_text:
                bot.send_message(cid, f"━━━━━━━━━━━━━━━\n{t(cid,'ad_label')}\n\n{ad_text}\n━━━━━━━━━━━━━━━")

            bot.send_message(cid, t(cid,"result_next"), reply_markup=result_kb(cid))

        except Exception as e:
            logger.error(f"Groq error: {e}")
            bot.send_message(cid, t(cid,"error"), reply_markup=main_kb(cid))

    else:
        bot.send_message(cid, t(cid,"main_menu"), reply_markup=main_kb(cid))


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
