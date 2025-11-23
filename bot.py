from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
import asyncio
import os
import subprocess
import uuid

# Токен будет из переменных окружения
import os
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Максимальное количество клипов
MAX_CLIPS = 5

class CutState(StatesGroup):
    waiting_video = State()
    waiting_count = State()
    waiting_timestamps = State()

# /start
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Йоу! Кидай серию/видео, я нарежу тебе клипы 🔥\n"
        "Максимум 5 штук за раз, чтобы я не сдох)"
    )

# Ловим видео
@dp.message(F.video, CutState.waiting_video)
@dp.message(F.video)
async def get_video(message: types.Message, state: FSMContext):
    video_file_id = message.video.file_id
    file = await bot.get_file(video_file_id)
    unique_id = str(uuid.uuid4())
    
    original_path = f"temp/{unique_id}_original.mp4"
    os.makedirs("temp", exist_ok=True)
    
    await bot.download_file(file.file_path, original_path)
    
    await state.update_data(original_path=original_path, unique_id=unique_id)
    await message.answer(f"Видео получил! ({message.video.duration} сек)\n\nСколько клипов нарезать? (1–{MAX_CLIPS})")
    await state.set_state(CutState.waiting_count)

# Получаем количество
@dp.message(CutState.waiting_count)
async def get_count(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not (1 <= int(message.text) <= MAX_CLIPS):
        await message.answer(f"Бро, введи число от 1 до {MAX_CLIPS} 😅")
        return
    
    count = int(message.text)
    await state.update_data(clips_count=count)
    await message.answer(
        f"Окей, {count} клипа(ов)\n\n"
        "Теперь пришли таймкоды — по одному на строку:\n"
        "<code>начало_в_секундах длительность_в_секундах</code>\n\n"
        f"Пример для {count} клипов:\n"
        "125 15\n"
        "680 22\n"
        "1840 18\n"
        "2450 20",
        parse_mode="HTML"
    )
    await state.set_state(CutState.waiting_timestamps)

# Получаем и режем
@dp.message(CutState.waiting_timestamps)
async def process_timestamps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    original_path = data["original_path"]
    unique_id = data["unique_id"]
    clips_count = data["clips_count"]
    
    lines = [l.strip() for l in message.text.split("\n") if l.strip()]
    
    if len(lines) != clips_count:
        await message.answer(f"Ты обещал {clips_count}, а прислал {len(lines)} строк 😤 Поправь и пришли заново")
        return
    
    await message.answer("Начинаю резать... ⏳")
    
    output_files = []
    
    for i, line in enumerate(lines):
        try:
            start, duration = map(float, line.split())
            output_path = f"temp/{unique_id}_clip_{i+1}.mp4"
            
            cmd = [
                "ffmpeg", "-y",
                "-i", original_path,
                "-ss", str(start),
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "veryfast",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                output_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            output_files.append(output_path)
        except:
            await message.answer(f"Ошибка на строке {i+1}: <code>{line}</code>\nПроверь таймкоды", parse_mode="HTML")
            # Удаляем всё и выходим
            for f in output_files + [original_path]:
                if os.path.exists(f): os.remove(f)
            await state.clear()
            return
    
    # Отправляем готовые клипы
    media = [types.InputMediaVideo(types.FSInputFile(path)) for path in output_files]
    await message.answer_media_group(media)
    
    await message.answer("Готово, бро! Все клипы выше ↑\n/start — нарезать ещё")
    
    # Чистим за собой
    for f in output_files + [original_path]:
        if os.path.exists(f):
            os.remove(f)
    
    await state.clear()
async def main():
    await dp.start_polling(bot)

if name == "__main__":
    asyncio.run(main())
