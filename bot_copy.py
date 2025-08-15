import asyncio
import json
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ========= НАСТРОЙКИ =========
API_TOKEN = '8127281037:AAHIKWzlmNJlmMg4N6_sMLGDLPEtyHg0_aU'   # <-- вставь свой токен бота
CHANNEL_USERNAME = "@etb_music"               # <-- твой канал
DB_NAME = "users.db"
support_user_url = "https://t.me/root_tora"

# Это НЕ postback-URL! Это трекинг/смарт ссылка для пользователя:
tracking_url_template = "https://u3.shortink.io/smart/3BhXXPRtZ739nL?trader_id={trader_id}&promo={promo}"

# Если у тебя есть отдельный промокод/метка кампании — поменяй тут.
DEFAULT_PROMO = "TG"

# Импорт словаря локализаций
from languages import text_lang

# ========= ИНИЦИАЛИЗАЦИЯ БОТА И ДИСПЕТЧЕРА =========
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ========= БАЗА ДАННЫХ =========
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                language    TEXT DEFAULT 'ru',
                subscribed  INTEGER DEFAULT 0,
                registered  INTEGER DEFAULT 0,
                trader_id   TEXT
            )
        """)
        # Логи постбеков (для отладки и аудита)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS postbacks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                trader_id   TEXT,
                promo       TEXT,
                status      TEXT,
                raw         TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# ========= ХЕЛПЕРЫ =========
def t(lang: str, key: str) -> str:
    # безопасный доступ к словарю локализаций
    return text_lang.get(lang, {}).get(key, key)

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status != "left"
    except Exception:
        return False

async def is_registered(trader_id: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM users WHERE trader_id=? AND registered=1", (trader_id,)) as cur:
            row = await cur.fetchone()
            return bool(row)

# ========= КЛАВИАТУРЫ =========
def language_inline():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("Русский", callback_data="lang_ru"),
        InlineKeyboardButton("Кыргыз",  callback_data="lang_kg"),
        InlineKeyboardButton("English", callback_data="lang_en"),
    )
    return kb

def subscribe_inline(lang):
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(t(lang,"Subscribe to channel"), url=f"https://t.me/{CHANNEL_USERNAME[1:]}"),
        InlineKeyboardButton(t(lang,"Check subscription"), callback_data="check_sub"),
    )

def main_menu_inline(lang):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(t(lang,"Change Language"), callback_data="change_lang"),
        InlineKeyboardButton(t(lang,"Instruction"),    callback_data="instruction"),
    )
    kb.add(
        InlineKeyboardButton(t(lang,"Support"), url=support_user_url),
        InlineKeyboardButton(t(lang,"Signals"), callback_data="signals"),
    )
    return kb

def back_inline(lang):
    return InlineKeyboardMarkup().add(InlineKeyboardButton(t(lang,"Back"), callback_data="back"))

def signals_inline(lang):
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(t(lang,"Register"),            callback_data="register"),
        InlineKeyboardButton(t(lang,"Check registration"),  callback_data="check_registration"),
        InlineKeyboardButton(t(lang,"Back"),                callback_data="back"),
    )

def support_inline(lang):
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(t(lang,"Support"), url=support_user_url),
        InlineKeyboardButton(t(lang,"Back"),    callback_data="back"),
    )

# ========= ХЕНДЛЕРЫ БОТА =========
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        await db.commit()
    await message.answer("Выберите язык / Тилди тандаңыз / Choose language", reply_markup=language_inline())

@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT language FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            lang = row[0] if row else "ru"

    # Выбор языка
    if data.startswith("lang_"):
        lang_new = data.split("_", 1)[1]
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET language=? WHERE user_id=?", (lang_new, user_id))
            await db.commit()

        if not await is_subscribed(user_id):
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=t(lang_new, "Please subscribe to the channel to continue"),
                reply_markup=subscribe_inline(lang_new),
            )
            return

        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=t(lang_new, "Main menu"),
            reply_markup=main_menu_inline(lang_new),
        )
        return

    # Проверка подписки
    if data == "check_sub":
        if await is_subscribed(user_id):
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE users SET subscribed=1 WHERE user_id=?", (user_id,))
                await db.commit()
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=t(lang, "Thanks! You are subscribed ✅"),
                reply_markup=main_menu_inline(lang),
            )
        else:
            await bot.answer_callback_query(callback_query.id, text="Вы ещё не подписаны 😕")
        return

    # Смена языка
    if data == "change_lang":
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="Выберите язык / Тилди тандаңыз / Choose language",
            reply_markup=language_inline(),
        )
        return

    # Инструкция
    if data == "instruction":
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=t(lang, "Instruction"),
            reply_markup=back_inline(lang),
        )
        return

    # Поддержка
    if data == "support":
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=t(lang, "Support"),
            reply_markup=support_inline(lang),
        )
        return

    # Сигналы
    if data == "signals":
        txt = t(lang, "Register for signals:")
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=txt,
            reply_markup=signals_inline(lang),
        )
        return

    # Регистрация — выдаём ссылку с твоим trader_id
    if data == "register":
        trader_id = str(user_id)  # если у сервиса есть СВОЙ ID — подставляй его сюда вместо user_id
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET trader_id=? WHERE user_id=?", (trader_id, user_id))
            await db.commit()

        url = tracking_url_template.format(trader_id=trader_id, promo=DEFAULT_PROMO)
        txt = f"{t(lang,'For registration, please follow the link')}:\n{url}"
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=txt,
            reply_markup=back_inline(lang),
        )
        return

    # Проверка регистрации (смотрим поле registered)
    if data == "check_registration":
        registered = await is_registered(str(user_id))
        msg = t(lang, "You are registered ✅") if registered else t(lang, "You are not registered ❌")
        await bot.answer_callback_query(callback_query.id, text=msg, show_alert=True)
        return

    # Назад
    if data == "back":
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=t(lang, "Main menu"),
            reply_markup=main_menu_inline(lang),
        )
        return

# ========= HTTP-СЕРВЕР ДЛЯ ПРИЁМА ПОСТБЕКА =========
async def handle_postback(request: web.Request):
    """
    Принимаем постбек от сервиса.
    Ожидаем хотя бы trader_id (название параметра может быть любым — пытаемся угадать).
    Логируем сырые параметры и помечаем пользователя как registered=1.
    """
    try:
        # Собираем все параметры из query и из тела (POST form/json)
        params = dict(request.rel_url.query)

        if request.can_read_body:
            ctype = request.headers.get("Content-Type", "")
            if "application/json" in ctype:
                body = await request.json()
                if isinstance(body, dict):
                    params.update({k: str(v) for k, v in body.items()})
            else:
                data = await request.post()
                params.update({k: str(v) for k, v in data.items()})

        # Пытаемся вытащить trader_id из разных возможных ключей
        trader_id = (
            params.get("trader_id")
            or params.get("sub_id")
            or params.get("sub1")
            or params.get("uid")
            or params.get("user_id")
        )
        promo = params.get("promo")
        status = params.get("status") or params.get("event") or params.get("action")

        raw_json = json.dumps(params, ensure_ascii=False)

        if not trader_id:
            # Логируем даже невалидный постбек, чтобы видеть, что присылает сервис
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "INSERT INTO postbacks (trader_id, promo, status, raw) VALUES (?, ?, ?, ?)",
                    (None, promo, status, raw_json),
                )
                await db.commit()
            return web.Response(text="missing trader_id", status=400)

        # Логируем постбек
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO postbacks (trader_id, promo, status, raw) VALUES (?, ?, ?, ?)",
                (trader_id, promo, status, raw_json),
            )
            # Ставим registered=1 при любом валидном постбеке с trader_id
            await db.execute(
                "UPDATE users SET registered=1 WHERE trader_id=?",
                (trader_id,),
            )
            await db.commit()

        # По желанию — уведомим пользователя в ТГ (если это реально Telegram ID)
        try:
            uid = int(trader_id)
            await bot.send_message(uid, t("ru", "You are registered ✅"))
        except Exception:
            # Если trader_id — не телеграмный int (например, сервисный ID), просто пропустим
            pass

        return web.Response(text="OK")
    except Exception as e:
        return web.Response(text=f"error: {e}", status=500)

async def handle_health(request: web.Request):
    return web.Response(text="OK")

async def start_http_server():
    app = web.Application()
    app.add_routes([
        web.get("/postback", handle_postback),
        web.post("/postback", handle_postback),
        web.get("/health", handle_health),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    # Слушаем на 0.0.0.0:8080 (прокинь порт/прокси через nginx)
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    # Просто держим задачу живой
    while True:
        await asyncio.sleep(3600)

# ========= ЗАПУСК =========
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # стартуем HTTP-сервер для постбеков параллельно с поллингом
    loop.create_task(start_http_server())
    loop.run_until_complete(init_db())
    executor.start_polling(dp, skip_updates=True)
