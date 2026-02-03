import os
import io
import base64
import asyncio
import tempfile
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart

from PIL import Image
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)


def prepare_image_for_openai(image_bytes: bytes) -> bytes:
    """
    Сжимаем/уменьшаем фото, чтобы:
    - быстрее работало
    - не грузило Render
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    max_side = 1600
    w, h = img.size
    scale = max(w, h) / max_side
    if scale > 1:
        img = img.resize((int(w / scale), int(h / scale)), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


def openai_make_interior(image_bytes: bytes) -> bytes:
    """
    Отправляем фото ковра в OpenAI как image edit и получаем готовую картинку в интерьере.
    Используем Images Edit endpoint.  [oai_citation:1‡platform.openai.com](https://platform.openai.com/docs/api-reference/images)
    """
    prompt = (
        "Сделай коммерческое фото для карточки Wildberries: "
        "аккуратно вырежи ковёр с исходного фото и помести его в фотореалистичный интерьер "
        "современной квартиры. Интерьер подбирай по оттенкам ковра (гармония цветов), "
        "сохрани рисунок и фактуру ковра без искажений. "
        "Перспектива ковра должна совпадать с полом, добавь реалистичные тени от ковра. "
        "Никаких водяных знаков, текста и логотипов. Высокое качество, как студийная съемка."
    )

    # Надёжнее всего для OpenAI клиента — отдать файл с диска (/tmp на Render writable)
    with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
        f.write(image_bytes)
        f.flush()

        result = client.images.edit(
            model="gpt-image-1.5",
            image=[open(f.name, "rb")],
            prompt=prompt,
            size="1024x1024",
        )

    b64 = result.data[0].b64_json
    return base64.b64decode(b64)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привет! Пришли фото ковра — я сделаю сразу готовую картинку ковра в подходящем интерьере.\n"
        "Важно: фото должно быть нормального качества (ковёр виден целиком)."
    )


@dp.message(F.photo)
async def photo_handler(message: Message):
    await message.answer("Принял фото. Делаю интерьер…")

    try:
        photo = message.photo[-1]
        file_bytes = await bot.download(photo.file_id)
        raw = file_bytes.read()

        prepared = await asyncio.to_thread(prepare_image_for_openai, raw)
        final_img = await asyncio.to_thread(openai_make_interior, prepared)

        tg_file = BufferedInputFile(final_img, filename="rug_interior.png")
        await message.answer_photo(
            photo=tg_file,
            caption="Готово ✅ Ковёр в интерьере."
        )

    except Exception as e:
        await message.answer(f"Ошибка: {type(e).__name__}: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
