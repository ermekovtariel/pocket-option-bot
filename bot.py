import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from languages import text_lang

API_TOKEN = '8127281037:AAHIKWzlmNJlmMg4N6_sMLGDLPEtyHg0_aU'
CHANNEL_USERNAME = '@etb_music'
DB_NAME = "users.db"
support_user_url = "https://t.me/root_tora"
post_back_url = "https://u3.shortink.io/smart/3BhXXPRtZ739nL?trader_id={trader_id}&promo={promo}"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ====== Инициализация базы ======
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'ru',
                subscribed INTEGER DEFAULT 0,
                registered INTEGER DEFAULT 0,
                trader_id TEXT
            )
        """)
        await db.commit()

# ====== Проверка подписки ======
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status != 'left'
    except:
        return False

# ====== Проверка регистрации ======
async def is_registered(trader_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM users WHERE trader_id=?", (trader_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row)

# ====== Inline клавиатуры ======
def language_inline():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("Русский", callback_data="lang_ru"),
        InlineKeyboardButton("Кыргыз", callback_data="lang_kg"),
        InlineKeyboardButton("English", callback_data="lang_en")
    )
    return kb

def subscribe_inline(lang):
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(text_lang[lang]["Subscribe to channel"], url=f"https://t.me/{CHANNEL_USERNAME[1:]}"),
        InlineKeyboardButton(text_lang[lang]["Check subscription"], callback_data="check_sub")
    )

def main_menu_inline(lang):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text_lang[lang]["Change Language"], callback_data="change_lang"),
        InlineKeyboardButton(text_lang[lang]["Instruction"], callback_data="instruction")
    )
    kb.add(
        InlineKeyboardButton(text_lang[lang]["Support"], url=support_user_url),
        InlineKeyboardButton(text_lang[lang]["Signals"], callback_data="signals")
    )
    return kb

def back_inline(lang):
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton(text_lang[lang]["Back"], callback_data="back")
    )

def signals_inline(lang):
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(text_lang[lang]["Register"], callback_data="register"),
        InlineKeyboardButton(text_lang[lang]["Check registration"], callback_data="check_registration"),
        InlineKeyboardButton(text_lang[lang]["Back"], callback_data="back")
    )

def support_inline(lang):
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(text_lang[lang]["Support"], url=support_user_url),
        InlineKeyboardButton(text_lang[lang]["Back"], callback_data="back")
    )

# ====== Хендлеры ======
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        await db.commit()
    await message.answer("Выберите язык / Тилди тандаңыз / Choose language", reply_markup=language_inline())

# ====== Callback обработчик ======
@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT language FROM users WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            lang = row[0] if row else 'ru'

    # ====== Выбор языка ======
    if data.startswith("lang_"):
        lang_new = data.split("_")[1]
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET language=? WHERE user_id=?", (lang_new, user_id))
            await db.commit()
        subscribed = await is_subscribed(user_id)
        if not subscribed:
            text = text_lang[lang_new]["Please subscribe to the channel to continue"]
            await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                        message_id=callback_query.message.message_id,
                                        text=text,
                                        reply_markup=subscribe_inline(lang_new))
            return
        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text=text_lang[lang_new]["Main menu"],
                                    reply_markup=main_menu_inline(lang_new))
        return

    # ====== Проверка подписки ======
    if data == "check_sub":
        subscribed = await is_subscribed(user_id)
        if subscribed:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE users SET subscribed=1 WHERE user_id=?", (user_id,))
                await db.commit()
            await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                        message_id=callback_query.message.message_id,
                                        text=text_lang[lang]["Thanks! You are subscribed ✅"],
                                        reply_markup=main_menu_inline(lang))
        else:
            await bot.answer_callback_query(callback_query.id, text="Вы ещё не подписаны 😕")
        return

    # ====== Смена языка ======
    if data=="change_lang":
        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text="Выберите язык / Тилди тандаңыз / Choose language",
                                    reply_markup=language_inline())
        return

    # ====== Инструкция ======
    if data=="instruction":
        text = text_lang[lang]["Instruction"]
        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text=text,
                                    reply_markup=back_inline(lang))
        return

    if data=="support":
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text_lang[lang]["Support"],
            reply_markup=support_inline(lang)
        )
        return
    
    # ====== Сигналы ======
    if data=="signals":
        text = text_lang[lang]["Register for signals:"]
        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text=text,
                                    reply_markup=signals_inline(lang))
        return

    # ====== Регистрация ======
    if data=="register":
        trader_id = str(user_id)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET trader_id=?, registered=1 WHERE user_id=?", (trader_id, user_id))
            await db.commit()
            
        url = post_back_url.format(trader_id=trader_id, promo="default")
        lang_text = text_lang[lang]["For registration, please follow the link"]
        text = f"{lang_text}:\n{url}"
        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text=text,
                                    reply_markup=back_inline(lang))
        return

    # ====== Проверка регистрации ======
    if data=="check_registration":
        registered = await is_registered(str(user_id))
        msg = "Вы зарегистрированы ✅" if registered else "Вы еще не зарегистрированы ❌"
        await bot.answer_callback_query(callback_query.id, text=msg, show_alert=True)
        return

    # ====== Назад ======
    if data=="back":
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text_lang[lang]["Main menu"],
            reply_markup=main_menu_inline(lang)
        )
        return

# ====== Запуск бота ======
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    executor.start_polling(dp, skip_updates=True)
