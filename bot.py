import os
import re
import logging
import uuid
import hmac
import hashlib
import requests
from datetime import datetime, timedelta
from flask import Flask, request
import telebot
from groq import Groq
import psycopg2
from psycopg2.extras import RealDictCursor

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")

# Платежи Platiga
MERCHANT_ID = os.getenv("MERCHANT_ID")               # Ваш Merchant ID (выдаст менеджер)
API_SECRET = os.getenv("API_SECRET")                 # Секретный ключ (выдаст менеджер)
PLATIGA_API_URL = os.getenv("PLATIGA_API_URL", "https://app.platega.io/transaction/process")
# URL вебхука – можно задать через переменную окружения, иначе используется значение по умолчанию
PLATIGA_WEBHOOK_URL = os.getenv("PLATIGA_WEBHOOK_URL", "https://resume-bot-a82h.onrender.com/webhook/platiga")

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-08-15-17"
TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-08-15-10"
SUPPORT_EMAIL = "marfor13365@gmail.com"

user_states = {}
user_data = {}
user_menu_msg = {}

# ========== ПЕРЕВОДЫ ==========
T = {
    "ru": {
        "choose_lang": "🌍 Выберите язык / Choose language:",
        "welcome": "👋 Привет!\n\nЯ адаптирую резюме под вакансию и оптимизирую под ATS-проверку.\n\nПримите условия использования:",
        "agreed": "✅ Условия приняты!",
        "main_menu": "🏠 Главное меню:",
        "sub_active": "✅ Подписка активна до: {date}",
        "sub_free": "✅ Доступ открыт (бесплатно)",
        "sub_none": "❌ Подписки нет\n\nЦена: {price}₽ / {days} дней\n\nДля оплаты: 📧 {email}",
        "need_sub": "🔒 Нужна подписка.\n\nЦена: {price}₽ / {days} дней\n\nДля оплаты: 📧 {email}",
        "btn_optimize": "🚀 Оптимизировать резюме",
        "btn_my_sub": "🎫 Моя подписка",
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
        "info_text": "ℹ️ Информация\n\n🤖 Бот оптимизации резюме\nАдаптирует резюме под вакансию с учётом ATS.\n\n📧 {email}",
        "support_text": "🆘 Поддержка\n\n📧 {email}\n\nНапишите вопрос прямо здесь:",
        "write_support": "✉️ Напишите ваш вопрос:",
        "support_sent": "✅ Вопрос отправлен! Ответим на {email}",
        "step1": "📄 Шаг 1 из 2 — Резюме\n\nОтправь резюме текстом или .txt файлом:",
        "step2": "✅ Резюме получено!\n\n📋 Шаг 2 из 2 — Вакансия\n\nТеперь вставь текст вакансии:",
        "processing": "⏳ Оптимизирую резюме...",
        "result_title": "✅ Готово!\n\n",
        "result_next": "💡 Что дальше?",
        "need_agree": "⚠️ Сначала примите условия.",
        "too_short_resume": "⚠️ Текст слишком короткий.",
        "too_short_vacancy": "⚠️ Текст вакансии слишком короткий.",
        "no_links": "🔗 Ссылки не поддерживаются. Скопируй текст вакансии.",
        "only_txt": "⚠️ Только .txt. Скопируй текст и отправь как сообщение.",
        "error": "❌ Ошибка. Попробуй ещё раз.",
        "lang_changed": "✅ Язык: Русский",
    },
    "en": {
        "choose_lang": "🌍 Выберите язык / Choose language:",
        "welcome": "👋 Hello!\n\nI adapt resumes for vacancies and optimize for ATS.\n\nPlease accept the terms:",
        "agreed": "✅ Terms accepted!",
        "main_menu": "🏠 Main menu:",
        "sub_active": "✅ Subscription until: {date}",
        "sub_free": "✅ Access is free",
        "sub_none": "❌ No subscription\n\nPrice: {price}₽ / {days} days\n\nTo pay: 📧 {email}",
        "need_sub": "🔒 Subscription required.\n\nPrice: {price}₽ / {days} days\n\nTo pay: 📧 {email}",
        "btn_optimize": "🚀 Optimize resume",
        "btn_my_sub": "🎫 My subscription",
        "btn_info": "ℹ️ Information",
        "btn_support": "🆘 Support",
        "btn_back": "◀️ Back",
        "btn_back_menu": "◀️ Back to menu",
        "btn_back_resume": "◀️ Re-enter resume",
        "btn_again": "🔄 Optimize again",
        "btn_home": "🏠 Main menu",
        "btn_policy": "📄 Privacy Policy",
        "btn_terms": "📋 Terms",
        "btn_agree": "✅ I accept",
        "btn_write_support": "✉️ Write question",
        "info_text": "ℹ️ Information\n\n🤖 Resume Optimization Bot\nAdapts resumes for vacancies with ATS.\n\n📧 {email}",
        "support_text": "🆘 Support\n\n📧 {email}\n\nWrite your question here:",
        "write_support": "✉️ Write your question:",
        "support_sent": "✅ Sent! We'll reply to {email}",
        "step1": "📄 Step 1 of 2 — Resume\n\nSend resume as text or .txt file:",
        "step2": "✅ Resume received!\n\n📋 Step 2 of 2 — Vacancy\n\nPaste vacancy text:",
        "processing": "⏳ Optimizing resume...",
        "result_title": "✅ Done!\n\n",
        "result_next": "💡 What next?",
        "need_agree": "⚠️ Accept terms first.",
        "too_short_resume": "⚠️ Text too short.",
        "too_short_vacancy": "⚠️ Vacancy text too short.",
        "no_links": "🔗 Links not supported. Copy vacancy text.",
        "only_txt": "⚠️ Only .txt. Copy text and send as message.",
        "error": "❌ Error. Try again.",
        "lang_changed": "✅ Language: English",
    }
}

