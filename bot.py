import os
import io
import base64
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart

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


def _build_prompt() -> str:
    # Жёсткий продающий промпт под WB (можешь потом шлифовать)
    return (
        "You are creating a photorealistic marketplace lifestyle image for a rug.\n"
        "Task:\n"
        "1) Keep the rug design/pattern/colors from the input photo.\n"
        "2) Place the SAME rug into a beautiful modern interior that matches the rug tones.\n"
        "3) The rug must look naturally integrated: correct perspective, scale, soft realistic shadows.\n"
        "4) Clean, premium staging, no extra text, no logos, no watermarks.\n"
        "Output: one high-quality photorealistic image."
    )


def generate_rug_interior(image_bytes: bytes) -> bytes:
    """
    Sends image to OpenAI Responses API with image_generation tool.
    Returns PNG bytes.
    Docs: Images & vision guide.   [oai_citation:1‡platform.openai.com](https://platform.openai.com/docs/guides/images)
    """
    # Telegram обычно присылает JPEG/WEBP. Делаем универсально data-url:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    resp = client.responses.create(
        model="gpt-5.2",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": _build_prompt()},
                {"type": "input_image", "image_url": data_url},
            ],
        }],
        tools=[{"type": "image_generation"}],
    )

    # В ответе ищем результат генерации (base64 png)
    image_b64_list = [
        out.result for out in resp.output
        if getattr(out, "type", None) == "image_generation_call"
    ]
    if not image_b64_list:
        raise RuntimeError("No image_generation_call in response")

    png_bytes = base64.b64decode(image_b64_list[0])
    return png_bytes


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привет! Пришли фото ковра — сделаю картинку ковра в подходящем интерьере и пришлю обратно."
    )


@dp.message(F.photo)
async def photo_handler(message: Message):
    await message.answer("Принял фото. Делаю интерьер… ⏳")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        downloaded = await bot.download_file(file.file_path)
        image_bytes = downloaded.read()

        # Генерация может быть долгой — уводим в отдельный поток
        out_png = await asyncio.to_thread(generate_rug_interior, image_bytes)

        input_file = BufferedInputFile(out_png, filename="rug_interior.png")
        await message.answer_document(
            document=input_file,
            caption="Готово ✅ Ковёр в подходящем интерьере."
        )

    except Exception as e:
        await message.answer(f"Ошибка: {type(e).__name__}: {e}")


@dp.message()
async def other_handler(message: Message):
    await message.answer("Пришли именно ФОТО ковра 🙂")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
