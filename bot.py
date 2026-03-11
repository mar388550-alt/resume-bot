import os
import logging
import io
import time
import telegram
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
)
from telegram.ext import (
    Dispatcher, CommandHandler, MessageHandler,
    CallbackQueryHandler, PreCheckoutQueryHandler,
    Filters, CallbackContext
)
from flask import Flask, request as flask_request
from openai import OpenAI

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ── Токены из Environment Variables на Render ────────────────────────────────
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "")
GROK_API_KEY     = os.environ.get("GROK_API_KEY", "")
PLATIGA_TOKEN    = os.environ.get("PLATIGA_TOKEN", "")
WEBHOOK_URL      = os.environ.get("WEBHOOK_URL", "https://resume-bot-a82h.onrender.com")
SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "@support")
ADMIN_ID         = int(os.environ.get("ADMIN_ID", "123456789"))  # замени через Render ENV

# ── Инициализация ─────────────────────────────────────────────────────────────
grok_client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
bot = telegram.Bot(token=BOT_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# ── Глобальное хранилище (в памяти) ──────────────────────────────────────────
user_db = {}
ads_db = []
settings = {
    "subscription_price": 29900,
    "subscription_label": "299 ₽/месяц"
}
ad_id_counter = [0]

# ── Утилиты ───────────────────────────────────────────────────────────────────
def get_user(user_id):
    if user_id not in user_db:
        user_db[user_id] = {
            "subscribed": False,
            "resume": None,
            "vacancy": None,
            "step": None,
            "joined": int(time.time())
        }
    return user_db[user_id]

def is_subscribed(user_id):
    return get_user(user_id)["subscribed"]

def is_admin(user_id):
    return user_id == ADMIN_ID

# ── Клавиатуры ────────────────────────────────────────────────────────────────
def main_menu(subscribed=False):
    price_label = settings["subscription_label"]
    if subscribed:
        kb = [
            [InlineKeyboardButton("📄 Оптимизировать резюме", callback_data="optimize")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
            [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        ]
    else:
        kb = [
            [InlineKeyboardButton(f"💳 Подписка — {price_label}", callback_data="subscribe")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
            [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        ]
    return InlineKeyboardMarkup(kb)

def info_menu():
    kb = [
        [InlineKeyboardButton("📋 Политика конфиденциальности",
            url="https://telegra.ph/Politika-konfidencialnosti-08-15-17")],
        [InlineKeyboardButton("📜 Пользовательское соглашение",
            url="https://telegra.ph/Polzovatelskoe-soglashenie-08-15-10")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back")],
    ]
    return InlineKeyboardMarkup(kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton("💰 Изменить цену подписки", callback_data="admin_price")],
        [InlineKeyboardButton("📢 Рекламные объявления", callback_data="admin_ads")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("◀️ Выход", callback_data="back")],
    ]
    return InlineKeyboardMarkup(kb)

def ads_menu():
    kb = [[InlineKeyboardButton("➕ Создать объявление", callback_data="ad_create")]]
    for ad in ads_db:
        short = ad["text"][:30] + ("…" if len(ad["text"]) > 30 else "")
        kb.append([InlineKeyboardButton(f"📌 {short}", callback_data=f"ad_view_{ad['id']}")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(kb)

def ad_actions_menu(ad_id):
    kb = [
        [InlineKeyboardButton("📤 Разослать всем", callback_data=f"ad_send_{ad_id}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"ad_delete_{ad_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_ads")],
    ]
    return InlineKeyboardMarkup(kb)

# ── /start ────────────────────────────────────────────────────────────────────
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    get_user(user_id)
    name = update.effective_user.first_name or "друг"
    price_label = settings["subscription_label"]
    text = (
        f"👋 Привет, {name}!\n\n"
        "Я — *ResumeAI Bot* 🤖\n"
        "Помогу создать идеальное резюме, которое пройдёт отбор у HR и ИИ-систем!\n\n"
        "🎯 *Что я умею:*\n"
        "• Анализирую резюме и описание вакансии\n"
        "• Оптимизирую текст под конкретную должность\n"
        "• Добавляю ключевые слова для прохождения ATS-фильтров\n"
        "• Даю советы по улучшению\n\n"
        f"💳 *Доступ по подписке — {price_label}*\n\n"
        "Нажми кнопку ниже чтобы начать 👇"
    )
    update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu(is_subscribed(user_id)))

# ── /admin ────────────────────────────────────────────────────────────────────
def admin_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("⛔ Нет доступа.")
        return
    update.message.reply_text("👨‍💼 *Панель администратора*", parse_mode="Markdown", reply_markup=admin_menu())

# ── Callback-обработчик ───────────────────────────────────────────────────────
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    data = query.data

    if data == "back":
        query.edit_message_text("Главное меню 👇", reply_markup=main_menu(is_subscribed(user_id)))

    elif data == "info":
        query.edit_message_text("📋 *Информация*\n\nЮридические документы:", parse_mode="Markdown", reply_markup=info_menu())

    elif data == "support":
        query.edit_message_text(
            f"🆘 *Поддержка*\n\nПиши нам: {SUPPORT_USERNAME}\n\nОтвечаем в течение 24 часов.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif data == "subscribe":
        if not PLATIGA_TOKEN:
            query.edit_message_text(
                "⏳ Оплата настраивается, скоро будет доступна!\n\nЗайди немного позже 🙏",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]]))
            return
        context.bot.send_invoice(
            chat_id=user_id,
            title="Подписка ResumeAI",
            description="Оптимизация резюме с помощью ИИ",
            payload="subscription_monthly",
            provider_token=PLATIGA_TOKEN,
            currency="RUB",
            prices=[LabeledPrice("Подписка на 1 месяц", settings["subscription_price"])],
            start_parameter="subscription",
        )

    elif data == "optimize":
        if not is_subscribed(user_id):
            query.edit_message_text(
                f"🔒 Только для подписчиков.\n\nПодписка — {settings['subscription_label']} 👇",
                reply_markup=main_menu(False))
            return
        user["step"] = "waiting_resume"
        user["resume"] = None
        user["vacancy"] = None
        query.edit_message_text(
            "📄 *Шаг 1 из 2 — Резюме*\n\nОтправь резюме текстом или файлом (PDF, DOCX, TXT):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="back")]]))

    elif data == "admin_back":
        if not is_admin(user_id): return
        query.edit_message_text("👨‍💼 *Панель администратора*", parse_mode="Markdown", reply_markup=admin_menu())

    elif data == "admin_stats":
        if not is_admin(user_id): return
        total = len(user_db)
        subs = sum(1 for u in user_db.values() if u["subscribed"])
        query.edit_message_text(
            f"📊 *Статистика*\n\n👥 Пользователей: {total}\n💳 Подписчиков: {subs}\n📢 Объявлений: {len(ads_db)}\n💰 Цена: {settings['subscription_label']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))

    elif data == "admin_price":
        if not is_admin(user_id): return
        user["step"] = "admin_set_price"
        query.edit_message_text(
            f"💰 *Изменить цену*\n\nТекущая: {settings['subscription_label']}\n\nВведи новую цену в рублях (например: `499`):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]]))

    elif data == "admin_ads":
        if not is_admin(user_id): return
        count = len(ads_db)
        text = f"📢 *Рекламные объявления*\n\n{'Объявлений: ' + str(count) if count else 'Пока нет объявлений.'}"
        query.edit_message_text(text, parse_mode="Markdown", reply_markup=ads_menu())

    elif data == "ad_create":
        if not is_admin(user_id): return
        user["step"] = "admin_create_ad"
        query.edit_message_text(
            "➕ *Новое объявление*\n\nОтправь текст объявления.\nМожно прикрепить фото с подписью.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_ads")]]))

    elif data.startswith("ad_view_"):
        if not is_admin(user_id): return
        ad_id = int(data.split("_")[2])
        ad = next((a for a in ads_db if a["id"] == ad_id), None)
        if not ad:
            query.edit_message_text("Не найдено.", reply_markup=ads_menu())
            return
        created = time.strftime("%d.%m.%Y %H:%M", time.localtime(ad["created_at"]))
        query.edit_message_text(
            f"📌 *Объявление #{ad_id}*\n🕐 {created}\n\n{ad['text']}",
            parse_mode="Markdown",
            reply_markup=ad_actions_menu(ad_id))

    elif data.startswith("ad_send_"):
        if not is_admin(user_id): return
        ad_id = int(data.split("_")[2])
        ad = next((a for a in ads_db if a["id"] == ad_id), None)
        if not ad:
            query.edit_message_text("Не найдено.", reply_markup=ads_menu())
            return
        query.edit_message_text("📤 Начинаю рассылку...")
        sent = 0
        failed = 0
        for uid in list(user_db.keys()):
            try:
                if ad.get("photo_id"):
                    context.bot.send_photo(chat_id=uid, photo=ad["photo_id"], caption=f"📢 {ad['text']}", parse_mode="Markdown")
                else:
                    context.bot.send_message(chat_id=uid, text=f"📢 *Объявление*\n\n{ad['text']}", parse_mode="Markdown")
                sent += 1
                time.sleep(0.05)
            except Exception:
                failed += 1
        context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Рассылка завершена!\n📤 Отправлено: {sent}\n❌ Ошибок: {failed}",
            reply_markup=admin_menu())

    elif data.startswith("ad_delete_"):
        if not is_admin(user_id): return
        ad_id = int(data.split("_")[2])
        ads_db[:] = [a for a in ads_db if a["id"] != ad_id]
        query.edit_message_text(f"🗑 Объявление #{ad_id} удалено.", reply_markup=ads_menu())

# ── Обработка текста ──────────────────────────────────────────────────────────
def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_user(user_id)
    text = update.message.text

    if user["step"] == "admin_set_price" and is_admin(user_id):
        try:
            price_rub = int(text.strip())
            if price_rub < 1: raise ValueError
            settings["subscription_price"] = price_rub * 100
            settings["subscription_label"] = f"{price_rub} ₽/месяц"
            user["step"] = None
            update.message.reply_text(f"✅ Цена изменена: *{price_rub} ₽/месяц*", parse_mode="Markdown", reply_markup=admin_menu())
        except ValueError:
            update.message.reply_text("⚠️ Введи число, например: `499`", parse_mode="Markdown")
        return

    if user["step"] == "admin_create_ad" and is_admin(user_id):
        ad_id_counter[0] += 1
        ads_db.append({"id": ad_id_counter[0], "text": text, "photo_id": None, "created_at": int(time.time())})
        user["step"] = None
        update.message.reply_text(f"✅ Объявление #{ad_id_counter[0]} создано!", reply_markup=ads_menu())
        return

    if user["step"] == "waiting_resume":
        user["resume"] = text
        user["step"] = "waiting_vacancy"
        update.message.reply_text(
            "✅ Резюме получено!\n\n🔗 *Шаг 2 из 2 — Вакансия*\n\nОтправь ссылку или текст описания вакансии:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="back")]]))
        return

    if user["step"] == "waiting_vacancy":
        user["vacancy"] = text
        user["step"] = None
        update.message.reply_text("⏳ Анализирую резюме... ~30 секунд 🤖")
        result = optimize_resume(user["resume"], user["vacancy"])
        for i in range(0, len(result), 4000):
            update.message.reply_text(result[i:i+4000], parse_mode="Markdown")
        update.message.reply_text("Хочешь оптимизировать под другую вакансию? 👇", reply_markup=main_menu(True))
        return

    update.message.reply_text("Используй меню 👇", reply_markup=main_menu(is_subscribed(user_id)))

# ── Обработка фото ────────────────────────────────────────────────────────────
def handle_photo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user["step"] == "admin_create_ad" and is_admin(user_id):
        photo = update.message.photo[-1]
        caption = update.message.caption or ""
        ad_id_counter[0] += 1
        ads_db.append({"id": ad_id_counter[0], "text": caption, "photo_id": photo.file_id, "created_at": int(time.time())})
        user["step"] = None
        update.message.reply_text(f"✅ Объявление #{ad_id_counter[0]} с фото создано!", reply_markup=ads_menu())
        return
    update.message.reply_text("Используй меню 👇", reply_markup=main_menu(is_subscribed(user_id)))

# ── Обработка файлов ──────────────────────────────────────────────────────────
def handle_document(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user["step"] == "waiting_resume":
        file = update.message.document
        file_name = (file.file_name or "").lower()
        if not any(file_name.endswith(ext) for ext in [".pdf", ".docx", ".txt"]):
            update.message.reply_text("⚠️ Поддерживаются PDF, DOCX, TXT. Или отправь текстом.")
            return
        tg_file = context.bot.get_file(file.file_id)
        file_bytes = tg_file.download_as_bytearray()
        resume_text = extract_text(file_bytes, file_name)
        if not resume_text:
            update.message.reply_text("⚠️ Не удалось прочитать. Попробуй текстом.")
            return
        user["resume"] = resume_text
        user["step"] = "waiting_vacancy"
        update.message.reply_text(
            "✅ Резюме из файла получено!\n\n🔗 *Шаг 2 из 2 — Вакансия*\n\nОтправь ссылку или текст вакансии:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="back")]]))
    else:
        update.message.reply_text("Используй меню 👇", reply_markup=main_menu(is_subscribed(user_id)))

def extract_text(file_bytes, file_name):
    try:
        if file_name.endswith(".txt"):
            return file_bytes.decode("utf-8", errors="ignore")
        elif file_name.endswith(".pdf"):
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(bytes(file_bytes)))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif file_name.endswith(".docx"):
            import docx
            doc = docx.Document(io.BytesIO(bytes(file_bytes)))
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return None

# ── Grok AI ───────────────────────────────────────────────────────────────────
def optimize_resume(resume: str, vacancy: str) -> str:
    try:
        prompt = f"""Ты — эксперт по карьерному консультированию и оптимизации резюме.

РЕЗЮМЕ КАНДИДАТА:
{resume[:3000]}

ВАКАНСИЯ / ОПИСАНИЕ:
{vacancy[:2000]}

Оптимизируй резюме под эту вакансию так чтобы:
1. Пройти ATS-фильтры (ключевые слова из вакансии)
2. Пройти ИИ-проверку рекрутинговых систем
3. Впечатлить HR-специалиста

Формат ответа:

🎯 *АНАЛИЗ СООТВЕТСТВИЯ*
[процент соответствия и краткий анализ]

✅ *СИЛЬНЫЕ СТОРОНЫ*
[что уже хорошо совпадает с вакансией]

🔑 *КЛЮЧЕВЫЕ СЛОВА ДЛЯ ATS*
[список слов из вакансии для добавления в резюме]

📝 *ОПТИМИЗИРОВАННОЕ РЕЗЮМЕ*
[полный текст переработанного резюме]

💡 *СОВЕТЫ ПО УЛУЧШЕНИЮ*
[3-5 конкретных советов]"""

        response = grok_client.chat.completions.create(
            model="grok-beta",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Grok error: {e}")
        return "⚠️ Ошибка ИИ. Попробуй через минуту."

# ── Платежи ───────────────────────────────────────────────────────────────────
def precheckout_handler(update: Update, context: CallbackContext):
    update.pre_checkout_query.answer(ok=True)

def successful_payment(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    get_user(user_id)["subscribed"] = True
    update.message.reply_text(
        "✅ *Оплата прошла!*\n\nПодписка активирована на 30 дней 🎉\nТеперь оптимизируй резюме под любые вакансии!",
        parse_mode="Markdown",
        reply_markup=main_menu(True))

# ── Регистрация хендлеров ─────────────────────────────────────────────────────
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("admin", admin_command))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_handler))
dispatcher.add_handler(MessageHandler(Filters.successful_payment, successful_payment))
dispatcher.add_handler(MessageHandler(Filters.document, handle_document))
dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

# ── Flask ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return "ResumeAI Bot работает! 🤖"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(flask_request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route("/set_webhook")
def set_webhook():
    url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    bot.set_webhook(url)
    return f"Webhook установлен: {url}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
