# -*- coding: utf-8 -*-

import logging
import io

# Библиотеки для Telegram
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Библиотека для работы с изображениями
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont

# --- НАСТРОЙКИ ---
# ВАЖНО! Вставьте сюда ваш токен, полученный от @BotFather
BOT_TOKEN = "7223410410:AAEDTvExPhjEHtYnlju5xnzu3LNw8w972-g"

# --- ЛОГИРОВАНИЕ ---
# Настройка для вывода информации о работе бота в консоль
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- УПРАВЛЕНИЕ СОСТОЯНИЕМ ---
# Словарь для хранения сессий пользователей.
# Ключ: chat_id, Значение: file_id оригинального изображения.
user_sessions = {}

# --- ФУНКЦИИ ОБРАБОТКИ ИЗОБРАЖЕНИЙ ---

def get_filter_functions():
    """Возвращает список из 9 функций-фильтров."""
    
    # Функция для создания сепии
    def apply_sepia(img):
        width, height = img.size
        pixels = img.load()
        for py in range(height):
            for px in range(width):
                r, g, b = img.getpixel((px, py))
                tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                pixels[px, py] = (tr, tg, tb)
        return img

    # Функция для "теплых" тонов
    def apply_warm(img):
        # Создаем прозрачный желтый слой
        yellow_layer = Image.new('RGB', img.size, (255, 230, 150))
        # Накладываем его с небольшой прозрачностью
        return Image.blend(img, yellow_layer, 0.2)

    # Функция для "холодных" тонов
    def apply_cool(img):
        # Создаем прозрачный синий слой
        blue_layer = Image.new('RGB', img.size, (173, 216, 230))
        # Накладываем его с небольшой прозрачностью
        return Image.blend(img, blue_layer, 0.2)

    # Список всех фильтров
    filter_list = [
        lambda img: ImageEnhance.Brightness(img).enhance(1.4),      # 1. Яркость +
        lambda img: ImageEnhance.Brightness(img).enhance(0.6),      # 2. Яркость -
        lambda img: ImageEnhance.Contrast(img).enhance(1.5),        # 3. Контраст +
        lambda img: ImageEnhance.Color(img).enhance(1.8),           # 4. Насыщенность +
        lambda img: img.convert('L').convert('RGB'),                # 5. Ч/Б (конвертируем обратно в RGB для совместимости)
        lambda img: apply_sepia(img.copy()),                        # 6. Сепия
        lambda img: img.filter(ImageFilter.SHARPEN),                # 7. Резкость
        lambda img: apply_warm(img.copy()),                         # 8. Теплые тона
        lambda img: apply_cool(img.copy())                          # 9. Холодные тона
    ]
    return filter_list

