import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Update, Message
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = os.environ["TOKEN"]
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
LIST_CHAT_IDS = [x.strip() for x in os.environ.get("LIST_CHAT_IDS", "").split(",") if x.strip()]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(F.text == "/start")
async def on_start(msg: Message):
    await msg.answer(f"Привет! Вы подписаны на обновления. Ваш chat_id: {msg.chat.id}")

@dp.message(F.text.startswith("/broadcast "))
async def broadcast_command(msg: Message):
    if msg.chat.id != ADMIN_CHAT_ID:
        await msg.answer("❌ У вас нет прав для рассылки.")
        return
    
    text = msg.text.replace("/broadcast ", "", 1).strip()
    
    if not text:
        await msg.answer("❌ Укажите текст сообщения после команды.\n\nПример:\n/broadcast Новая версия 1.2.0 доступна!")
        return
    
    status_msg = await msg.answer("📤 Рассылка началась...")
    
    sent = 0
    failed = 0
    failed_ids = []
    
    for cid in LIST_CHAT_IDS:
        try:
            await bot.send_message(cid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            failed_ids.append(f"{cid} ({str(e)[:30]})")
            print(f"Не удалось отправить в {cid}: {e}")
    
    report = f"✅ Рассылка завершена!\n\n"
    report += f"📊 Статистика:\n"
    report += f"• Успешно: {sent}\n"
    report += f"• Ошибки: {failed}\n"
    
    if failed_ids:
        report += f"\n❌ Не доставлено:\n"
        for fid in failed_ids[:10]:
            report += f"• {fid}\n"
        if len(failed_ids) > 10:
            report += f"... и ещё {len(failed_ids) - 10}"
    
    await status_msg.edit_text(report)

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
