import os
import re
import logging
import uuid
import json
import time
import threading
import requests
from datetime import datetime, timedelta
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
CHANNEL_ID = os.getenv("CHANNEL_ID", "@rezumeizi")   # канал для постов

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

# ========== ПЕРЕВОДЫ (сокращено для краткости, в реальном файле нужно оставить полный словарь) ==========
# (я не копирую весь T, он должен остаться из предыдущей версии. В финальном файле он есть.)
# Для экономии места в ответе приведу только структуру. При замене кода используйте ваш полный T.

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ==========
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def ensure_column_exists():
    """Гарантированно добавляет колонку sub_start, если её нет."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_start TIMESTAMP DEFAULT NULL")
        logger.info("✅ Колонка sub_start проверена/добавлена (IF NOT EXISTS)")
    except Exception as e:
        logger.error(f"Ошибка при добавлении колонки: {e}")
    conn.commit()
    conn.close()

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        agreed BOOLEAN DEFAULT FALSE,
        lang TEXT DEFAULT 'ru',
        sub_until TIMESTAMP DEFAULT NULL,
        sub_start TIMESTAMP DEFAULT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    ensure_column_exists()  # <-- принудительная проверка
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        user_id BIGINT PRIMARY KEY,
        message TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        order_id TEXT,
        amount INTEGER,
        status TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS poster_state (
            key VARCHAR(50) PRIMARY KEY,
            value INTEGER
        )
    """)
    c.execute("""
        INSERT INTO poster_state (key, value) 
        VALUES ('topic_index', 0) 
        ON CONFLICT (key) DO NOTHING
    """)
    for key, val in [("price","0"),("subscription_days","30"),("ad_text",""),("ad_active","0")]:
        c.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING", (key,val))
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def get_user(uid):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def upsert_user(uid, agreed=None, lang=None, sub_until=None, sub_start=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO users(user_id) VALUES(%s) ON CONFLICT(user_id) DO NOTHING", (uid,))
    if agreed is not None:
        c.execute("UPDATE users SET agreed=%s WHERE user_id=%s", (agreed, uid))
    if lang is not None:
        c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (lang, uid))
    if sub_until is not None:
        c.execute("UPDATE users SET sub_until=%s WHERE user_id=%s", (sub_until, uid))
    if sub_start is not None:
        c.execute("UPDATE users SET sub_start=%s WHERE user_id=%s", (sub_start, uid))
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

# ========== СТАТИСТИКА (с обработкой ошибок) ==========
def get_stats():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE sub_until > NOW()")
        active_subs = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE sub_start >= DATE_TRUNC('day', NOW())")
        today_subs = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE sub_start IS NOT NULL")
        total_subs = c.fetchone()[0]
    except Exception as e:
        logger.error(f"Ошибка в get_stats: {e}")
        total_users = active_subs = today_subs = total_subs = 0
    finally:
        conn.close()
    return total_users, active_subs, today_subs, total_subs

