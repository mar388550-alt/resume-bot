import os
import re
import logging
import uuid
import json
import time
import threading
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, request
import telebot
from groq import Groq
import psycopg2
from psycopg2.extras import RealDictCursor

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@rezumeizi")

MERCHANT_ID = os.getenv("MERCHANT_ID")
API_SECRET = os.getenv("API_SECRET")
PLATIGA_API_URL = "https://app.platega.io/transaction/process"
PLATIGA_LK_URL = "https://platega.io/"

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
        "sub_active": "✅ Подписка резюме-адаптер активна до: {date}",
        "sub_free": "✅ Доступ открыт (бесплатно)",
        "sub_none": "❌ Подписки резюме-адаптер нет\n\nЦена: {price}₽ / {days} дней",
        "need_sub": "🔒 Нужна подписка резюме-адаптер.\n\nЦена: {price}₽ / {days} дней\n\nДля оплаты: 📧 {email}",
        "btn_optimize": "🚀 Оптимизировать резюме",
        "btn_my_sub": "📄 Подписка резюме-адаптер",
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
        "info_text": "ℹ️ Информация\n\n🤖 Бот оптимизации резюме\nАдаптирует резюме под вакансию с учётом ATS.\n\n📢 Наш канал: @rezumeizi",
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
        "payment_success": "✅ Оплата прошла успешно!\nПодписка резюме-адаптер активна до {date}.",
        # VPN
        "btn_vpn": "🔐 VPN без ограничений",
        "vpn_menu": "🌐 *VPN без ограничений*\n\n{description}\n\n💰 Цена: {price}₽ / месяц\n\n{status}",
        "vpn_active": "✅ Ваш VPN активен до {date}\n🔑 Ключ:\n`{key}`",
        "vpn_inactive": "❌ У вас нет активного VPN.",
        "btn_pay_resume": "💳 Оплатить резюме адаптер",
        "btn_pay_vpn": "💳 Оплатить VPN",
        "btn_vpn_instruction": "📖 Инструкция",
        "vpn_paid_success": "✅ Оплата VPN получена!\n\n{instruction}",
        "vpn_no_keys": "⚠️ К сожалению, все ключи временно закончились. Обратитесь к администратору.",
    },
    "en": {
        "choose_lang": "🌍 Выберите язык / Choose language:",
        "welcome": "👋 Hello!\n\nI adapt resumes for vacancies and optimize for ATS.\n\nPlease accept the terms:",
        "agreed": "✅ Terms accepted!",
        "main_menu": "🏠 Main menu:",
        "sub_active": "✅ Resume adapter subscription active until: {date}",
        "sub_free": "✅ Access is free",
        "sub_none": "❌ No resume adapter subscription\n\nPrice: {price}₽ / {days} days",
        "need_sub": "🔒 Resume adapter subscription required.\n\nPrice: {price}₽ / {days} days\n\nTo pay: 📧 {email}",
        "btn_optimize": "🚀 Optimize resume",
        "btn_my_sub": "📄 Resume adapter subscription",
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
        "info_text": "ℹ️ Information\n\n🤖 Resume Optimization Bot\nAdapts resumes for vacancies with ATS.\n\n📢 Our channel: @rezumeizi",
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
        "payment_success": "✅ Payment successful!\nResume adapter subscription active until {date}.",
        # VPN
        "btn_vpn": "🔐 Unlimited VPN",
        "vpn_menu": "🌐 *Unlimited VPN*\n\n{description}\n\n💰 Price: {price}₽ / month\n\n{status}",
        "vpn_active": "✅ Your VPN is active until {date}\n🔑 Key:\n`{key}`",
        "vpn_inactive": "❌ You don't have an active VPN.",
        "btn_pay_resume": "💳 Pay for resume adapter",
        "btn_pay_vpn": "💳 Pay for VPN",
        "btn_vpn_instruction": "📖 Instructions",
        "vpn_paid_success": "✅ VPN payment received!\n\n{instruction}",
        "vpn_no_keys": "⚠️ Sorry, all keys are temporarily sold out. Contact administrator.",
    }
}

