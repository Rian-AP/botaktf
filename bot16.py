import os
import asyncio
from PIL import Image
from playwright.async_api import async_playwright
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext
from datetime import datetime, timedelta
from time import time

# Telegram Bot Token
TOKEN = '7419862491:AAF4K2cy7TMvALRLAMzReQHtDf6-C9RYI_s'
GROUP_ID = '55395'  # ID группы ИСС-22
WHITE_COLOR = (255, 255, 255)  # Цвет для обрезки

# Хранилище для кулдауна запросов
last_request_time = {}

# Функция для создания скриншота
async def take_screenshot(url, filename):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        
        # Делаем скриншот всей страницы
        await page.screenshot(path=filename, full_page=True)
        await browser.close()

# Функция для обрезки изображения до указанного цвета
def crop_to_white_color(filename):
    image = Image.open(filename)
    width, height = image.size

    # Поиск строки, где начинается белый цвет
    bottom_crop = height
    for y in range(height - 1, -1, -1):  # Идем снизу вверх
        for x in range(width):
            if image.getpixel((x, y)) == WHITE_COLOR:
                bottom_crop = y
                break
        if bottom_crop != height:
            break

    # Обрезаем изображение до найденной строки
    if (bottom_crop != height):  # Если белый цвет был найден
        cropped_image = image.crop((0, 0, width, bottom_crop))
        cropped_image.save(filename)

# Функция для отправки скриншота за указанный день
async def send_screenshot(chat_id, date, context, loading_message_id):
    formatted_date = date.strftime("%Y-%m-%d")
    url = f"https://arcotel.ru/studentam/raspisanie-i-grafiki/raspisanie-zanyatiy-studentov-ochnoy-i-vecherney-form-obucheniya?group={GROUP_ID}&date={formatted_date}"
    
    filename = f"screenshot_{formatted_date}.png"
    try:
        await take_screenshot(url, filename)
        crop_to_white_color(filename)

        # Отправка скриншота в Telegram
        with open(filename, 'rb') as file:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=file,
                caption=f"Вот ваше расписание на {formatted_date}:"
            )
            
            # Удаление сообщения о загрузке после отправки скриншота
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)

            # Отправка сообщения с инструкцией
            await context.bot.send_message(
                chat_id=chat_id,
                text="Выберите неделю, за которую хотите получить расписание:",
                reply_markup=create_week_keyboard()
            )
    except Exception as e:
        print(f"Ошибка при отправке изображения: {e}")
        # Если произошла ошибка, отправляем сообщение
        await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text="Расписание скинуть не получилось, попробуйте через пару секунд!"
        )
    finally:
        # Удаление файла после отправки
        if os.path.exists(filename):
            os.remove(filename)

# Функция для создания клавиатуры с кнопками выбора недели
def create_week_keyboard():
    keyboard = [
        [InlineKeyboardButton("Эта неделя", callback_data='this_week')],
        [InlineKeyboardButton("Следующая неделя", callback_data='next_week')],
        [InlineKeyboardButton("Через неделю", callback_data='two_weeks')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Функция для обработки команды /start
async def start_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Привет! Выберите неделю, за которую хотите получить расписание:",
        reply_markup=create_week_keyboard()
    )

# Функция для обработки команды /help
async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Выберите неделю, за которую хотите получить расписание:",
        reply_markup=create_week_keyboard()
    )

# Функция для обработки нажатий на кнопки
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    today = datetime.now()
    selected_date = None

    # Проверка кулдауна
    current_time = time()
    if user_id in last_request_time and (current_time - last_request_time[user_id]) < 5:
        await query.message.reply_text("Пожалуйста, подождите несколько секунд перед следующим запросом.")
        return
    last_request_time[user_id] = current_time

    if data == 'this_week':
        selected_date = today
    elif data == 'next_week':
        selected_date = today + timedelta(days=7)
    elif data == 'two_weeks':
        selected_date = today + timedelta(days=14)

    if selected_date:
        # Отправка сообщения о загрузке
        loading_message = await query.message.reply_text(
            "Подождите, расписание скидывается..."
        )
        
        # Отправка скриншота
        await send_screenshot(query.message.chat.id, selected_date, context, loading_message.message_id)

# Основная функция для настройки и запуска бота
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button))
    
    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
