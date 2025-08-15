import asyncio
import json
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.types import WebAppInfo

# ========= НАСТРОЙКИ =========
API_TOKEN = "8127281037:AAHIKWzlmNJlmMg4N6_sMLGDLPEtyHg0_aU"   # <-- твой токен бота
CHANNEL_USERNAME = "@etb_music"
DB_NAME = "users.db"
support_user_url = "https://t.me/root_tora"

# Ссылка для регистрации пользователя (click_id = user_id)
tracking_url_template = "https://u3.shortink.io/smart/3BhXXPRtZ739nL?click_id={click_id}&promo={promo}"
DEFAULT_PROMO = "TG"

from languages import text_lang

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ========= ИНИЦИАЛИЗАЦИЯ/МИГРАЦИЯ БД =========
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Основные таблицы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'ru',
                subscribed INTEGER DEFAULT 0,
                registered INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS postbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                click_id TEXT,
                trader_id TEXT,
                promo TEXT,
                status TEXT,
                raw TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Миграция недостающих колонок (click_id, trader_id)
        cols_users = set()
        async with db.execute("PRAGMA table_info(users)") as cur:
            async for row in cur:
                # row = (cid, name, type, notnull, dflt_value, pk)
                cols_users.add(row[1])

        if "click_id" not in cols_users:
            await db.execute("ALTER TABLE users ADD COLUMN click_id TEXT")
        if "trader_id" not in cols_users:
            await db.execute("ALTER TABLE users ADD COLUMN trader_id TEXT")
        await db.commit()

# ========= ХЕЛПЕРЫ =========
def t(lang, key):
    return text_lang.get(lang, {}).get(key, key)

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status != "left"
    except:
        return False

async def is_registered(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT registered FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])

# ========= КЛАВИАТУРЫ =========
def language_inline():
    return InlineKeyboardMarkup(row_width=3).add(
        InlineKeyboardButton("Русский", callback_data="lang_ru"),
        InlineKeyboardButton("Кыргыз", callback_data="lang_kg"),
        InlineKeyboardButton("English", callback_data="lang_en"),
    )

def subscribe_inline(lang):
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton(t(lang, "Subscribe to channel"), url=f"https://t.me/{CHANNEL_USERNAME[1:]}"),
        InlineKeyboardButton(t(lang, "Check subscription"), callback_data="check_sub"),
    )

def main_menu_inline(lang, registered=False):
    kb = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton(t(lang, "Change Language"), callback_data="change_lang"),
        InlineKeyboardButton(t(lang, "Instruction"), callback_data="instruction"),
        InlineKeyboardButton(t(lang, "Support"), url=support_user_url),
        InlineKeyboardButton(t(lang, "Signals"), callback_data="signals"),
    )
    if registered:
        kb.add(InlineKeyboardButton(t(lang, "Open Mini App"), web_app=WebAppInfo(url="http://pocketproffesional.ru/")))
    return kb

def back_inline(lang):
    return InlineKeyboardMarkup().add(InlineKeyboardButton(t(lang, "Back"), callback_data="back"))

def signals_inline(lang):
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(t(lang, "Register"), callback_data="register"),
        InlineKeyboardButton(t(lang, "Check registration"), callback_data="check_registration"),
        InlineKeyboardButton(t(lang, "Back"), callback_data="back"),
    )

# ========= ХЕНДЛЕРЫ БОТА =========
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, click_id) VALUES (?, ?)",
            (message.from_user.id, str(message.from_user.id))
        )
        await db.commit()
    # await message.answer("Выберите язык / Choose language", reply_markup=language_inline())
    kb = language_inline()
    await bot.send_photo(
        message.chat.id,
        photo=open("main.jpg", "rb"),
        caption="Выберите язык / Choose language",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: True)