SYSTEM_PROMPT = {
    "ru": "Ты эксперт по оптимизации резюме. Кратко и чётко адаптируй резюме под вакансию: добавь ключевые слова, оптимизируй под ATS. Сохрани реальные данные. В конце 2-3 строки: процент соответствия и главное что изменено.",
    "en": "You are a resume expert. Briefly adapt the resume for the vacancy: add keywords, optimize for ATS. Keep real data. End with 2-3 lines: match % and key changes."
}

# ========== ФУНКЦИИ БАЗЫ ДАННЫХ ==========
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=10)

def get_conn_with_retry(retries=5, delay=3):
    for attempt in range(1, retries + 1):
        try:
            conn = get_conn()
            logger.info(f"Подключение к БД успешно (попытка {attempt})")
            return conn
        except Exception as e:
            logger.warning(f"Ошибка подключения (попытка {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                raise

def init_database():
    conn = get_conn_with_retry(retries=5, delay=3)
    c = conn.cursor()

    tables = {
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                agreed BOOLEAN DEFAULT FALSE,
                lang TEXT DEFAULT 'ru',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """,
        "settings": "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
        "tickets": """
            CREATE TABLE IF NOT EXISTS tickets (
                user_id BIGINT PRIMARY KEY,
                message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """,
        "payments": """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                order_id TEXT,
                amount INTEGER,
                status TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """,
        "poster_state": "CREATE TABLE IF NOT EXISTS poster_state (key VARCHAR(50) PRIMARY KEY, value INTEGER)",
        "vpn_keys": """
            CREATE TABLE IF NOT EXISTS vpn_keys (
                id SERIAL PRIMARY KEY,
                key_text TEXT UNIQUE NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                used_by BIGINT,
                used_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """,
        "vpn_purchases": """
            CREATE TABLE IF NOT EXISTS vpn_purchases (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                key_id INTEGER REFERENCES vpn_keys(id),
                purchased_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
        """
    }
    for name, sql in tables.items():
        try:
            c.execute(sql)
            logger.info(f"Таблица {name} проверена/создана")
        except Exception as e:
            logger.error(f"Ошибка создания таблицы {name}: {e}")
            conn.rollback()

    c.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='sub_start') THEN
                ALTER TABLE users ADD COLUMN sub_start TIMESTAMP WITH TIME ZONE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='sub_end') THEN
                ALTER TABLE users ADD COLUMN sub_end TIMESTAMP WITH TIME ZONE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='is_subscribed') THEN
                ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;
    """)
    logger.info("Колонки подписки проверены/добавлены")

    init_data = [
        ("INSERT INTO poster_state (key, value) VALUES ('topic_index', 0) ON CONFLICT (key) DO NOTHING", None),
        ("INSERT INTO settings(key,value) VALUES('price','100') ON CONFLICT(key) DO NOTHING", None),
        ("INSERT INTO settings(key,value) VALUES('subscription_days','30') ON CONFLICT(key) DO NOTHING", None),
        ("INSERT INTO settings(key,value) VALUES('ad_text','') ON CONFLICT(key) DO NOTHING", None),
        ("INSERT INTO settings(key,value) VALUES('ad_active','0') ON CONFLICT(key) DO NOTHING", None),
        ("INSERT INTO settings(key,value) VALUES('vpn_price','300') ON CONFLICT(key) DO NOTHING", None),
        ("INSERT INTO settings(key,value) VALUES('vpn_description','🔐 Анонимный и быстрый VPN без ограничений трафика и скорости. Подходит для любых устройств.') ON CONFLICT(key) DO NOTHING", None),
        ("INSERT INTO settings(key,value) VALUES('vpn_instruction','📱 Инструкция по подключению VPN через Happ:\n\n1️⃣ Скачайте приложение:\n• Android (Google Play): https://play.google.com/store/apps/details?id=com.happproxy\n• Android (RuStore): https://apps.rustore.ru/app/com.happproxy\n• iOS: https://apps.apple.com/ru/app/happ-proxy-utility/id6504287215\n\n2️⃣ Скопируйте ключ: {key}\n\n3️⃣ Откройте Happ → кнопка «+» → «Из буфера» → нажмите на сервер.\n\n✅ Готово!') ON CONFLICT(key) DO NOTHING", None),
    ]
    for sql, params in init_data:
        try:
            c.execute(sql, params)
        except Exception as e:
            logger.error(f"Ошибка вставки начальных данных: {e}")
            conn.rollback()

    conn.commit()
    conn.close()
    logger.info("✅ Инициализация базы данных успешно завершена")

# ========== ОСНОВНЫЕ ФУНКЦИИ РАБОТЫ С БД ==========
def get_user(uid):
    conn = get_conn_with_retry()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def upsert_user(uid, agreed=None, lang=None, sub_end=None, sub_start=None, is_subscribed=None):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("INSERT INTO users(user_id) VALUES(%s) ON CONFLICT(user_id) DO NOTHING", (uid,))
    updates = []
    params = []
    if agreed is not None:
        updates.append("agreed = %s")
        params.append(agreed)
    if lang is not None:
        updates.append("lang = %s")
        params.append(lang)
    if sub_end is not None:
        updates.append("sub_end = %s")
        params.append(sub_end)
    if sub_start is not None:
        updates.append("sub_start = %s")
        params.append(sub_start)
    if is_subscribed is not None:
        updates.append("is_subscribed = %s")
        params.append(is_subscribed)
    if updates:
        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = %s"
        params.append(uid)
        c.execute(query, params)
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=%s", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute(
        "INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=%s",
        (key, str(value), str(value))
    )
    conn.commit()
    conn.close()

def save_ticket(uid, message):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tickets(user_id,message) VALUES(%s,%s) ON CONFLICT(user_id) DO UPDATE SET message=%s,created_at=NOW()",
        (uid, message, message)
    )
    conn.commit()
    conn.close()

def get_tickets():
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT user_id, message FROM tickets ORDER BY created_at DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_ticket(uid):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("DELETE FROM tickets WHERE user_id=%s", (uid,))
    conn.commit()
    conn.close()

def count_users():
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    n = c.fetchone()[0]
    conn.close()
    return n

def count_tickets():
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tickets")
    n = c.fetchone()[0]
    conn.close()
    return n

def get_all_users():
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

# ========== ФУНКЦИИ ПОДПИСКИ (резюме) ==========
def has_access(uid):
    try:
        if get_setting("price") == "0":
            return True
        user = get_user(uid)
        if not user:
            return False
        sub_end = user.get("sub_end")
        if not sub_end:
            return False
        return sub_end > datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"Ошибка has_access: {e}")
        return False

def sub_status_text(uid):
    price = get_setting("price")
    days = get_setting("subscription_days")
    if price == "0":
        return t(uid, "sub_free")
    user = get_user(uid)
    if user:
        sub_end = user.get("sub_end")
        if sub_end and sub_end > datetime.now(timezone.utc):
            date_str = sub_end.strftime("%d.%m.%Y")
            return t(uid, "sub_active", date=date_str)
    return t(uid, "sub_none", price=price, days=days)

def activate_subscription(user_id: int, days: int = None):
    if days is None:
        days = int(get_setting("subscription_days") or 30)
    now = datetime.now(timezone.utc)
    sub_end = now + timedelta(days=days)
    upsert_user(user_id, sub_start=now, sub_end=sub_end, is_subscribed=True)
    logger.info(f"✅ Подписка (резюме) активирована для {user_id} до {sub_end}")
    return sub_end

# ========== ФУНКЦИИ VPN ==========
def get_vpn_price():
    return int(get_setting("vpn_price") or 300)

def get_vpn_description():
    return get_setting("vpn_description") or "Анонимный и быстрый VPN без ограничений."

def get_vpn_instruction():
    return get_setting("vpn_instruction") or "Инструкция по VPN не задана."

def get_active_vpn_purchase(user_id):
    conn = get_conn_with_retry()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("""
        SELECT vp.*, vk.key_text 
        FROM vpn_purchases vp
        JOIN vpn_keys vk ON vp.key_id = vk.id
        WHERE vp.user_id = %s AND vp.is_active = TRUE AND vp.expires_at > NOW()
        ORDER BY vp.purchased_at DESC LIMIT 1
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def has_active_vpn(user_id):
    purchase = get_active_vpn_purchase(user_id)
    return purchase is not None

def get_free_vpn_key():
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT id, key_text FROM vpn_keys WHERE used = FALSE ORDER BY id LIMIT 1 FOR UPDATE")
    row = c.fetchone()
    if row:
        key_id, key_text = row
        c.execute("UPDATE vpn_keys SET used = TRUE WHERE id = %s", (key_id,))
        conn.commit()
        conn.close()
        return key_id, key_text
    conn.close()
    return None, None

def activate_vpn(user_id, key_id):
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("""
        INSERT INTO vpn_purchases (user_id, key_id, expires_at)
        VALUES (%s, %s, %s)
    """, (user_id, key_id, expires_at))
    conn.commit()
    conn.close()
    logger.info(f"✅ VPN активирован для {user_id} до {expires_at}")

def deactivate_old_vpn(user_id):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("UPDATE vpn_purchases SET is_active = FALSE WHERE user_id = %s AND is_active = TRUE", (user_id,))
    conn.commit()
    conn.close()

def add_vpn_key(key_text):
    conn = get_conn_with_retry()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO vpn_keys (key_text) VALUES (%s) ON CONFLICT (key_text) DO NOTHING", (key_text,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления ключа: {e}")
        return False
    finally:
        conn.close()

def get_all_vpn_keys():
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT id, key_text, used, used_by FROM vpn_keys ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def get_vpn_stats():
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM vpn_keys WHERE used = FALSE")
    free = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM vpn_keys WHERE used = TRUE")
    used = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM vpn_purchases WHERE is_active = TRUE AND expires_at > NOW()")
    active_subs = c.fetchone()[0]
    conn.close()
    return free, used, active_subs

# ========== ФУНКЦИИ СТАТИСТИКИ ==========
def get_stats():
    conn = get_conn_with_retry()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = TRUE AND sub_end > NOW()")
        active_subs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE sub_start >= DATE_TRUNC('day', NOW())")
        today_subs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = TRUE")
        total_subs = c.fetchone()[0]
    except Exception as e:
        logger.error(f"Ошибка в get_stats: {e}")
        total_users = active_subs = today_subs = total_subs = 0
    finally:
        conn.close()
    return total_users, active_subs, today_subs, total_subs

def get_users_list(offset=0, limit=20):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, sub_end
        FROM users
        ORDER BY user_id
        LIMIT %s OFFSET %s
    """, (limit, offset))
    rows = c.fetchall()
    conn.close()
    return rows

# ========== ФУНКЦИИ ПОСТИНГА ==========
def load_topic_index():
    try:
        conn = get_conn_with_retry()
        c = conn.cursor()
        c.execute("SELECT value FROM poster_state WHERE key = 'topic_index'")
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"Ошибка load_topic_index: {e}")
        return 0

