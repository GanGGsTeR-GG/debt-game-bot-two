import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN
from db import init_db, get_player, create_player, update_player, record_choice, increment_losses
from scenes import SCENES, INTERACTIVE_SCENES

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ===================== КЛАВИАТУРА =====================
def make_keyboard(buttons, user_id):
    """Создаёт клавиатуру из списка кнопок."""
    kb = []
    for btn in buttons:
        # callback_data — это scene_id
        kb.append([InlineKeyboardButton(text=btn["text"], callback_data=btn["next"])])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ===================== СТАРТ =====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    player = get_player(user_id)

    if player is None:
        # Новый игрок
        create_player(user_id, message.from_user.first_name or "Игрок")
        scene_id = "s00"
    else:
        # Продолжаем с последней сцены
        scene_id = player["current_scene"]
        # Если последняя сцена — концовка, начинаем заново
        if scene_id in ["end_quagmire", "end_application", "end_intercept", "end_death"]:
            scene_id = "s00"

    await send_scene(user_id, scene_id)


# ===================== РЕСТАРТ =====================
@dp.message(Command("restart"))
async def cmd_restart(message: types.Message):
    user_id = message.from_user.id
    # Удаляем старую запись и создаём новую
    from db import delete_player
    delete_player(user_id)
    create_player(user_id, message.from_user.first_name or "Игрок")
    await send_scene(user_id, "s00")


# ===================== ОТПРАВКА СЦЕНЫ =====================
async def send_scene(user_id, scene_id):
    """Отправляет сцену игроку."""
    scene = SCENES.get(scene_id)
    if scene is None:
        # Сцена не найдена — отправляем ошибку
        await bot.send_message(user_id, "⚠️ Ошибка: сцена не найдена. Напиши /start")
        return

    # Обновляем текущую сцену в базе
    update_player(user_id, current_scene=scene_id)

    # Если это концовка — отправляем без кнопок
    if not scene["buttons"]:
        await bot.send_message(user_id, scene["text"], parse_mode="HTML")
        # Предлагаем начать заново
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Начать заново", callback_data="restart")]
        ])
        await bot.send_message(user_id, "Хочешь пройти ещё раз?", reply_markup=kb)
        return

    # Обычная сцена с кнопками
    kb = make_keyboard(scene["buttons"], user_id)
    try:
        await bot.send_message(user_id, scene["text"], reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        # Если HTML не парсится — отправляем без разметки
        logging.error(f"Ошибка отправки сцены: {e}")
        await bot.send_message(user_id, scene["text"].replace("<b>", "").replace("</b>", "")
                              .replace("<i>", "").replace("</i>", ""), reply_markup=kb)


# ===================== ОБРАБОТКА НАЖАТИЙ =====================
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    next_scene = callback.data

    # Обработка рестарта
    if next_scene == "restart":
        from db import delete_player
        delete_player(user_id)
        create_player(user_id, callback.from_user.first_name or "Игрок")
        await callback.message.answer("Начинаем заново...")
        await send_scene(user_id, "s00")
        await callback.answer()
        return

    # Получаем текущую сцену игрока
    player = get_player(user_id)
    if player is None:
        await callback.answer("Напиши /start")
        return

    # Получаем текущую сцену из SCENES
    current_scene_id = player["current_scene"]
    current_scene = SCENES.get(current_scene_id)

    if current_scene is None or not current_scene["buttons"]:
        await callback.answer("Игра окончена. Напиши /start")
        return

    # Ищем кнопку, на которую нажал пользователь
    pressed_button = None
    for btn in current_scene["buttons"]:
        if btn["next"] == next_scene:
            pressed_button = btn
            break

    if pressed_button is None:
        await callback.answer("Ошибка: кнопка не найдена")
        return

    # Записываем выбор в базу, если есть ключ развилки
    if pressed_button.get("key"):
        record_choice(user_id, pressed_button["key"])

    # Считаем проигрыши интерактивов
    if current_scene_id in INTERACTIVE_SCENES.get("kidnap", []):
        if "_fail" in current_scene_id:
            increment_losses(user_id)

    if current_scene_id in INTERACTIVE_SCENES.get("neighbor", []):
        if "_fail" in current_scene_id:
            increment_losses(user_id)

    if current_scene_id in INTERACTIVE_SCENES.get("fight", []):
        if "_fail" in current_scene_id:
            increment_losses(user_id)

    # Спецлогика: концовка "Смерть" — если 2+ проигрышей
    if next_scene == "s20_ending_choice":
        player = get_player(user_id)
        losses = player["losses"] if player else 0
        if losses >= 2:
            # Игрок проиграл 2+ интерактивов — принудительная смерть
            await send_scene(user_id, "end_death")
            await callback.message.delete()
            await callback.answer()
            return

    # Удаляем старое сообщение с кнопками
    try:
        await callback.message.delete()
    except:
        pass

    # Отправляем следующую сцену
    await send_scene(user_id, next_scene)
    await callback.answer()


# ===================== ЗАПУСК =====================
async def main():
    init_db()
    print("✅ Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