def create_collage(image_list):
    """Создает коллаж 3x3 из списка изображений и нумерует их."""
    if not image_list or len(image_list) != 9:
        return None

    # Уменьшаем каждое изображение до размера 300x300 для коллажа
    thumb_width = 300
    images_resized = [img.resize((thumb_width, thumb_width)) for img in image_list]

    # Создаем большой холст для коллажа 3x3
    collage_width = thumb_width * 3
    collage_height = thumb_width * 3
    collage_image = Image.new('RGB', (collage_width, collage_height))
    
    # Загружаем шрифт для номеров
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except IOError:
        font = ImageFont.load_default() # Используем стандартный шрифт, если Arial не найден
    
    # Вставляем каждую картинку в сетку
    for index, img in enumerate(images_resized):
        x = (index % 3) * thumb_width
        y = (index // 3) * thumb_width
        
        # Рисуем номер на картинке
        draw = ImageDraw.Draw(img)
        # Тень для текста
        draw.text((12, 12), str(index + 1), font=font, fill=(0, 0, 0))
        # Сам текст
        draw.text((10, 10), str(index + 1), font=font, fill=(255, 255, 255))
        
        collage_image.paste(img, (x, y))

    # Сохраняем коллаж в байтовый поток в памяти
    collage_buffer = io.BytesIO()
    collage_image.save(collage_buffer, format='JPEG', quality=85)
    collage_buffer.seek(0)
    
    return collage_buffer

# --- ОБРАБОТЧИКИ КОМАНД TELEGRAM ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение при команде /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        "Отправь мне фотографию, и я сделаю 9 вариантов цветокоррекции. "
        "Ты сможешь распечатать их, выбрать лучший и получить его в полном качестве.\n\n"
        "Для помощи используй /help."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет инструкцию по использованию."""
    await update.message.reply_text(
        "Как пользоваться ботом:\n"
        "1. Отправь мне любую фотографию.\n"
        "2. Я пришлю в ответ коллаж из 9 пронумерованных вариантов.\n"
        "3. Распечатай этот коллаж и выбери номер фильтра, который лучше всего смотрится на твоем принтере.\n"
        "4. Отправь мне этот номер (просто цифру от 1 до 9).\n"
        "5. Я пришлю тебе исходное фото с выбранным фильтром в высоком качестве (в виде файла, чтобы не было сжатия)."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает полученную фотографию."""
    chat_id = update.effective_chat.id
    
    # Получаем файл фото в самом высоком разрешении
    photo_file_id = update.message.photo[-1].file_id
    
    # Сохраняем сессию пользователя
    user_sessions[chat_id] = photo_file_id
    logger.info(f"User {chat_id} uploaded a photo. File_id: {photo_file_id}")
    
    await update.message.reply_text("Отлично, я получил фото! Начинаю обработку... Это может занять до минуты.")
    
    # Скачиваем файл в память
    bot = context.bot
    file = await bot.get_file(photo_file_id)
    file_bytes = await file.download_as_bytearray()
    
    # Открываем изображение с помощью Pillow
    original_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    
    # Применяем все фильтры
    filters_list = get_filter_functions()
    processed_images = [f(original_image.copy()) for f in filters_list]
    
    # Создаем коллаж
    collage_buffer = create_collage(processed_images)
    
    if collage_buffer:
        await update.message.reply_photo(
            photo=collage_buffer,
            caption="Вот 9 вариантов. Распечатайте этот файл, выберите лучший вариант и отправьте мне его номер (от 1 до 9)."
        )
    else:
        await update.message.reply_text("Произошла ошибка при создании коллажа. Попробуйте еще раз.")

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя (цифру)."""
    chat_id = update.effective_chat.id
    choice_text = update.message.text
    
    # Проверяем, есть ли у пользователя активная сессия
    if chat_id not in user_sessions:
        await update.message.reply_text("Сначала, пожалуйста, отправьте фотографию.")
        return
        
    # Проверяем, является ли сообщение цифрой от 1 до 9
    try:
        choice_index = int(choice_text)
        if not 1 <= choice_index <= 9:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Пожалуйста, отправьте одну цифру от 1 до 9.")
        return
        
    await update.message.reply_text(f"Вы выбрали фильтр №{choice_index}. Готовлю финальное изображение...")
    
    # Получаем file_id из сессии
    photo_file_id = user_sessions[chat_id]
    
    # Скачиваем ОРИГИНАЛЬНЫЙ файл еще раз для максимального качества
    bot = context.bot
    file = await bot.get_file(photo_file_id)
    file_bytes = await file.download_as_bytearray()
    original_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    
    # Применяем ТОЛЬКО ОДИН выбранный фильтр
    selected_filter = get_filter_functions()[choice_index - 1] # -1 т.к. списки начинаются с 0
    final_image = selected_filter(original_image.copy())
    
    # Сохраняем финальное изображение в буфер
    final_image_buffer = io.BytesIO()
    final_image.save(final_image_buffer, format='PNG') # PNG для сохранения качества
    final_image_buffer.seek(0)
    
    # Отправляем как ДОКУМЕНТ, чтобы избежать сжатия Telegram
    await context.bot.send_document(
        chat_id=chat_id,
        document=InputFile(final_image_buffer, filename=f"filtered_image_{choice_index}.png"),
        caption=f"Готово! Ваше изображение с фильтром №{choice_index}. Отправлено как файл для сохранения максимального качества."
    )
    
    # Удаляем сессию пользователя после успешной отправки
    del user_sessions[chat_id]
    logger.info(f"Session for user {chat_id} closed.")

# --- ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА БОТА ---
def main():
    """Запускает бота."""
    if BOT_TOKEN == "ВАШ_ТЕЛЕГРАМ_ТОКЕН_ЗДЕСЬ":
        print("!!! ОШИБКА: Пожалуйста, вставьте ваш токен Telegram в переменную BOT_TOKEN в коде.")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()