def save_topic_index(index):
    conn = get_conn_with_retry()
    c = conn.cursor()
    c.execute("UPDATE poster_state SET value = %s WHERE key = 'topic_index'", (index,))
    conn.commit()
    conn.close()

TOPICS_RU = [
    "5 ошибок в резюме которые отсеивают ATS-системы",
    "Как правильно описать опыт работы чтобы пройти ATS",
    "Ключевые слова в резюме: как их найти и вставить",
    "Почему HR не видит твоё резюме и как это исправить",
    "Формат резюме который принимают все ATS-системы",
    "Как адаптировать одно резюме под разные вакансии",
    "Раздел навыков в резюме: что писать и как оформить",
    "Сопроводительное письмо: нужно ли и как писать",
    "Как описать достижения в резюме с цифрами",
    "Топ-10 слов которые убивают твоё резюме",
    "Как пройти ATS если у тебя нет опыта работы",
    "Резюме для смены профессии: как составить",
    "Linkedin профиль vs резюме: в чём разница",
    "Как указать образование в резюме правильно",
    "Пробелы в карьере: как объяснить в резюме",
]

def generate_post(topic):
    prompt = f"""Напиши полезный пост для Telegram канала о резюме и карьере.
Тема: {topic}

Требования:
- 150-200 слов
- Живой разговорный стиль
- 3-5 конкретных советов
- В конце призыв подписаться на канал @rezumeizi (если уместно)
- Используй эмодзи
- Без хэштегов"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.7
    )
    return response.choices[0].message.content

def send_post_to_telegram(text):
    bot.send_message(CHANNEL_ID, text)
    return True

def post_with_retry(topic, retries=3):
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Генерация поста для темы: {topic}")
            post_text = generate_post(topic)
            send_post_to_telegram(post_text)
            logger.info("✅ Пост отправлен")
            return True
        except Exception as e:
            logger.error(f"Попытка {attempt} не удалась: {e}")
            if attempt < retries:
                time.sleep(10 * attempt)
    return False

def scheduled_job():
    topic_index = load_topic_index()
    topic = TOPICS_RU[topic_index % len(TOPICS_RU)]
    success = post_with_retry(topic)
    if success:
        save_topic_index(topic_index + 1)

# ========== ПЛАТЕЖИ ==========
def create_platiga_payment(user_id, amount, description, payment_method=11, order_id=None, service_type="subscription"):
    if not order_id:
        order_id = f"{user_id}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
    bot_url = f"https://t.me/{(bot.get_me()).username}"
    payload_data = json.dumps({"user_id": user_id, "order_id": order_id, "type": service_type}, ensure_ascii=False)
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/platiga"
    payload = {
        "paymentMethod": payment_method,
        "paymentDetails": {"amount": amount, "currency": "RUB"},
        "description": description,
        "return": f"{bot_url}?start=payment_success_{order_id}",
        "failedUrl": f"{bot_url}?start=payment_fail_{order_id}",
        "payload": payload_data,
        "webhook_url": webhook_url
    }
    headers = {
        "X-MerchantId": MERCHANT_ID,
        "X-Secret": API_SECRET,
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(PLATIGA_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("redirect")
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        return None

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def t(uid, key, **kwargs):
    user = get_user(uid)
    lang = user["lang"] if user else "ru"
    text = T.get(lang, T["ru"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

def get_lang(uid):
    user = get_user(uid)
    return user["lang"] if user else "ru"

def get_ad_footer():
    if get_setting("ad_active") == "1":
        ad = get_setting("ad_text")
        if ad:
            return f"\n\n━━━━━━━━━━━━━━━\n📢 {ad}"
    return ""

def delete_prev_menu(cid):
    if cid in user_menu_msg:
        try:
            bot.delete_message(cid, user_menu_msg[cid])
        except:
            pass
        del user_menu_msg[cid]

def send_menu(cid, text, kb):
    delete_prev_menu(cid)
    ad = get_ad_footer()
    msg = bot.send_message(cid, text + ad, reply_markup=kb, parse_mode="Markdown")
    user_menu_msg[cid] = msg.message_id
    return msg

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
    kb.add(telebot.types.InlineKeyboardButton(t(uid, "btn_agree"), callback_data="agree"))
    kb.row(
        telebot.types.InlineKeyboardButton(t(uid, "btn_policy"), url=PRIVACY_URL),
        telebot.types.InlineKeyboardButton(t(uid, "btn_terms"), url=TERMS_URL)
    )
    return kb

def main_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    if has_access(uid):
        kb.add(telebot.types.InlineKeyboardButton(t(uid, "btn_optimize"), callback_data="start_flow"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid, "btn_vpn"), callback_data="vpn_menu"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid, "btn_my_sub"), callback_data="my_sub"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid, "btn_info"), callback_data="info"))
    kb.add(telebot.types.InlineKeyboardButton(t(uid, "btn_support"), callback_data="support"))
    return kb

def info_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.row(
        telebot.types.InlineKeyboardButton(t(uid, "btn_policy"), url=PRIVACY
