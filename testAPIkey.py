import requests

api_key = "fbad7bcd81483d70eaaf42321770286c"
lat = 55.7522  # Координаты Москвы из предыдущего ответа
lon = 37.6156

url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly&appid={api_key}&units=metric"
print(f"Отправляю запрос: {url}")

response = requests.get(url)
print(f"Код ответа: {response.status_code}")
print(f"Ответ: {response.text}")