SYSTEM_PROMPT = {
    "ru": "Ты эксперт по оптимизации резюме. Кратко и чётко адаптируй резюме под вакансию: добавь ключевые слова, оптимизируй под ATS. Сохрани реальные данные. В конце 2-3 строки: процент соответствия и главное что изменено.",
    "en": "You are a resume expert. Briefly adapt the resume for the vacancy: add keywords, optimize for ATS. Keep real data. End with 2-3 lines: match % and key changes."
}

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ==========
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        agreed BOOLEAN DEFAULT FALSE,
        lang TEXT DEFAULT 'ru',
        sub_until TIMESTAMP DEFAULT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        user_id BIGINT PRIMARY KEY,
        message TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    # Таблица для логов платежей (опционально)
    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        order_id TEXT,
        amount INTEGER,
        status TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    for key, val in [("price","0"),("subscription_days","30"),("ad_text",""),("ad_active","0")]:
        c.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING", (key,val))
    conn.commit()
    conn.close()

def get_user(uid):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def upsert_user(uid, agreed=None, lang=None, sub_until=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO users(user_id) VALUES(%s) ON CONFLICT(user_id) DO NOTHING", (uid,))
    if agreed is not None:
        c.execute("UPDATE users SET agreed=%s WHERE user_id=%s", (agreed, uid))
    if lang is not None:
        c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (lang, uid))
    if sub_until is not None:
        c.execute("UPDATE users SET sub_until=%s WHERE user_id=%s", (sub_until, uid))
    conn.commit()
    conn.close()

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
    c.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=%s", (key,str(value),str(value)))
    conn.commit()
    conn.close()

def save_ticket(uid, message):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO tickets(user_id,message) VALUES(%s,%s) ON CONFLICT(user_id) DO UPDATE SET message=%s,created_at=NOW()", (uid,message,message))
    conn.commit()
    conn.close()

