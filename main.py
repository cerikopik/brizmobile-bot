import os
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, Update
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiohttp import web

# Конфиг
TOKEN = os.environ["TOKEN"]
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# FSM: состояния для рассылки
class BroadcastStates(StatesGroup):
    waiting_message = State()

# --- Хранение chat_id всех пользователей ---
def add_user(chat_id):
    # Используем SQLite, БД будет храниться в файле users.db
    conn = sqlite3.connect("users.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY)"
    )
    try:
        conn.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
    except Exception:
        pass
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect("users.db")
    cur = conn.execute("SELECT chat_id FROM users")
    ids = [row[0] for row in cur.fetchall()]
    conn.close()
    return ids

# --- /start: каждый пользователь записывается в БД ---
@dp.message(Command("start"))
async def cmd_start(msg: Message):
    add_user(msg.chat.id)
    await msg.answer("Вы подписаны на рассылку обновлений!")

# --- /broadcast: начинается процедура рассылки ---
@dp.message(Command("broadcast"))
async def cmd_broadcast(msg: Message, state: FSMContext):
    if msg.chat.id != ADMIN_CHAT_ID:
        await msg.answer("❌ Нет прав на рассылку.")
        return
    await msg.answer("Введите текст рассылки и отправьте одним сообщением:")
    await state.set_state(BroadcastStates.waiting_message)

# --- Получаем текст рассылки только от администратора ---
@dp.message(BroadcastStates.waiting_message)
async def broadcast_text(msg: Message, state: FSMContext):
    if msg.chat.id != ADMIN_CHAT_ID:
        await msg.answer("❌ Только администратор может отправлять рассылку.")
        return
    text = msg.text.strip()
    ids = get_all_users()
    sent, failed = 0, 0
    failed_ids = []

    status_msg = await msg.answer(f"📤 Рассылка сообщения ({len(ids)} пользователей) началась...")

    for cid in ids:
        try:
            await bot.send_message(cid, text)
            sent += 1
            await asyncio.sleep(0.05)  # антифлуд — 20 сообщений/сек
        except Exception as e:
            failed += 1
            failed_ids.append(f"{cid} ({str(e)[:32]})")

    report = f"✅ Рассылка завершена!\n\n• Всего: {len(ids)}\n• Доставлено: {sent}\n• Ошибки: {failed}\n"
    if failed_ids:
        report += "\n❌ Не доставлено:\n" + "\n".join(failed_ids[:10])
        if len(failed_ids) > 10:
            report += f"\n... и ещё {len(failed_ids) - 10}"

    await status_msg.edit_text(report)
    await state.clear()  # Сбросить FSM: для нового сообщения нужно снова /broadcast

# --- Вебхук для Cloud Run ---
async def handle_webhook(request: web.Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")

def create_app():
    app = web.Application()
    app.router.add_post("/", handle_webhook)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
