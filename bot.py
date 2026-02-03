import os
import io
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart

from rembg import remove
from PIL import Image

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set in environment variables.")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


def cut_rug_from_photo(image_bytes: bytes) -> bytes:
    """
    Remove background and return PNG with alpha channel.
    Чтобы не зависало на Render — уменьшаем фото перед вырезанием.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # Уменьшаем до 1600px по большей стороне (важно для скорости/памяти)
    max_side = 1600
    w, h = img.size
    scale = max(w, h) / max_side
    if scale > 1:
        new_w = int(w / scale)
        new_h = int(h / scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    out = remove(img)  # PIL Image / bytes depending on rembg, но с PIL обычно ок

    # На всякий случай приводим к PIL Image
    if isinstance(out, bytes):
        out = Image.open(io.BytesIO(out)).convert("RGBA")

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привет! Пришли фото ковра — я вырежу его (уберу фон) и верну PNG.\n"
        "Если фото очень большое — я автоматически уменьшу его, чтобы не зависало."
    )


@dp.message(F.photo)
async def photo_handler(message: Message):
    await message.answer("Принял фото. Вырезаю ковёр…")

    try:
        # Самый простой и стабильный способ скачать фото в aiogram v3
        photo = message.photo[-1]
        file_bytes = await bot.download(photo.file_id)
        image_bytes = file_bytes.read()

        # rembg — тяжёлое, уводим в отдельный поток
        cut_png = await asyncio.to_thread(cut_rug_from_photo, image_bytes)

        input_file = BufferedInputFile(cut_png, filename="cut_rug.png")

        await message.answer_document(
            document=input_file,
            caption="Готово ✅ PNG с прозрачным фоном."
        )

    except Exception as e:
        await message.answer(f"Ошибка при вырезании: {type(e).__name__}: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