def get_tickets():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, message FROM tickets ORDER BY created_at DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_ticket(uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM tickets WHERE user_id=%s", (uid,))
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

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

init_db()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def t(uid, key, **kwargs):
    user = get_user(uid)
    lang = user["lang"] if user else "ru"
    text = T.get(lang, T["ru"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

def get_lang(uid):
    user = get_user(uid)
    return user["lang"] if user else "ru"

def has_access(uid):
    if get_setting("price") == "0":
        return True
    user = get_user(uid)
    return bool(user and user["sub_until"] and user["sub_until"] > datetime.now())

def sub_status_text(uid):
    price = get_setting("price")
    days = get_setting("subscription_days")
    if price == "0":
        return t(uid, "sub_free")
    user = get_user(uid)
    if user and user["sub_until"] and user["sub_until"] > datetime.now():
        return t(uid, "sub_active", date=user["sub_until"].strftime("%d.%m.%Y"))
    return t(uid, "sub_none", price=price, days=days, email=SUPPORT_EMAIL)

def get_ad_footer():
    """Реклама как подпись — всегда видна внизу каждого сообщения"""
    if get_setting("ad_active") == "1":
        ad = get_setting("ad_text")
        if ad:
            return f"\n\n━━━━━━━━━━━━━━━\n📢 {ad}"
    return ""

def delete_prev_menu(cid):
    """Удаляем предыдущее меню"""
    if cid in user_menu_msg:
        try:
            bot.delete_message(cid, user_menu_msg[cid])
        except: pass
        del user_menu_msg[cid]

def send_menu(cid, text, kb):
    """Отправляем новое меню и сохраняем его message_id"""
    delete_prev_menu(cid)
    ad = get_ad_footer()
    msg = bot.send_message(cid, text + ad, reply_markup=kb)
    user_menu_msg[cid] = msg.message_id
    return msg

# ========== ФУНКЦИЯ ДЛЯ СОЗДАНИЯ ПЛАТЕЖА В PLATIGA ==========
def create_platiga_payment(user_id, amount, description, payment_method=1, order_id=None):
    """
    Создаёт платёж в Platiga и возвращает ссылку для оплаты.
    """
    if not order_id:
        order_id = f"{user_id}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
    
    # Базовый URL для возврата пользователя в бота
    bot_url = f"https://t.me/{(bot.get_me()).username}"
    
    payload = {
        "paymentMethod": payment_method,
        "paymentDetails": {
            "amount": amount,
            "currency": "RUB"
        },
        "description": description,
        "return": f"{bot_url}?start=payment_success_{order_id}",
        "failedUrl": f"{bot_url}?start=payment_fail_{order_id}",
        "payload": {
            "user_id": user_id,
            "order_id": order_id,
            "type": "subscription"
        }
    }
    
    # Добавляем вебхук (он уже задан выше)
    if PLATIGA_WEBHOOK_URL:
        payload["webhook_url"] = PLATIGA_WEBHOOK_URL
    
    headers = {
        "X-MerchantId": MERCHANT_ID,
        "X-Secret": API_SECRET,
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Creating Platiga payment for user {user_id}, amount {amount}")
        response = requests.post(PLATIGA_API_URL, json=payload, headers=headers, timeout=15)
        
        logger.info(f"Platiga response status: {response.status_code}")
        logger.info(f"Platiga response body: {response.text}")
        
        response.raise_for_status()
        data = response.json()
        
        # Поле со ссылкой может называться по-разному — уточните у Platiga
        payment_url = (data.get("paymentUrl") or data.get("redirectUrl") or 
                       data.get("confirmationUrl") or data.get("url"))
        
        if not payment_url:
            logger.error(f"Platiga: no payment URL in response: {data}")
            return None
            
        return payment_url
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Platiga payment creation failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response body: {e.response.text}")
        return None

# ========== КЛАВИАТУРЫ ==========
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
    if has_access(uid):
        kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_optimize"), callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_my_sub"), callback_data="my_sub"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_info"), callback_data="info"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid,"btn_support"), callback_data="support"))
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
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(f"💰 Цена: {price_text}", callback_data="admin_price"))
    kb.add(telebot.types.InlineKeyboardButton(f"📅 Дней подписки: {days}", callback_data="admin_days"))
    kb.add(telebot.types.InlineKeyboardButton(f"📢 Реклама: {'✅ Вкл' if ad_active else '❌ Выкл'}", callback_data="admin_ad_toggle"))
    kb.add(telebot.types.InlineKeyboardButton("✏️ Текст рекламы", callback_data="admin_ad_text"))
    kb.add(telebot.types.InlineKeyboardButton("➕ Выдать подписку", callback_data="admin_give_sub"))
    kb.add(telebot.types.InlineKeyboardButton("📢 Рассылка всем", callback_data="admin_broadcast"))
    kb.add(telebot.types.InlineKeyboardButton("🎫 Обращения", callback_data="admin_tickets"))
    kb.add(telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    kb.add(telebot.types.InlineKeyboardButton("🏠 Выйти из админки", callback_data="admin_exit"))
    return kb

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@bot.message_handler(commands=["start"])
def start(message):
    cid = message.chat.id
    user_states[cid] = None
    upsert_user(cid)
    delete_prev_menu(cid)
    msg = bot.send_message(cid, T["ru"]["choose_lang"], reply_markup=lang_kb())
    user_menu_msg[cid] = msg.message_id

@bot.message_handler(commands=["admin"])
def admin_cmd(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа.")
        return
    _show_admin(message.chat.id)

def _show_admin(cid):
    delete_prev_menu(cid)
    price = get_setting("price")
    days = get_setting("subscription_days")
    ad_text = get_setting("ad_text") or "не задан"
    ad_active = get_setting("ad_active") == "1"
    msg = bot.send_message(cid,
        f"⚙️ Админ панель\n\n"
        f"💰 Цена: {price}₽\n"
        f"📅 Дней подписки: {days}\n"
        f"📢 Реклама: {'✅ Вкл' if ad_active else '❌ Выкл'}\n"
        f"📝 Текст рекламы: {ad_text}\n\n"
        f"🎫 Обращений: {count_tickets()}\n"
        f"👥 Пользователей: {count_users()}",
        reply_markup=admin_kb()
    )
    user_menu_msg[cid] = msg.message_id

# ========== ОБРАБОТЧИК INLINE КНОПОК ==========
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    cid = call.message.chat.id
    data = call.data

    # ── ЯЗЫК ──
    if data in ("lang_ru", "lang_en"):
        lang = data.split("_")[1]
        upsert_user(cid, lang=lang)
        bot.answer_callback_query(call.id, T[lang]["lang_changed"])
        user = get_user(cid)
        if user and user["agreed"]:
            try:
                bot.edit_message_text(
                    t(cid,"main_menu") + get_ad_footer(),
                    cid, call.message.message_id, reply_markup=main_kb(cid)
                )
            except:
                send_menu(cid, t(cid,"main_menu"), main_kb(cid))
        else:
            try:
                bot.edit_message_text(
                    t(cid,"welcome") + get_ad_footer(),
                    cid, call.message.message_id, reply_markup=agree_kb(cid)
                )
            except:
                send_menu(cid, t(cid,"welcome"), agree_kb(cid))

    # ── AGREE ──
    elif data == "agree":
        upsert_user(cid, agreed=True)
        try:
            bot.edit_message_text(
                t(cid,"main_menu") + get_ad_footer(),
                cid, call.message.message_id, reply_markup=main_kb(cid)
            )
            user_menu_msg[cid] = call.message.message_id
        except:
            send_menu(cid, t(cid,"main_menu"), main_kb(cid))

    # ── MAIN MENU ──
    elif data == "back_main":
        user_states[cid] = None
        try:
            bot.edit_message_text(
                t(cid,"main_menu") + get_ad_footer(),
                cid, call.message.message_id, reply_markup=main_kb(cid)
            )
            user_menu_msg[cid] = call.message.message_id
        except:
            send_menu(cid, t(cid,"main_menu"), main_kb(cid))

    # ── МОЯ ПОДПИСКА (с кнопкой оплаты) ──
    elif data == "my_sub":
        status = sub_status_text(cid)
        kb = telebot.types.InlineKeyboardMarkup()
        if not has_access(cid) and get_setting("price") != "0":
            kb.add(telebot.types.InlineKeyboardButton("💳 Оплатить подписку", callback_data="pay_subscription"))
        kb.add(telebot.types.InlineKeyboardButton(t(cid,"btn_back"), callback_data="back_main"))
        try:
            bot.edit_message_text(
                status + get_ad_footer(),
                cid, call.message.message_id,
                reply_markup=kb
            )
        except:
            pass

    # ── ОПЛАТА ПОДПИСКИ ──
    elif data == "pay_subscription":
        user = get_user(cid)
        if not user or not user["agreed"]:
            bot.answer_callback_query(call.id, t(cid,"need_agree"))
            return
        if has_access(cid):
            bot.answer_callback_query(call.id, "У вас уже есть активная подписка!")
            return

        price = int(get_setting("price"))
        days = get_setting("subscription_days")
        description = f"Подписка на {days} дней"

        # Проверяем, заданы ли ключи Platiga
        if not MERCHANT_ID or not API_SECRET:
            bot.answer_callback_query(call.id, "Платёжная система временно недоступна. Попробуйте позже.")
            logger.error("Platiga credentials not set")
            return

        payment_url = create_platiga_payment(cid, price, description, payment_method=1)  # payment_method уточните

        if payment_url:
            try:
                bot.edit_message_text(
                    f"💳 Для оплаты перейдите по ссылке:\n{payment_url}\n\nПосле оплаты подписка активируется автоматически.",
                    cid, call.message.message_id,
                    reply_markup=telebot.types.InlineKeyboardMarkup().add(
                        telebot.types.InlineKeyboardButton(t(cid,"btn_back"), callback_data="back_main")
                    )
                )
            except:
                pass
        else:
            bot.answer_callback_query(call.id, "Ошибка создания платежа, попробуйте позже.")

    elif data == "info":
        try:
            bot.edit_message_text(
                t(cid,"info_text",email=SUPPORT_EMAIL) + get_ad_footer(),
                cid, call.message.message_id, reply_markup=info_kb(cid)
            )
        except: pass

    elif data == "support":
        try:
            bot.edit_message_text(
                t(cid,"support_text",email=SUPPORT_EMAIL) + get_ad_footer(),
                cid, call.message.message_id, reply_markup=support_kb(cid)
            )
        except: pass

    elif data == "write_support":
        user_states[cid] = "writing_support"
        try:
            bot.edit_message_text(
                t(cid,"write_support") + get_ad_footer(),
                cid, call.message.message_id, reply_markup=back_main_kb(cid)
            )
        except: pass

    # ── FLOW ──
    elif data == "start_flow":
        user = get_user(cid)
        if not user or not user["agreed"]:
            bot.answer_callback_query(call.id, t(cid,"need_agree"))
            return
        if not has_access(cid):
            price = get_setting("price")
            days = get_setting("subscription_days")
            try:
                bot.edit_message_text(
                    t(cid,"need_sub",price=price,days=days,email=SUPPORT_EMAIL) + get_ad_footer(),
                    cid, call.message.message_id,
                    reply_markup=telebot.types.InlineKeyboardMarkup().add(
                        telebot.types.InlineKeyboardButton(t(cid,"btn_back"), callback_data="back_main")
                    )
                )
            except: pass
            return
        user_states[cid] = "waiting_resume"
        user_data.setdefault(cid, {})["resume"] = ""
        try:
            bot.edit_message_text(
                t(cid,"step1") + get_ad_footer(),
                cid, call.message.message_id, reply_markup=back_main_kb(cid)
            )
            user_menu_msg[cid] = call.message.message_id
        except:
            send_menu(cid, t(cid,"step1"), back_main_kb(cid))

    # ── ADMIN ──
    elif data == "admin_exit" and cid == ADMIN_ID:
        user_states[cid] = None
        try:
            bot.edit_message_text(
                t(cid,"main_menu") + get_ad_footer(),
                cid, call.message.message_id, reply_markup=main_kb(cid)
            )
        except:
            send_menu(cid, t(cid,"main_menu"), main_kb(cid))

    elif data == "admin_price" and cid == ADMIN_ID:
        user_states[cid] = "admin_set_price"
        try:
            bot.edit_message_text(
                f"💰 Текущая цена: {get_setting('price')}₽\n\nВведите новую цену (0 = бесплатно):",
                cid, call.message.message_id, reply_markup=back_main_kb(cid)
            )
        except: pass

    elif data == "admin_days" and cid == ADMIN_ID:
        user_states[cid] = "admin_set_days"
        try:
            bot.edit_message_text(
                f"📅 Текущее кол-во дней: {get_setting('subscription_days')}\n\nВведите новое количество:",
                cid, call.message.message_id, reply_markup=back_main_kb(cid)
            )
        except: pass

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
        current = get_setting("ad_text") or "не задан"
        try:
            bot.edit_message_text(
                f"✏️ Текущий текст рекламы:\n{current}\n\nВведите новый текст\n(будет видна внизу КАЖДОГО экрана):",
                cid, call.message.message_id, reply_markup=back_main_kb(cid)
            )
        except: pass

    elif data == "admin_give_sub" and cid == ADMIN_ID:
        user_states[cid] = "admin_give_sub"
        try:
            bot.edit_message_text(
                f"➕ Введите Telegram ID пользователя\n(подписка на {get_setting('subscription_days')} дней):",
                cid, call.message.message_id, reply_markup=back_main_kb(cid)
            )
        except: pass

    elif data == "admin_broadcast" and cid == ADMIN_ID:
        user_states[cid] = "admin_broadcast"
        try:
            bot.edit_message_text(
                "📢 Введите текст рассылки:",
                cid, call.message.message_id, reply_markup=back_main_kb(cid)
            )
        except: pass

    elif data == "admin_tickets" and cid == ADMIN_ID:
        tickets = get_tickets()
        if not tickets:
            bot.answer_callback_query(call.id, "🎫 Обращений нет")
        else:
            for uid, msg in tickets:
                kb = telebot.types.InlineKeyboardMarkup()
                kb.add(telebot.types.InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{uid}"))
                bot.send_message(cid, f"🎫 От {uid}:\n\n{msg}", reply_markup=kb)

    elif data.startswith("reply_") and cid == ADMIN_ID:
        target_id = int(data.split("_")[1])
        user_states[cid] = f"replying_{target_id}"
        bot.send_message(cid, f"✉️ Введите ответ пользователю {target_id}:")

    elif data == "admin_stats" and cid == ADMIN_ID:
        bot.answer_callback_query(call.id, f"👥 {count_users()} польз. | 🎫 {count_tickets()} обращений")

    try:
        bot.answer_callback_query(call.id)
    except: pass


# ========== ОБРАБОТЧИК ДОКУМЕНТОВ ==========
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
    send_menu(cid, t(cid,"step2"), back_resume_kb(cid))

# ========== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ==========
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
        try: bot.delete_message(cid, message.message_id)
        except: pass
        send_menu(cid, t(cid,"support_sent",email=SUPPORT_EMAIL) + "\n\n" + t(cid,"main_menu"), main_kb(cid))
        try:
            bot.send_message(ADMIN_ID, f"🎫 От {cid}:\n\n{text}")
        except: pass
        return

    if state and state.startswith("replying_") and cid == ADMIN_ID:
        target_id = int(state.split("_")[1])
        try:
            bot.send_message(target_id, f"📨 Ответ от поддержки:\n\n{text}")
            delete_ticket(target_id)
        except Exception as e:
            bot.send_message(cid, f"❌ Ошибка: {e}")
        user_states[cid] = None
        _show_admin(cid)
        return

    if state == "admin_set_price" and cid == ADMIN_ID:
        try:
            set_setting("price", int(text))
            user_states[cid] = None
            _show_admin(cid)
        except:
            bot.send_message(cid, "❌ Введите число.")
        return

    if state == "admin_set_days" and cid == ADMIN_ID:
        try:
            set_setting("subscription_days", int(text))
            user_states[cid] = None
            _show_admin(cid)
        except:
            bot.send_message(cid, "❌ Введите число.")
        return

    if state == "admin_set_ad" and cid == ADMIN_ID:
        set_setting("ad_text", text)
        set_setting("ad_active", "1")
        user_states[cid] = None
        _show_admin(cid)
        return

    if state == "admin_give_sub" and cid == ADMIN_ID:
        try:
            target_id = int(text.strip())
            days = int(get_setting("subscription_days"))
            sub_until = datetime.now() + timedelta(days=days)
            upsert_user(target_id, sub_until=sub_until)
            date_str = sub_until.strftime("%d.%m.%Y")
            try:
                bot.send_message(target_id, f"🎉 Подписка выдана до {date_str}!", reply_markup=main_kb(target_id))
            except: pass
        except:
            bot.send_message(cid, "❌ Неверный ID.")
        user_states[cid] = None
        _show_admin(cid)
        return

    if state == "admin_broadcast" and cid == ADMIN_ID:
        users = get_all_users()
        sent = 0
        for uid in users:
            try:
                bot.send_message(uid, f"📢 {text}")
                sent += 1
            except: pass
        bot.send_message(cid, f"✅ Отправлено {sent}/{len(users)}")
        user_states[cid] = None
        _show_admin(cid)
        return

    user = get_user(cid)
    if not user or not user["agreed"]:
        send_menu(cid, t(cid,"need_agree"), agree_kb(cid))
        return

    if state == "waiting_resume":
        if len(text) < 50:
            bot.send_message(cid, t(cid,"too_short_resume"))
            return
        user_data.setdefault(cid, {})["resume"] = text
        user_states[cid] = "waiting_vacancy"
        send_menu(cid, t(cid,"step2"), back_resume_kb(cid))

    elif state == "waiting_vacancy":
        if re.match(r'https?://\S+', text.strip()):
            bot.send_message(cid, t(cid,"no_links"))
            return
        if len(text) < 30:
            bot.send_message(cid, t(cid,"too_short_vacancy"))
            return

        resume = user_data.get(cid, {}).get("resume", "")
        user_states[cid] = None
        delete_prev_menu(cid)
        proc_msg = bot.send_message(cid, t(cid,"processing"))

        lang = get_lang(cid)
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT[lang]},
                    {"role": "user", "content": f"RESUME:\n{resume}\n\n===\n\nVACANCY:\n{text}"}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            result = response.choices[0].message.content

            try: bot.delete_message(cid, proc_msg.message_id)
            except: pass

            full_text = t(cid,"result_title") + result
            if len(full_text) > 4000:
                bot.send_message(cid, t(cid,"result_title"))
                for i in range(0, len(result), 4000):
                    bot.send_message(cid, result[i:i+4000])
            else:
                bot.send_message(cid, full_text)

            send_menu(cid, t(cid,"result_next"), result_kb(cid))

        except Exception as e:
            logger.error(f"Groq error: {e}")
            try: bot.delete_message(cid, proc_msg.message_id)
            except: pass
            send_menu(cid, t(cid,"error"), main_kb(cid))

    else:
        send_menu(cid, t(cid,"main_menu"), main_kb(cid))

# ========== ВЕБХУК ДЛЯ TELEGRAM ==========
@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return "OK", 200

# ========== ВЕБХУК ДЛЯ PLATIGA ==========
@app.route("/webhook/platiga", methods=["POST"])
def platiga_webhook():
    """
    Принимает уведомления от Platiga о статусе платежа.
    После получения успешного платежа активирует подписку пользователю.
    """
    data = request.get_json()
    logger.info(f"📩 Platiga webhook received: {data}")

    # Здесь нужно будет обработать данные, когда узнаем их структуру от Platiga
    # Примерная логика (уточните поля у менеджера):
    # event = data.get("event") or data.get("status")
    # if event == "succeeded" or event == "paid":
    #     user_id = data.get("payload", {}).get("user_id")
    #     order_id = data.get("payload", {}).get("order_id")
    #     if user_id:
    #         days = int(get_setting("subscription_days"))
    #         sub_until = datetime.now() + timedelta(days=days)
    #         upsert_user(int(user_id), sub_until=sub_until)
    #         bot.send_message(user_id, f"✅ Оплата прошла! Подписка до {sub_until.strftime('%d.%m.%Y')}")

    return "OK", 200

@app.route("/")
def index():
    return "Bot is running!", 200

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    # Устанавливаем вебхук для Telegram (если нужно)
    bot.remove_webhook()
    # Используем переменную окружения RENDER_EXTERNAL_HOSTNAME или подставляем вручную
    # Если переменная не задана, используем значение по умолчанию
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'resume-bot-a82h.onrender.com')}/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
