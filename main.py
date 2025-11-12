import os
import asyncio
import sqlite3  # Новый импорт!
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Update, Message, BotCommand
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = os.environ["TOKEN"]
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === Работа с подпиской через SQLite ===
def add_user(chat_id):
    conn = sqlite3.connect("users.db")
    conn.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def remove_user(chat_id):
    conn = sqlite3.connect("users.db")
    conn.execute("DELETE FROM users WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect("users.db")
    cur = conn.execute("SELECT chat_id FROM users")
    ids = [row[0] for row in cur.fetchall()]
    conn.close()
    return ids

# === Команды и меню ===
async def set_commands_for_user(chat_id):
    # Меню для админа
    admin_commands = [
        BotCommand(command="broadcast", description="Создать рассылку"),
        BotCommand(command="start", description="Подписаться на рассылку"),
        BotCommand(command="unsubscribe", description="Отписаться от рассылки")
    ]
    # Меню для подписчика
    user_commands = [
        BotCommand(command="start", description="Подписаться на рассылку"),
        BotCommand(command="unsubscribe", description="Отписаться от рассылки"),
    ]
    if chat_id == ADMIN_CHAT_ID:
        await bot.set_my_commands(admin_commands, scope={"type": "chat", "chat_id": chat_id})
    else:
        await bot.set_my_commands(user_commands, scope={"type": "chat", "chat_id": chat_id})

# === /start: добавить в базу, показать меню ===
@dp.message(F.text == "/start")
async def on_start(msg: Message):
    add_user(msg.chat.id)
    await set_commands_for_user(msg.chat.id)
    await msg.answer("Вы подписаны на рассылку!")

# === /unsubscribe: убрать из базы, показать меню ===
@dp.message(F.text == "/unsubscribe")
async def unsubscribe_command(msg: Message):
    remove_user(msg.chat.id)
    await set_commands_for_user(msg.chat.id)
    await msg.answer("Вы отписались от рассылки. Чтобы снова получать уведомления, используйте /start.")

# === /broadcast: только для админа, структура как раньше ===
@dp.message(F.text.startswith("/broadcast"))
async def broadcast_command(msg: Message):
    if msg.chat.id != ADMIN_CHAT_ID:
        await msg.answer("❌ Нет прав на рассылку.")
        return
    text = msg.text.replace("/broadcast ", "", 1).strip()
    if not text:
        await msg.answer("❌ Укажите текст для рассылки после команды.")
        return
    status_msg = await msg.answer("📤 Рассылка началась...")
    ids = get_all_users()
    sent, failed = 0, 0
    failed_ids = []
    for cid in ids:
        try:
            await bot.send_message(cid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            failed_ids.append(f"{cid} ({str(e)[:30]})")
            print(f"Не удалось отправить в {cid}: {e}")
    report = (f"✅ Рассылка завершена!\n\n"
              f"• Доставлено: {sent}\n"
              f"• Ошибки: {failed}\n")
    if failed_ids:
        report += "\n❌ Не доставлено:\n" + "\n".join(failed_ids[:10])
        if len(failed_ids) > 10:
            report += f"\n... и ещё {len(failed_ids) - 10}"
    await status_msg.edit_text(report)

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
    port = int(os.environ.get("PORT", 8080))
    web.run_app(create_app(), host="0.0.0.0", port=port)