def get_users_list(offset=0, limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, sub_until 
        FROM users 
        ORDER BY user_id 
        LIMIT %s OFFSET %s
    """, (limit, offset))
    rows = c.fetchall()
    conn.close()
    return rows

# ---------- Функции для постинга ----------
def load_topic_index():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM poster_state WHERE key = 'topic_index'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def save_topic_index(index):
    conn = get_conn()
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
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=data, timeout=10)
    response.raise_for_status()
    return response.json()

def post_with_retry(topic, retries=3):
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Generating post for topic: {topic}")
            post_text = generate_post(topic)
            logger.info("Post generated, sending to Telegram...")
            result = send_post_to_telegram(post_text)
            if result.get("ok"):
                logger.info("✅ Post sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {result}")
        except Exception as e:
            logger.error(f"Attempt {attempt} failed: {e}")
        if attempt < retries:
            wait = 10 * attempt
            logger.info(f"Retrying in {wait} seconds...")
            time.sleep(wait)
    return False

def scheduled_job():
    """Выполняет публикацию поста. Вызывается по cron-эндпоинту."""
    topic_index = load_topic_index()
    topic = TOPICS_RU[topic_index % len(TOPICS_RU)]
    logger.info(f"Starting scheduled job for topic index {topic_index}: {topic}")

    success = post_with_retry(topic)
    if success:
        topic_index += 1
        save_topic_index(topic_index)
    else:
        logger.error("Failed to post after retries, will try again tomorrow with same topic.")

# ========== ФУНКЦИЯ ДЛЯ СОЗДАНИЯ ПЛАТЕЖА ==========
def create_platiga_payment(user_id, amount, description, payment_method=11, order_id=None):
    if not order_id:
        order_id = f"{user_id}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
    bot_url = f"https://t.me/{(bot.get_me()).username}"
    payload_data = json.dumps({"user_id": user_id, "order_id": order_id, "type": "subscription"}, ensure_ascii=False)

    webhook_url = "https://resume-bot-a82h.onrender.com/webhook/platiga"

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
        logger.info(f"Creating Platiga payment for user {user_id}, amount {amount}, method {payment_method}")
        logger.info(f"Request payload: {payload}")
        response = requests.post(PLATIGA_API_URL, json=payload, headers=headers, timeout=15)
        logger.info(f"Platiga response status: {response.status_code}")
        logger.info(f"Platiga response body: {response.text}")
        response.raise_for_status()
        data = response.json()
        payment_url = data.get("redirect")
        if not payment_url:
            logger.error(f"Platiga: no 'redirect' field in response: {data}")
            return None
        return payment_url
    except Exception as e:
        logger.error(f"Platiga payment creation failed: {e}")
        return None

# ========== КЛАВИАТУРЫ (здесь оставьте полный набор из вашего кода) ==========
# (не копирую для краткости, но в финальном файле они должны быть)

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
    return t(uid, "sub_none", price=price, days=days)

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
        except: pass
        del user_menu_msg[cid]

def send_menu(cid, text, kb):
    delete_prev_menu(cid)
    ad = get_ad_footer()
    msg = bot.send_message(cid, text + ad, reply_markup=kb)
    user_menu_msg[cid] = msg.message_id
    return msg

# ========== ОБРАБОТЧИКИ КОМАНД ==========
# (здесь должны быть все ваши обработчики – /start, /admin, и т.д. – они уже есть в предыдущей версии)

# ========== ВЕБХУК ДЛЯ PLATIGA (исправленный) ==========
@app.route("/webhook/platiga", methods=["POST"])
def platiga_webhook():
    data = request.get_json(silent=True) or {}
    logger.info(f"📩 Platiga webhook RAW: {json.dumps(data, ensure_ascii=False, indent=2)}")

    status = data.get("status")
    payload_str = data.get("payload") or "{}"

    # Надёжный парсинг payload (Platiga иногда присылает по-разному)
    try:
        if isinstance(payload_str, str):
            payload = json.loads(payload_str)
        else:
            payload = payload_str
    except Exception as e:
        logger.error(f"❌ Не удалось распарсить payload: {e}")
        payload = {}

    user_id = payload.get("user_id")
    order_id = payload.get("order_id")

    logger.info(f"Parsed → status={status}, user_id={user_id}, order_id={order_id}")

    if status == "CONFIRMED" and user_id:
        try:
            user_id = int(user_id)
            days = int(get_setting("subscription_days"))
            sub_until = datetime.now() + timedelta(days=days)
            sub_start = datetime.now()

            upsert_user(user_id, sub_until=sub_until, sub_start=sub_start)

            logger.info(f"✅ Подписка активирована для {user_id} до {sub_until}")

            try:
                bot.send_message(
                    user_id,
                    f"✅ Оплата прошла успешно!\nПодписка активна до {sub_until.strftime('%d.%m.%Y')}.",
                    reply_markup=main_kb(user_id)
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка активации подписки: {e}")
    else:
        logger.warning(f"⚠️ Webhook без активации: status={status}, user_id={user_id}")

    return "OK", 200

# ========== ЭНДПОИНТ ДЛЯ ВНЕШНЕГО КРОНА ==========
@app.route("/cron/post", methods=["GET"])
def cron_post():
    if not MERCHANT_ID or not API_SECRET:
        # если нет ключей, просто возвращаем OK, чтобы не спамить ошибками
        return "OK", 200
    threading.Thread(target=scheduled_job).start()
    logger.info("Cron endpoint triggered, post generation started")
    return "OK", 200

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

@app.route("/")
def index():
    return "Bot is running!", 200

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    bot.remove_webhook()
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'resume-bot-a82h.onrender.com')}/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
