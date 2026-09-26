import os
import subprocess
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

# Вставте токен від @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ТУТ")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Тимчасова папка
os.makedirs("temp", exist_ok=True)

# Словник для збереження останнього завантаженого файлу користувача
user_files = {}

TEXT_WATERMARK = "ТРУХА ПОЛТАВА • t.me/truexapoltava"

def get_color_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬛ Чорна вотермарка", callback_data="wm_black"),
            InlineKeyboardButton(text="⬜ Біла вотермарка", callback_data="wm_white")
        ]
    ])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Скиньте сюди **фото** або **відео**, оберіть колір — і я накладу сітку вотермарки каналу!"
    )

# Обробка фото
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    input_path = f"temp/{message.from_user.id}_in.jpg"
    await bot.download_file(file_info.file_path, input_path)
    
    user_files[message.from_user.id] = {
        "type": "photo",
        "input": input_path
    }
    
    await message.reply("Оберіть колір напису:", reply_markup=get_color_keyboard())

# Обробка відео
@dp.message(F.video)
async def handle_video(message: types.Message):
    video = message.video
    if video.file_size > 45 * 1024 * 1024:
        await message.reply("⚠️ Файл завеликий (ліміт для безкоштовного Telegram API — 50 МБ).")
        return

    msg = await message.reply("⏳ Завантажую відео на обробку...")
    file_info = await bot.get_file(video.file_id)
    input_path = f"temp/{message.from_user.id}_in.mp4"
    await bot.download_file(file_info.file_path, input_path)
    
    user_files[message.from_user.id] = {
        "type": "video",
        "input": input_path
    }
    
    await msg.edit_text("Оберіть колір напису:", reply_markup=get_color_keyboard())

# Обробка вибору кольору
@dp.callback_query(F.data.startswith("wm_"))
async def apply_watermark(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_files:
        await callback.answer("Файл застарів або не знайдений. Скиньте заново.", show_alert=True)
        return

    data = user_files[user_id]
    color_choice = callback.data.split("_")[1]
    
    # Колір шрифту з напівпрозорістю
    font_color = "black@0.26" if color_choice == "black" else "white@0.32"

    await callback.message.edit_text("⚙️ Накладаю сітку... Це займе пару секунд.")
    
    ext = "jpg" if data["type"] == "photo" else "mp4"
    output_path = f"temp/{user_id}_out.{ext}"

    # Фільтр FFmpeg: генерує 4 рядки похилого тексту
    vf_filter = (
        f"drawtext=text='{TEXT_WATERMARK}':fontcolor={font_color}:fontsize=h/28:x=w*0.05:y=h*0.2:angle=-22,"
        f"drawtext=text='{TEXT_WATERMARK}':fontcolor={font_color}:fontsize=h/28:x=w*0.05:y=h*0.42:angle=-22,"
        f"drawtext=text='{TEXT_WATERMARK}':fontcolor={font_color}:fontsize=h/28:x=w*0.05:y=h*0.65:angle=-22,"
        f"drawtext=text='{TEXT_WATERMARK}':fontcolor={font_color}:fontsize=h/28:x=w*0.05:y=h*0.87:angle=-22"
    )

    if data["type"] == "photo":
        cmd = [
            "ffmpeg", "-y", "-i", data["input"],
            "-vf", vf_filter,
            output_path
        ]
    else:
        # Для відео — ультрашвидкий пресет
        cmd = [
            "ffmpeg", "-y", "-i", data["input"],
            "-vf", vf_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-c:a", "copy",
            output_path
        ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        doc = FSInputFile(output_path)
        if data["type"] == "photo":
            await callback.message.answer_photo(doc, caption="✅ Готово для публікації")
        else:
            await callback.message.answer_video(doc, caption="✅ Готово для публікації")
            
        await callback.message.delete()
    except Exception as e:
        await callback.message.answer(f"Помилка при рендері: {e}")
    finally:
        # Очищення тимчасових файлів
        for p in [data.get("input"), output_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
        user_files.pop(user_id, None)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