async def callbacks(call: types.CallbackQuery):
    user_id = call.from_user.id
    data = call.data

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT language FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            lang = row[0] if row else "ru"

    if data.startswith("lang_"):
        new_lang = data.split("_", 1)[1]
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET language=? WHERE user_id=?", (new_lang, user_id))
            await db.commit()
        if not await is_subscribed(user_id):
            await call.message.edit_text(
                t(new_lang, "Please subscribe to the channel to continue"),
                reply_markup=subscribe_inline(new_lang)
            )
            return
        registered = await is_registered(user_id)
        await call.message.edit_text(t(new_lang, "Main menu"), reply_markup=main_menu_inline(new_lang, registered=registered))
        return

    if data == "check_sub":
        if await is_subscribed(user_id):
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE users SET subscribed=1 WHERE user_id=?", (user_id,))
                await db.commit()
            registered = await is_registered(user_id)
            await call.message.edit_text(t(lang, "Thanks! You are subscribed ✅"), reply_markup=main_menu_inline(lang, registered=registered))
        else:
            await bot.answer_callback_query(call.id, "Вы ещё не подписаны 😕")
        return

    if data == "signals":
        await call.message.edit_text(t(lang, "Register for signals:"), reply_markup=signals_inline(lang))
        return

    if data == "register":
        # на всякий случай ещё раз зафиксируем click_id=user_id
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET click_id=? WHERE user_id=?", (str(user_id), user_id))
            await db.commit()
        url = tracking_url_template.format(click_id=user_id, promo=DEFAULT_PROMO)
        await call.message.edit_text(
            f"{t(lang, 'For registration, please follow the link')}:\n{url}",
            reply_markup=back_inline(lang)
        )
        return

    if data == "check_registration":
        if await is_registered(user_id):
            await bot.answer_callback_query(call.id, t(lang, "You are registered ✅"), show_alert=True)
        else:
            await bot.answer_callback_query(call.id, t(lang, "You are not registered ❌"), show_alert=True)
        return

    if data == "back":
        registered = await is_registered(user_id)
        await call.message.edit_text(t(lang, "Main menu"), reply_markup=main_menu_inline(lang, registered=registered))
        return

# ========= HTTP POSTBACK (GET + POST) =========
async def handle_postback(request: web.Request):
    """
    Принимаем постбек и из GET, и из POST.
    Поддержка:
      - query string
      - application/json
      - form-data / x-www-form-urlencoded
    Обновляем пользователя по click_id, сохраняем trader_id и registered=1.
    """
    try:
        params = {}

        # из query
        params.update(dict(request.rel_url.query))

        # из тела
        if request.can_read_body:
            ctype = request.headers.get("Content-Type", "") or ""
            ctype = ctype.lower()
            if "application/json" in ctype:
                try:
                    body = await request.json()
                    if isinstance(body, dict):
                        params.update({k: str(v) for k, v in body.items()})
                except Exception:
                    pass
            else:
                try:
                    data = await request.post()
                    params.update({k: str(v) for k, v in data.items()})
                except Exception:
                    pass

        # допускаем синонимы на всякий случай
        click_id = params.get("click_id") or params.get("uid") or params.get("user_id") or params.get("sub_id") or params.get("sub1")
        trader_id = params.get("trader_id")
        promo = params.get("promo")
        status = params.get("status") or params.get("event") or params.get("action")
        raw_json = json.dumps(params, ensure_ascii=False)

        if not click_id:
            return web.Response(text="missing click_id", status=400)

        async with aiosqlite.connect(DB_NAME) as db:
            # лог
            await db.execute(
                "INSERT INTO postbacks (click_id, trader_id, promo, status, raw) VALUES (?, ?, ?, ?, ?)",
                (click_id, trader_id, promo, status, raw_json)
            )
            # апдейт пользователя
            await db.execute(
                "UPDATE users SET trader_id=?, registered=1 WHERE click_id=?",
                (trader_id, click_id)
            )
            await db.commit()

        # уведомление пользователю (если click_id — реальный Telegram id)
        try:
            await bot.send_message(int(click_id), t("ru", "You are registered ✅"))
        except Exception:
            pass

        return web.Response(text="OK")
    except Exception as e:
        return web.Response(text=f"error: {e}", status=500)

async def handle_health(request: web.Request):
    return web.Response(text="OK")

async def start_http_server():
    app = web.Application()
    app.router.add_get("/postback", handle_postback)
    app.router.add_post("/postback", handle_postback)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    # слушаем на 3001 как просил
    site = web.TCPSite(runner, "0.0.0.0", 3001)
    await site.start()

    # держим задачу живой
    while True:
        await asyncio.sleep(3600)

# ========= ЗАПУСК =========
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    loop.create_task(start_http_server())  # HTTP на 3001
    executor.start_polling(dp, skip_updates=True)
