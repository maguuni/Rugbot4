import os
import io
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from rembg import remove
from PIL import Image

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set in environment variables.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


def cut_rug_from_photo(image_bytes: bytes) -> bytes:
    """Remove background and return PNG with alpha channel."""
    input_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    out = remove(input_img)  # PIL Image with transparent bg
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привет! Пришли фото ковра — я вырежу его (уберу фон) и верну PNG.\n"
        "Дальше добавим вставку в интерьер."
    )


@dp.message(F.photo)
async def photo_handler(message: Message):
    await message.answer("Принял фото. Вырезаю ковёр…")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    downloaded = await bot.download_file(file.file_path)
    image_bytes = downloaded.read()

    try:
        cut_png = await asyncio.to_thread(cut_rug_from_photo, image_bytes)

        await message.answer_document(
            document=("cut_rug.png", cut_png),
            caption="Готово ✅ PNG с прозрачным фоном."
        )
    except Exception as e:
        await message.answer(f"Ошибка при вырезании: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
