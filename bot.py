import os
import logging
import json
from datetime import datetime, timedelta
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
# # Добавьте эти строки для загрузки переменных из .env файла.При деплое закомментировать
# from dotenv import load_dotenv
# # Загружаем переменные окружения из .env файла. При деплое закомментировать
# load_dotenv()


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для ConversationHandler
CHOOSING_ACTION, ADDING_LOCATION, SELECTING_LOCATION = range(3)

# Файл для хранения данных пользователей
USER_DATA_FILE = "user_data.json"

# API ключ для OpenWeatherMap
WEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

# Загрузка данных пользователей из файла
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {}

# Сохранение данных пользователей в файл
def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

# Получение данных пользователя
def get_user_data(user_id, user_data):
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "locations": []
        }
    return user_data[user_id_str]

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = load_user_data()
    user = get_user_data(update.effective_user.id, user_data)
    save_user_data(user_data)
    
    buttons = [
        [
            InlineKeyboardButton("🎣 Прогноз клёва", callback_data="show_forecast"),
            InlineKeyboardButton("📍 Мои локации", callback_data="show_locations")
        ],
        [
            InlineKeyboardButton("➕ Добавить локацию", callback_data="add_location"),
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ],
        [InlineKeyboardButton("🔄 Перезапуск", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\n\n"
        "Я бот-предсказатель клёва рыбы. Я анализирую погодные условия и подскажу, когда лучше всего отправиться на рыбалку.\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=reply_markup
    )
    return CHOOSING_ACTION

# Обработчик команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Команды бота:*\n\n"
        "🎣 */forecast* - получить прогноз клёва\n"
        "📍 */locations* - список моих локаций\n"
        "➕ */add_location* - добавить новую локацию\n"
        "❓ */help* - получить помощь\n"
        "🔄 Перезапуск - перезапустить бота\n\n"
        "*Как это работает?*\n"
        "1. Добавь свои любимые места для рыбалки\n"
        "2. Запроси прогноз клёва\n"
        "3. Бот проанализирует погодные условия и оценит вероятность хорошего клёва\n\n"
        "*Факторы, влияющие на клёв:*\n"
        "• Атмосферное давление и его изменения\n"
        "• Температура воздуха и воды\n"
        "• Ветер (направление и сила)\n"
        "• Облачность\n"
        "• Осадки\n"
        "• Фазы луны"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')
    return CHOOSING_ACTION

# Обработчик добавления локации
async def add_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['expecting_location'] = True
    buttons = [[InlineKeyboardButton("🔄 Отмена", callback_data="restart")]]
    await update.message.reply_text(
        "📍 Пожалуйста, отправь название города или населенного пункта, рядом с которым ты рыбачишь.\n\n"
        "Например: Москва, Санкт-Петербург, Сочи",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ADDING_LOCATION

# Обработчик получения названия локации
async def location_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location_name = update.message.text.strip()
    
    # Проверяем существование локации через API погоды
    try:
        weather_data = get_weather_data(location_name)
        location_info = {
            "name": weather_data["name"],
            "country": weather_data["sys"]["country"],
            "lat": weather_data["coord"]["lat"],
            "lon": weather_data["coord"]["lon"],
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Сохраняем локацию пользователя
        user_data = load_user_data()
        user = get_user_data(update.effective_user.id, user_data)
        
        # Проверяем, нет ли уже такой локации
        location_exists = False
        for loc in user["locations"]:
            if loc["name"] == location_info["name"] and loc["country"] == location_info["country"]:
                location_exists = True
                break
        
        if location_exists:
            await update.message.reply_text(f"Локация {location_info['name']} уже добавлена в твой список!")
        else:
            user["locations"].append(location_info)
            save_user_data(user_data)
            await update.message.reply_text(
                f"✅ Локация успешно добавлена!\n\n"
                f"📍 *{location_info['name']}, {location_info['country']}*\n"
                f"Координаты: {location_info['lat']}, {location_info['lon']}\n\n"
                f"Теперь ты можешь получить прогноз клёва для этой локации.",
                parse_mode='Markdown'
            )
        
    except Exception as e:
        logger.error(f"Error adding location: {e}")
        await update.message.reply_text(
            "❌ Не удалось найти такой населенный пункт. Пожалуйста, проверь название и попробуй снова."
        )
    
    return CHOOSING_ACTION

# Обработчик команды мои локации
async def show_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Определяем, откуда пришел запрос - из команды или callback
    if update.callback_query:
        query = update.callback_query
        user_id = query.from_user.id
        message = query.message
    else:
        user_id = update.effective_user.id
        message = update.message

    user_data = load_user_data()
    user = get_user_data(user_id, user_data)
    
    if not user["locations"]:
        text = "У тебя пока нет добавленных локаций. Нажми на '➕ Добавить локацию', чтобы добавить места для рыбалки."
        if update.callback_query:
            await query.edit_message_text(text)
        else:
            await message.reply_text(text)
        return CHOOSING_ACTION
    
    locations_text = "📍 *Мои локации для рыбалки:*\n\n"
    buttons = []
    
    for i, loc in enumerate(user["locations"]):
        locations_text += f"{i+1}. {loc['name']}, {loc['country']}\n"
        buttons.append([InlineKeyboardButton(
            f"{loc['name']}, {loc['country']}", 
            callback_data=f"location_{i}"
        )])
    
    buttons.append([InlineKeyboardButton("❌ Удалить локацию", callback_data="delete_location")])
    buttons.append([InlineKeyboardButton("🔄 Вернуться в главное меню", callback_data="restart")])
    
    if update.callback_query:
        await query.edit_message_text(
            locations_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await message.reply_text(
            locations_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    return SELECTING_LOCATION

# Обработчик команды прогноз клёва
async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Определяем, откуда пришел запрос - из команды или callback
    if update.callback_query:
        query = update.callback_query
        user_id = query.from_user.id
        message = query.message
    else:
        user_id = update.effective_user.id
        message = update.message

    user_data = load_user_data()
    user = get_user_data(user_id, user_data)
    
    if not user["locations"]:
        text = "У тебя пока нет добавленных локаций. Нажми на '➕ Добавить локацию', чтобы добавить места для рыбалки."
        if update.callback_query:
            await query.edit_message_text(text)
        else:
            await message.reply_text(text)
        return CHOOSING_ACTION
    
    buttons = []
    for i, loc in enumerate(user["locations"]):
        buttons.append([InlineKeyboardButton(
            f"{loc['name']}, {loc['country']}", 
            callback_data=f"forecast_{i}"
        )])
    
    buttons.append([InlineKeyboardButton("🔄 Вернуться в главное меню", callback_data="restart")])
    
    text = "🎣 Выбери локацию для прогноза клёва:"
    if update.callback_query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    return SELECTING_LOCATION

# Обработчик нажатий на кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_data = load_user_data()
    user = get_user_data(query.from_user.id, user_data)
    
    if data == "restart":
        buttons = [
            [
                InlineKeyboardButton("🎣 Прогноз клёва", callback_data="show_forecast"),
                InlineKeyboardButton("📍 Мои локации", callback_data="show_locations")
            ],
            [
                InlineKeyboardButton("➕ Добавить локацию", callback_data="add_location"),
                InlineKeyboardButton("❓ Помощь", callback_data="help")
            ],
            [InlineKeyboardButton("🔄 Перезапуск", callback_data="restart")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await query.edit_message_text(
            f"Бот перезапущен!\n\n"
            "Выберите действие из меню ниже:",
            reply_markup=reply_markup
        )
        return CHOOSING_ACTION
    
    elif data == "show_forecast":
        return await forecast_command(update, context)
    
    elif data == "show_locations":
        return await show_locations(update, context)
    
    elif data == "add_location":
        await query.edit_message_text(
            "📍 Пожалуйста, отправь название города или населенного пункта, рядом с которым ты рыбачишь.\n\n"
            "Например: Москва, Санкт-Петербург, Сочи"
        )
        return ADDING_LOCATION
    
    elif data == "help":
        help_text = (
            "🤖 *Команды бота:*\n\n"
            "🎣 Прогноз клёва - получить прогноз клёва\n"
            "📍 Мои локации - список моих локаций\n"
            "➕ Добавить локацию - добавить новую локацию\n"
            "❓ Помощь - получить помощь\n"
            "🔄 Перезапуск - перезапустить бота\n\n"
            "*Как это работает?*\n"
            "1. Добавь свои любимые места для рыбалки\n"
            "2. Запроси прогноз клёва\n"
            "3. Бот проанализирует погодные условия и оценит вероятность хорошего клёва\n\n"
            "*Факторы, влияющие на клёв:*\n"
            "• Атмосферное давление и его изменения\n"
            "• Температура воздуха и воды\n"
            "• Ветер (направление и сила)\n"
            "• Облачность\n"
            "• Осадки\n"
            "• Фазы луны"
        )
        
        buttons = [[InlineKeyboardButton("🔄 Вернуться в главное меню", callback_data="restart")]]
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        return CHOOSING_ACTION
    
    elif data.startswith("location_"):
        # Получение информации о локации
        location_index = int(data.split("_")[1])
        location = user["locations"][location_index]
        
        # Получаем прогноз погоды для этой локации
        weather_forecast = get_weather_forecast(location["lat"], location["lon"])
        
        location_text = (
            f"📍 *{location['name']}, {location['country']}*\n\n"
            f"🌤 *Текущая погода:*\n"
            f"Температура: {weather_forecast['current']['temp']}°C\n"
            f"Ощущается как: {weather_forecast['current']['feels_like']}°C\n"
            f"Давление: {weather_forecast['current']['pressure']} гПа\n"
            f"Влажность: {weather_forecast['current']['humidity']}%\n"
            f"Ветер: {weather_forecast['current']['wind_speed']} м/с, {get_wind_direction(weather_forecast['current']['wind_deg'])}\n"
            f"Облачность: {weather_forecast['current']['clouds']}%\n"
        )
        
        await query.message.reply_text(location_text, parse_mode='Markdown')
    
    elif data.startswith("forecast_"):
        # Получение прогноза клёва для локации
        location_index = int(data.split("_")[1])
        location = user["locations"][location_index]
        
        await query.message.reply_text(f"🔍 Анализирую погодные условия для {location['name']}...")
        
        # Получаем прогноз погоды
        weather_forecast = get_weather_forecast(location["lat"], location["lon"])
        
        # Анализируем прогноз клёва на 3 дня
        forecast_text = f"🎣 *Прогноз клёва для {location['name']}*\n\n"
        
        # Текущая фаза луны
        moon_phase = get_moon_phase()
        forecast_text += f"🌙 Фаза луны: {moon_phase['name']}\n\n"
        
        # Прогноз на сегодня и следующие 2 дня
        for i in range(3):
            date = (datetime.now() + timedelta(days=i)).strftime("%d.%m.%Y")
            daily_forecast = weather_forecast['daily'][i]
            
            # Рассчитываем вероятность клёва
            bite_probability, factors = calculate_bite_probability(daily_forecast, moon_phase)
            bite_rating = get_bite_rating(bite_probability)
            
            forecast_text += f"📅 *{date}*\n"
            forecast_text += f"🌡 Температура: {daily_forecast['temp']['day']}°C\n"
            forecast_text += f"💨 Ветер: {daily_forecast['wind_speed']} м/с, {get_wind_direction(daily_forecast['wind_deg'])}\n"
            forecast_text += f"☁️ Облачность: {daily_forecast['clouds']}%\n"
            forecast_text += f"💧 Влажность: {daily_forecast['humidity']}%\n"
            forecast_text += f"📊 Давление: {daily_forecast['pressure']} гПа\n"
            forecast_text += f"🌧 Осадки: {daily_forecast.get('rain', 0)} мм\n"
            forecast_text += f"🎣 Клёв: {bite_rating}\n"
            
            # Добавляем ключевые факторы
            forecast_text += "👍 Благоприятные факторы:\n"
            for factor in factors['positive']:
                forecast_text += f"  • {factor}\n"
            
            forecast_text += "👎 Неблагоприятные факторы:\n"
            for factor in factors['negative']:
                forecast_text += f"  • {factor}\n"
            
            forecast_text += "\n"
        
        # Добавляем рекомендации
        forecast_text += "*Рекомендации по рыбалке:*\n"
        
        if bite_probability > 75:
            forecast_text += "• Отличное время для рыбалки! Не упустите возможность.\n"
            forecast_text += "• Хищная рыба будет активна, стоит использовать активные приманки.\n"
        elif bite_probability > 50:
            forecast_text += "• Хороший день для рыбалки, особенно в утренние и вечерние часы.\n"
            forecast_text += "• Стоит комбинировать разные техники ловли.\n"
        elif bite_probability > 25:
            forecast_text += "• Умеренный клёв, лучше рыбачить в самое тихое время дня.\n"
            forecast_text += "• Рекомендуется использовать пассивные приманки и насадки.\n"
        else:
            forecast_text += "• Неблагоприятные условия для клёва, рыба малоактивна.\n"
            forecast_text += "• Если всё же решите рыбачить, стоит сосредоточиться на глубоких местах.\n"
        
        await query.message.reply_text(forecast_text, parse_mode='Markdown')
    
    elif data == "delete_location":
        # Отображаем локации для удаления
        if not user["locations"]:
            await query.message.reply_text("У тебя нет добавленных локаций.")
            return CHOOSING_ACTION
        
        buttons = []
        for i, loc in enumerate(user["locations"]):
            buttons.append([InlineKeyboardButton(
                f"Удалить: {loc['name']}", 
                callback_data=f"remove_{i}"
            )])
        
        buttons.append([InlineKeyboardButton("Отмена", callback_data="cancel_delete")])
        
        await query.edit_message_text(
            "Выбери локацию для удаления:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif data.startswith("remove_"):
        location_index = int(data.split("_")[1])
        # Удаление локации
        if 0 <= location_index < len(user["locations"]):
            removed_location = user["locations"].pop(location_index)
            save_user_data(user_data)
            
            await query.edit_message_text(
                f"Локация {removed_location['name']} удалена.",
                reply_markup=None
            )
        else:
            await query.edit_message_text(
                "Ошибка: локация не найдена.",
                reply_markup=None
            )
    
    elif data == "cancel_delete":
        await query.edit_message_text(
            "Удаление отменено.",
            reply_markup=None
        )
    
    return CHOOSING_ACTION

# Получение данных погоды для локации
def get_weather_data(location_name):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location_name}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to get weather data: {response.status_code}")
    return response.json()

# Получение прогноза погоды для координат

def get_weather_forecast(lat, lon):
    """
    Получает прогноз погоды с использованием бесплатного API
    вместо OneCall API (который требует подписки)
    """
    try:
        # Текущая погода
        current_weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        current_response = requests.get(current_weather_url)
        
        if current_response.status_code != 200:
            raise Exception(f"Failed to get current weather: {current_response.status_code}")
        
        current_data = current_response.json()
        
        # 5-дневный прогноз
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        forecast_response = requests.get(forecast_url)
        
        if forecast_response.status_code != 200:
            raise Exception(f"Failed to get forecast: {forecast_response.status_code}")
        
        forecast_data = forecast_response.json()
        
        # Преобразуем в формат, совместимый с текущим кодом
        result = {
            "current": {
                "temp": current_data["main"]["temp"],
                "feels_like": current_data["main"]["feels_like"],
                "pressure": current_data["main"]["pressure"],
                "humidity": current_data["main"]["humidity"],
                "wind_speed": current_data["wind"]["speed"],
                "wind_deg": current_data["wind"]["deg"],
                "clouds": current_data["clouds"]["all"]
            },
            "daily": []
        }
        
        # Группируем прогноз по дням и берем среднее
        days_data = {}
        for item in forecast_data["list"]:
            date = item["dt_txt"].split(" ")[0]
            if date not in days_data:
                days_data[date] = []
            days_data[date].append(item)
        
        # Преобразуем данные для каждого дня
        for date, items in days_data.items():
            if len(result["daily"]) >= 3:  # Нам нужно только 3 дня
                break
                
            temp_sum = sum(item["main"]["temp"] for item in items)
            temp_avg = temp_sum / len(items)
            
            temp_day = max(item["main"]["temp"] for item in items)
            temp_night = min(item["main"]["temp"] for item in items)
            
            pressure_sum = sum(item["main"]["pressure"] for item in items)
            pressure_avg = pressure_sum / len(items)
            
            humidity_sum = sum(item["main"]["humidity"] for item in items)
            humidity_avg = humidity_sum / len(items)
            
            wind_speed_sum = sum(item["wind"]["speed"] for item in items)
            wind_speed_avg = wind_speed_sum / len(items)
            
            wind_deg_sum = sum(item["wind"]["deg"] for item in items)
            wind_deg_avg = wind_deg_sum / len(items)
            
            clouds_sum = sum(item["clouds"]["all"] for item in items)
            clouds_avg = clouds_sum / len(items)
            
            # Проверка на наличие дождя
            rain = 0
            for item in items:
                if "rain" in item and "3h" in item["rain"]:
                    rain += item["rain"]["3h"]
            
            day_data = {
                "temp": {
                    "day": temp_day,
                    "night": temp_night
                },
                "pressure": pressure_avg,
                "humidity": humidity_avg,
                "wind_speed": wind_speed_avg,
                "wind_deg": wind_deg_avg,
                "clouds": clouds_avg
            }
            
            if rain > 0:
                day_data["rain"] = rain
            
            result["daily"].append(day_data)
        
        # Если прогноз менее чем на 3 дня, дублируем последний день
        while len(result["daily"]) < 3:
            if result["daily"]:
                result["daily"].append(result["daily"][-1])
            else:
                # Если нет данных, создаем дефолтный прогноз
                result["daily"].append({
                    "temp": {"day": current_data["main"]["temp"], "night": current_data["main"]["temp"] - 5},
                    "pressure": current_data["main"]["pressure"],
                    "humidity": current_data["main"]["humidity"],
                    "wind_speed": current_data["wind"]["speed"],
                    "wind_deg": current_data["wind"]["deg"],
                    "clouds": current_data["clouds"]["all"]
                })
        
        return result
        
    except Exception as e:
        # Для отладки возвращаем тестовые данные
        logger.error(f"Error getting weather data: {e}")
        return {
            "current": {
                "temp": 15.5,
                "feels_like": 14.8,
                "pressure": 1013,
                "humidity": 76,
                "wind_speed": 3.6,
                "wind_deg": 220,
                "clouds": 75
            },
            "daily": [
                {
                    "temp": {"day": 15.5, "night": 10.2},
                    "pressure": 1013,
                    "humidity": 76,
                    "wind_speed": 3.6,
                    "wind_deg": 220,
                    "clouds": 75
                },
                {
                    "temp": {"day": 16.8, "night": 11.5},
                    "pressure": 1012,
                    "humidity": 70,
                    "wind_speed": 4.1,
                    "wind_deg": 200,
                    "clouds": 60
                },
                {
                    "temp": {"day": 17.2, "night": 12.0},
                    "pressure": 1010,
                    "humidity": 65,
                    "wind_speed": 3.8,
                    "wind_deg": 210,
                    "clouds": 45
                }
            ]
        }

# Получение направления ветра
def get_wind_direction(degrees):
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    index = round(degrees / 45) % 8
    return directions[index]

# Определение фазы луны
def get_moon_phase():
    # Простое определение фазы луны на основе текущей даты
    # В реальности нужно использовать астрономические расчеты
    current_day = datetime.now().day
    month_days = 30  # приблизительно
    
    moon_phase_day = current_day % 30
    
    if moon_phase_day < 2:
        return {"phase": 0, "name": "Новолуние 🌑", "fishing_factor": 0.7}
    elif moon_phase_day < 7:
        return {"phase": 1, "name": "Растущий серп 🌒", "fishing_factor": 0.8}
    elif moon_phase_day < 9:
        return {"phase": 2, "name": "Первая четверть 🌓", "fishing_factor": 0.9}
    elif moon_phase_day < 14:
        return {"phase": 3, "name": "Растущая луна 🌔", "fishing_factor": 0.85}
    elif moon_phase_day < 16:
        return {"phase": 4, "name": "Полнолуние 🌕", "fishing_factor": 1.0}
    elif moon_phase_day < 21:
        return {"phase": 5, "name": "Убывающая луна 🌖", "fishing_factor": 0.85}
    elif moon_phase_day < 23:
        return {"phase": 6, "name": "Последняя четверть 🌗", "fishing_factor": 0.75}
    elif moon_phase_day < 28:
        return {"phase": 7, "name": "Убывающий серп 🌘", "fishing_factor": 0.7}
    else:
        return {"phase": 0, "name": "Новолуние 🌑", "fishing_factor": 0.7}

# Расчет вероятности клёва на основе погодных условий
def calculate_bite_probability(weather_data, moon_phase):
    probability = 50  # Базовая вероятность
    positive_factors = []
    negative_factors = []
    
    # Фактор температуры
    temp = weather_data['temp']['day']
    if 15 <= temp <= 25:
        probability += 15
        positive_factors.append(f"Оптимальная температура ({temp}°C)")
    elif 10 <= temp < 15 or 25 < temp <= 30:
        probability += 5
        positive_factors.append(f"Приемлемая температура ({temp}°C)")
    elif temp < 5 or temp > 35:
        probability -= 20
        negative_factors.append(f"Неблагоприятная температура ({temp}°C)")
    elif 5 <= temp < 10 or 30 < temp <= 35:
        probability -= 10
        negative_factors.append(f"Не очень благоприятная температура ({temp}°C)")
    
    # Фактор ветра
    wind_speed = weather_data['wind_speed']
    if wind_speed < 2:
        probability += 10
        positive_factors.append("Слабый ветер")
    elif 2 <= wind_speed <= 5:
        probability += 5
        positive_factors.append("Умеренный ветер")
    elif 5 < wind_speed <= 8:
        probability -= 5
        negative_factors.append("Сильный ветер")
    else:
        probability -= 15
        negative_factors.append("Очень сильный ветер")
    
    # Фактор давления и его стабильности
    # Для простоты принимаем стандартное давление как благоприятное
    pressure = weather_data['pressure']
    if 1010 <= pressure <= 1020:
        probability += 10
        positive_factors.append("Стабильное атмосферное давление")
    elif (1000 <= pressure < 1010) or (1020 < pressure <= 1030):
        probability += 0
    else:
        probability -= 10
        negative_factors.append("Нестабильное атмосферное давление")
    
    # Фактор облачности
    clouds = weather_data['clouds']
    if 30 <= clouds <= 70:
        probability += 10
        positive_factors.append("Переменная облачность")
    elif clouds < 30:
        probability += 5
        positive_factors.append("Ясная погода")
    else:
        probability -= 5
        negative_factors.append("Пасмурная погода")
    
    # Фактор осадков
    if 'rain' in weather_data and weather_data['rain'] > 0:
        rain = weather_data['rain']
        if rain < 2:
            probability += 5  # Небольшой дождь может увеличить активность рыбы
            positive_factors.append("Легкий дождь")
        elif 2 <= rain <= 5:
            probability -= 5
            negative_factors.append("Умеренный дождь")
        else:
            probability -= 15
            negative_factors.append("Сильный дождь")
    
    # Фактор фазы луны
    moon_factor = moon_phase['fishing_factor']
    probability *= moon_factor
    
    if moon_factor >= 0.9:
        positive_factors.append(f"Благоприятная фаза луны ({moon_phase['name']})")
    elif moon_factor <= 0.7:
        negative_factors.append(f"Неблагоприятная фаза луны ({moon_phase['name']})")
    
    # Убеждаемся, что вероятность в пределах от 0 до 100
    probability = max(0, min(100, probability))
    
    return probability, {"positive": positive_factors, "negative": negative_factors}

# Получение текстового рейтинга клёва на основе вероятности
def get_bite_rating(probability):
    if probability >= 80:
        return "🔥🔥🔥🔥🔥 Отличный клёв"
    elif probability >= 60:
        return "🔥🔥🔥🔥 Хороший клёв"
    elif probability >= 40:
        return "🔥🔥🔥 Средний клёв"
    elif probability >= 20:
        return "🔥🔥 Слабый клёв"
    else:
        return "🔥 Очень слабый клёв"

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return CHOOSING_ACTION
        
    text = update.message.text
    
    # Создаем инлайн клавиатуру для возврата в главное меню
    buttons = [[InlineKeyboardButton("🔄 Вернуться в главное меню", callback_data="restart")]]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if text.startswith("/"):
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки меню для навигации.",
            reply_markup=reply_markup
        )
    else:
        # Если мы ожидаем ввод локации
        if context.user_data.get('expecting_location'):
            context.user_data['expecting_location'] = False
            return await location_received(update, context)
            
    return CHOOSING_ACTION

# Основная функция
def main():
    # Получаем токен бота из переменной окружения
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Пожалуйста, установите переменную окружения TELEGRAM_BOT_TOKEN")
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Добавляем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_ACTION: [
                CommandHandler("help", help_command),
                CommandHandler("forecast", forecast_command),
                CommandHandler("locations", show_locations),
                CommandHandler("add_location", add_location),
                CallbackQueryHandler(button_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            ],
            ADDING_LOCATION: [
                CallbackQueryHandler(button_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_received),
            ],
            SELECTING_LOCATION: [
                CallbackQueryHandler(button_callback),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_callback, pattern="^restart$")
        ],
    )
    
    application.add_handler(conv_handler)
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()