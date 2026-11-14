# tools.py
import requests
import urllib.parse
import re
import random
from math import radians, sin, cos, asin, sqrt

WEATHER_TRANSLATION = {"Sunny": "Солнечно", "Clear": "Ясно", "Partly cloudy": "Переменная облачность", "Cloudy": "Облачно", "Overcast": "Пасмурно", "Light rain": "Небольшой дождь", "Moderate rain": "Дождь", "Heavy rain": "Сильный дождь", "Light snow": "Небольшой снег", "Moderate snow": "Снег", "Heavy snow": "Сильный снег"}

def get_real_weather(city_name: str = "Уфа") -> str:
    try:
        res = requests.get(f"https://wttr.in/{city_name}?format=j1", timeout=10).json()
        curr = res['current_condition'][0]
        return f"{curr['temp_C']}°C, {WEATHER_TRANSLATION.get(curr['weatherDesc'][0]['value'].strip(), '')}"
    except: return "Данные недоступны"

def get_news_ufa() -> str:
    try:
        res = requests.get("https://news.mail.ru/rss/ufa/", timeout=5)
        res.encoding = 'utf-8'
        match = re.search(r'<item>.*?<title>(.*?)</title>', res.text, re.DOTALL)
        if match: return re.sub(r'<[^>]+>', '', re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', match.group(1).strip()))
    except: pass
    return "В Уфе всё спокойно."

def get_currency() -> str:
    try:
        res = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=5).json()
        return f"Доллар: {res['Valute']['USD']['Value']:.2f}, Евро: {res['Valute']['EUR']['Value']:.2f}"
    except: return "Курсы скрыты."

def get_traffic() -> str: return f"{random.randint(4, 8)} баллов из 10"

def dist_m(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2-p1)/2)**2 + cos(p1)*cos(p2)*sin(radians(lon2-lon1)/2)**2
    return 12742000 * asin(sqrt(a))

RESTAURANTS = {
    "national": [
        {"name": "Ресторан «Башкирия»", "desc": "Гастрономические традиции тюркских народов и русской кухни.", "full_desc": "Ресторан при одноименной гостинице славится взаимодействием гастрономических традиций с кухнями ближайших тюркских народов, а также с русской кухней.", "address": "ул. Ленина, 25/29", "hours": "12:00–00:00", "avg_check": "1500 ₽", "rating": "4.6", "coords": (54.7267, 55.9500), "image": "/static/img/bashkiriya.jpg"},
        {"name": "Terra Bashkiria", "desc": "Современная башкирская кухня в историческом центре.", "full_desc": "Заведение находится в исторической части города. Рекомендуем отведать конину на ребрах, запеченную мозговую кость и бишбармак.", "address": "ул. Заки Валиди, 2", "hours": "12:00–23:00", "avg_check": "2000 ₽", "rating": "4.8", "coords": (54.7214, 55.9421), "image": "/static/img/terra_bashkiria.jpg"}
    ],
    "coffee": [
        {"name": "Кофейня №1", "desc": "Уютное место с отличным кофе.", "full_desc": "Заглушка для демонстрации.", "address": "ул. Ленина, 10", "hours": "08:00–22:00", "avg_check": "400 ₽", "rating": "4.7", "coords": (54.7267, 55.9500), "image": "/static/img/coffee_1.jpg"},
        {"name": "Кофейня №2", "desc": "Спешелти кофе и свежая выпечка.", "full_desc": "Заглушка для демонстрации.", "address": "ул. Коммунистическая, 20", "hours": "09:00–21:00", "avg_check": "500 ₽", "rating": "4.5", "coords": (54.7267, 55.9500), "image": "/static/img/coffee_2.jpg"}
    ],
    "budget": [
        {"name": "Дом башкирской кухни", "desc": "Бюджетно, домашняя атмосфера.", "full_desc": "Отличное место, чтобы попробовать национальную кухню без лишних затрат. Домашняя атмосфера и большие порции.", "address": "ул. Ленина, 72", "hours": "11:00–23:00", "avg_check": "600 ₽", "rating": "4.7", "coords": (54.7342, 55.9517), "image": "/static/img/dom_bashkirskoy_kuhni.jpg"},
        {"name": "Кафе Площадь двух фонтанов", "desc": "Быстрый перекус в центре.", "full_desc": "Кафе с демократичными ценами и приятной атмосферой.", "address": "ул. Ленина, 65/2", "hours": "11:00–23:00", "avg_check": "500 ₽", "rating": "4.5", "coords": (54.7267, 55.9500), "image": "/static/img/dva_fontana.jpg"}
    ],
    "premium": [
        {"name": "Вид сверху", "desc": "Панорамный вид, высокий чек.", "full_desc": "Ресторан на крыше с потрясающим видом на город.", "address": "пр. Октября, 31", "hours": "12:00–02:00", "avg_check": "4000 ₽", "rating": "4.8", "coords": (54.7388, 55.9721), "image": "/static/img/vid_sverhu.jpg"},
        {"name": "Маяковский", "desc": "Культовое место, атмосфера конструктивизма.", "full_desc": "Кафе «Маяковский» — это культовое место в Уфе. Здесь подают отличный кофе, десерты и завтраки.", "address": "ул. Коммунистическая, 60", "hours": "09:00–00:00", "avg_check": "1500 ₽", "rating": "4.6", "coords": (54.7267, 55.9500), "image": "/static/img/mayakovskiy.jpg"}
    ],
    "kids": [
        {"name": "Сойка", "desc": "Игровая зона, детское меню.", "full_desc": "Семейное кафе «Сойка» — это место, где родители могут отдохнуть, а дети — поиграть.", "address": "ул. Менделеева, 137", "hours": "10:00–22:00", "avg_check": "700 ₽", "rating": "4.8", "coords": (54.7275, 55.9680), "image": "/static/img/soyka.jpg"},
        {"name": "Азык-Тулек", "desc": "Национальная кухня, живая музыка.", "full_desc": "Ресторан «Азык-Тулек» — это настоящий уголок башкирской культуры в центре Уфы.", "address": "ул. Чернышевского, 82", "hours": "12:00–00:00", "avg_check": "1200 ₽", "rating": "4.7", "coords": (54.7285, 55.9478), "image": "/static/img/azyk_tulek.jpg"}
    ]
}

ATTRACTIONS = {
    "history": [
        {"name": "Дом-музей Ш.А. Худайбердина", "desc": "Мемориальный дом-музей революционера и писателя Шагита Худайбердина.", "full_desc": "Дом-музей Ш.А. Худайбердина — это филиал Национального музея Республики Башкортостан.", "address": "ул. Новомостовая, 20", "hours": "Вт-Пт: 11:00–18:00, Сб: 13:00–21:00", "price": "Взрослый: 150 ₽", "rating": "4.2", "coords": (54.7194, 55.9557), "image": "/static/img/muzei_hudaiberdina.jpg"},
        {"name": "Республиканский музей Боевой Славы", "desc": "Музей в Парке Победы, посвящённый вкладу Башкирии в Великую Отечественную войну.", "full_desc": "Республиканский музей Боевой Славы расположен в Парке Победы на высоком берегу реки Белой.", "address": "ул. Комарова, 7 (Парк Победы)", "hours": "Вт-Вс: 11:00–18:00 (Чт до 21:00)", "price": "Взрослый: 55 ₽", "rating": "4.7", "coords": (54.8218, 56.0571), "image": "/static/img/muzei_boevoy_slavy.jpg"},
        {"name": "Мемориальный дом-музей С.Т. Аксакова", "desc": "Старинный особняк, где прошли детские годы писателя Сергея Аксакова.", "full_desc": "Мемориальный дом-музей С.Т. Аксакова — уникальный историко-культурный объект Уфы.", "address": "ул. Зайнуллы Расулева, 4", "hours": "Вт-Сб: 11:00–18:00", "price": "Взрослый: 100 ₽", "rating": "4.7", "coords": (54.7135, 55.9516), "image": "/static/img/muzei_aksakova.jpg"},
        {"name": "Музей истории города Уфы", "desc": "Современный музей об истории и развитии Уфы.", "full_desc": "Музей истории города Уфы открылся в 2019 году.", "address": "ул. Ленина, 72", "hours": "Вт-Вс: 10:00–19:30", "price": "Взрослый: 150 ₽", "rating": "4.5", "coords": (54.7342, 55.9517), "image": "/static/img/muzei_istorii_ufy.jpg"}
    ],
    "nature": [
        {"name": "Парк Кашкадан", "desc": "Озеро, прогулки, велосипеды, ночные фонтаны.", "full_desc": "Парк Кашкадан — это большой парк с озером в центре Уфы. Вечером включаются красивые светомузыкальные фонтаны.", "address": "ул. Маршала Жукова, 31", "hours": "Круглосуточно", "price": "Вход свободный", "rating": "4.8", "coords": (54.7722, 55.9483), "image": "/static/img/kashkadan.jpg"},
        {"name": "Уфимское ожерелье", "desc": "Смотровая площадка, виды на реку, арка.", "full_desc": "«Уфимское ожерелье» — это смотровая площадка на высоком берегу реки Белой.", "address": "ул. Менделеева, 205", "hours": "Круглосуточно", "price": "Вход свободный", "rating": "4.9", "coords": (54.7267, 55.9500), "image": "/static/img/ufa_ozherelye.jpg"}
    ],
    "symbols": [
        {"name": "Колоннада на набережной", "desc": "Красивая архитектура у воды, закаты.", "full_desc": "Колоннада на набережной реки Белой — это любимое место прогулок уфимцев и гостей города.", "address": "ул. Набережная", "hours": "Круглосуточно", "price": "Вход свободный", "rating": "4.8", "coords": (54.7267, 55.9500), "image": "/static/img/kolonnada.jpg"},
        {"name": "Памятник Ленину перед Горсоветом", "desc": "Главная площадь города, памятник Ленину.", "full_desc": "Площадь Ленина — это главная площадь Уфы, где проходят все городские праздники.", "address": "ул. Ленина", "hours": "Круглосуточно", "price": "Вход свободный", "rating": "4.8", "coords": (54.7267, 55.9500), "image": "/static/img/lenin.jpg"},
        {"name": "Советская площадь", "desc": "Фонтаны, архитектура, Дом Правительства.", "full_desc": "Советская площадь — это административный центр города. Здесь находится Дом Правительства и красивые фонтаны.", "address": "ул. Заки Валиди", "hours": "Круглосуточно", "price": "Вход свободный", "rating": "4.7", "coords": (54.7214, 55.9421), "image": "/static/img/sovetskaya.jpg"},
        {"name": "Парк Победы (Вечный огонь)", "desc": "Мемориал, Вечный огонь, панорама города.", "full_desc": "Парк Победы — это мемориальный комплекс, посвящённый победе в Великой Отечественной войне.", "address": "ул. Комарова, 7", "hours": "Круглосуточно", "price": "Вход свободный", "rating": "4.9", "coords": (54.8218, 56.0571), "image": "/static/img/park_pobedy.jpg"}
    ]
}

HOTELS = [
    {"name": "Отель Азимут", "desc": "Современный 4* отель в центре, рядом с набережной.", "full_desc": "Отель «Азимут» — современный 4-звездочный отель в сердце Уфы.", "address": "пр. Октября, 31", "hours": "Круглосуточно", "avg_check": "от 5000 ₽/ночь", "rating": "4.8", "phone": "+73472220000", "coords": (54.7431, 55.9721), "image": "/static/img/azimut.jpg"},
    {"name": "Гостиница Башкирия", "desc": "Историческое здание в центре города.", "full_desc": "Гостиница «Башкирия» — историческое здание в центре Уфы.", "address": "ул. Ленина, 25/29", "hours": "Круглосуточно", "avg_check": "от 4000 ₽/ночь", "rating": "4.5", "phone": "+73472250000", "coords": (54.7269, 55.9438), "image": "/static/img/bashkiriya_hotel.jpg"},
    {"name": "Hampton by Hilton Ufa", "desc": "3* отель в центре, современный.", "full_desc": "Hampton by Hilton Ufa — современный 3-звездочный отель в центре города.", "address": "ул. Цюрупы, 32", "hours": "Круглосуточно", "avg_check": "от 4500 ₽/ночь", "rating": "4.7", "phone": "+73472260000", "coords": (54.7295, 55.9465), "image": "/static/img/hilton.jpg"},
    {"name": "Бутик-отель Пушкин", "desc": "Уютный отель у памятника Салавату.", "full_desc": "Бутик-отель «Пушкин» — уютное место рядом с главной достопримечательностью Уфы.", "address": "ул. Пушкина, 1", "hours": "Круглосуточно", "avg_check": "от 6000 ₽/ночь", "rating": "4.9", "phone": "+73472270000", "coords": (54.7238, 55.9412), "image": "/static/img/pushkin.jpg"},
    {"name": "Гостиница Иремель", "desc": "Бюджетный вариант в центре.", "full_desc": "Гостиница «Иремель» — бюджетный вариант в центре города.", "address": "ул. Менделеева, 137", "hours": "Круглосуточно", "avg_check": "от 2500 ₽/ночь", "rating": "4.3", "phone": "+73472280000", "coords": (54.7275, 55.9680), "image": "/static/img/iremel.jpg"}
]

APARTMENTS = [
    {"name": "Уютная студия на Ленина", "desc": "Светлая студия в самом центре. Рядом Гостиный двор и кафе.", "full_desc": "Светлая студия в самом центре Уфы. Идеально для двоих.", "address": "ул. Ленина, 15", "hours": "Круглосуточно", "avg_check": "2500 ₽/сутки", "rating": "4.9", "phone": "+79871112233", "coords": (54.7267, 55.9500), "image": "/static/img/apartment_1.jpg"},
    {"name": "Апартаменты у Гостиного двора", "desc": "Просторные апартаменты с видом на исторический центр.", "full_desc": "Просторные апартаменты с видом на исторический центр.", "address": "ул. Верхнеторговая, 5", "hours": "Круглосуточно", "avg_check": "3500 ₽/сутки", "rating": "4.8", "phone": "+79872223344", "coords": (54.7150, 55.9450), "image": "/static/img/apartment_2.jpg"}
]

DELIVERY_PLACES = {
    "pizza": {"title": "🍕 Додо Пицца", "text": "Отличный выбор! Доставка займет 30-40 минут. Адрес уже подставлен.", "url": "https://dodopizza.ru/ufa"},
    "sushi": {"title": "🍣 Фудзияма", "text": "Свежие роллы и суши. Доставка 40-50 минут. Адрес подставлен.", "url": "https://fujiyama.ru/"},
    "grocery": {"title": "🛒 Магнит Доставка", "text": "Продукты и всё необходимое прямо к двери. Доставка от 45 минут.", "url": "https://magnit.ru/"}
}

KNOWN_ADDRESSES = {
    "термы стерлитамак": (53.6303, 55.9503), "гостиный двор": (54.7150, 55.9450),
    "дом аксакова": (54.7135, 55.9516), "парк кашкадан": (54.7722, 55.9483),
    "железнодорожный вокзал уфа": (54.7488, 55.9617), "аэропорт уфа": (54.5575, 55.8736),
    "павловка": (54.4333, 56.8833), "азимут": (54.7431, 55.9721),
    "конгресс-холл": (54.7214, 55.9421), "площадь ленина": (54.7267, 55.9500),
    "набережная": (54.7267, 55.9500), "музей худайбердина": (54.7194, 55.9557),
    "музей боевой славы": (54.8218, 56.0571), "музей истории уфы": (54.7342, 55.9517),
    "музей истории города уфы": (54.7342, 55.9517), "дом башкирской кухни": (54.7342, 55.9517),
    "советская площадь": (54.7214, 55.9421), "уфимское ожерелье": (54.7267, 55.9500),
    "terra bashkiria": (54.7214, 55.9421), "колоннада на набережной": (54.7267, 55.9500),
    "парк победы": (54.8218, 56.0571)
}

CITY_ZONES = {
    "ufa_center": {"coords": (54.7267, 55.9500), "radius": 3000},
    "ufa": {"coords": (54.7388, 55.9721), "radius": 25000},
    "sterlitamak": {"coords": (53.6304, 55.9310), "radius": 15000},
    "pavlovka": {"coords": (54.4333, 56.8833), "radius": 10000},
}

def current_zone(lat, lon):
    if dist_m(lat, lon, *CITY_ZONES["ufa_center"]["coords"]) <= CITY_ZONES["ufa_center"]["radius"]: return "ufa_center"
    if dist_m(lat, lon, *CITY_ZONES["ufa"]["coords"]) <= CITY_ZONES["ufa"]["radius"]: return "ufa"
    if dist_m(lat, lon, *CITY_ZONES["sterlitamak"]["coords"]) <= CITY_ZONES["sterlitamak"]["radius"]: return "sterlitamak"
    if dist_m(lat, lon, *CITY_ZONES["pavlovka"]["coords"]) <= CITY_ZONES["pavlovka"]["radius"]: return "pavlovka"
    return "bashkortostan"

def get_auto_map_link(start_lat, start_lon, end_lat, end_lon):
    return f"https://yandex.ru/maps/?rtext={start_lat},{start_lon}~{end_lat},{end_lon}&rtt=auto"

def get_walk_map_link(start_lat, start_lon, end_lat, end_lon):
    return f"https://yandex.ru/maps/?rtext={start_lat},{start_lon}~{end_lat},{end_lon}&rtt=pd"

def get_bus_map_link(start_lat, start_lon, end_lat, end_lon):
    return f"https://yandex.ru/maps/?rtext={start_lat},{start_lon}~{end_lat},{end_lon}&rtt=mt"

def get_taxi_link(start_lat, start_lon, end_lat, end_lon, tariff="econom"):
    q = {"start-lat": start_lat, "start-lon": start_lon, "end-lat": end_lat, "end-lon": end_lon, "tariffClass": tariff, "ref": "uje", "appmetrica_tracking_id": "25395763362139037"}
    return "https://3.redirect.appmetrica.yandex.com/route?" + urllib.parse.urlencode(q)

def _normalize_for_match(text: str) -> str:
    text = text.lower()
    for suffix in [", республика башкортостан", ", башкортостан", ", уфа"]: text = text.replace(suffix, "")
    return text.strip()

def _find_known_address(query: str):
    normalized = _normalize_for_match(query)
    for key, coords in KNOWN_ADDRESSES.items():
        if key in normalized: return coords
    return None

def geocode_address(address: str, city: str = "Уфа"):
    known = _find_known_address(address)
    if known: return known
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address + ', ' + city)}&format=json&limit=1"
        res = requests.get(url, headers={'User-Agent': 'BASHGID/1.0'}, timeout=5).json()
        if res: return float(res[0]['lat']), float(res[0]['lon'])
    except: pass
    return None, None

DEMO_ROUTES = {
    "Музей истории города Уфы": {"bus": ["Выйди из отеля, иди до остановки 'Горсовет' (на стороне Азимута).", "Садись на автобус 167, 167п или 110. Едь 2 остановки.", "Выйди на остановке 'Ленина'. Музей в 3 минутах пешком по улице Ленина."]},
    "Terra Bashkiria": {"bus": ["Иди до остановки 'Горсовет' (на стороне Азимута).", "Садись на 167, 167п или 110. Едь 3 остановки.", "Выйди на остановке 'Конгресс-холл'. Заведение в 2 минутах пешком."]},
    "Памятник Ленину перед Горсоветом": {"walk": ["Ты уже на месте! Памятник Ленину прямо перед тобой."]},
    "Республиканский музей Боевой Славы": {"bus": ["Перейди на противоположную сторону от отеля Азимут (к остановке 'Горсовет' в сторону Парка Победы).", "Садись на автобус 249, 69 или 258.", "Доезжай до остановки 'БГУ'. Выйди.", "Дальше пешком около 2 км в сторону Парка Победы."]},
    "Парк Победы (Вечный огонь)": {"bus": ["Перейди на противоположную сторону от Азимута.", "Садись на 249, 69 или 258. Доезжай до 'БГУ'.", "Выйди и иди прямо по аллее в сторону Парка Победы (около 2 км)."]},
    "Сойка": {"bus": ["Иди до остановки 'Горсовет' (сторона Азимута).", "Садись на 167п. Едь до остановки 'Гостиный двор'.", "Выйди, пересядь на автобус 74.", "Доезжай до остановки 'ТРК Иремель'. Выйди.", "Пешком 3 минуты до входа в ТРК."]},
    "Парк Кашкадан": {"bus": ["Иди до остановки 'Горсовет' (сторона Азимута).", "Садись на 110. Едь до остановки 'Центральный рынок'.", "Пересядь на автобус 288.", "Доезжай до остановки 'Кашкадан'. Выйди.", "Пешком 5 минут до входа в парк."]}
}

DEMO_INTEREST_ROUTES = {
    "history": {
        "title": "🏛 История и музеи",
        "steps": [
            {"text": "🕒 10:00 — Музей истории города Уфы (ул. Ленина, 72)", "action": "[ri_details:attr_history:Музей истории города Уфы]", "place": "Музей истории города Уфы"},
            {"text": "🕒 13:00 — Обед в «Доме башкирской кухни» (ул. Ленина, 72)", "action": "[ri_details:cat_budget:Дом башкирской кухни]", "place": "Дом башкирской кухни"},
            {"text": "🕒 15:00 — Прогулка по Советской площади", "action": "[ri_details:attr_symbols:Советская площадь]", "place": "Советская площадь"}
        ]
    },
    "nature": {
        "title": "🌳 Природа и прогулки",
        "steps": [
            {"text": "🕒 11:00 — Прогулка в Парке Кашкадан (у озера)", "action": "[ri_details:attr_nature:Парк Кашкадан]", "place": "Парк Кашкадан"},
            {"text": "🕒 14:00 — Перекус в кафе «Сойка» (рядом с парком)", "action": "[ri_details:cat_kids:Сойка]", "place": "Сойка"},
            {"text": "🕒 16:00 — Смотровая площадка «Уфимское ожерелье»", "action": "[ri_details:attr_nature:Уфимское ожерелье]", "place": "Уфимское ожерелье"}
        ]
    },
    "food": {
        "title": "🍽 Гастрономия",
        "steps": [
            {"text": "🕒 12:00 — Обед в ресторане «Terra Bashkiria» (ул. Заки Валиди, 2)", "action": "[ri_details:cat_national:Terra Bashkiria]", "place": "Terra Bashkiria"},
            {"text": "🕒 15:00 — Кофе и десерты в «Маяковском» (ул. Коммунистическая, 60)", "action": "[ri_details:cat_premium:Маяковский]", "place": "Маяковский"},
            {"text": "🕒 18:00 — Ужин в ресторане «Вид сверху» (пр. Октября, 31)", "action": "[ri_details:cat_premium:Вид сверху]", "place": "Вид сверху"}
        ]
    },
    "mix": {
        "title": "🚶 Всё сразу (микс)",
        "steps": [
            {"text": "🕒 10:00 — Музей истории города Уфы (ул. Ленина, 72)", "action": "[ri_details:attr_history:Музей истории города Уфы]", "place": "Музей истории города Уфы"},
            {"text": "🕒 13:00 — Обед в «Доме башкирской кухни» (ул. Ленина, 72)", "action": "[ri_details:cat_budget:Дом башкирской кухни]", "place": "Дом башкирской кухни"},
            {"text": "🕒 15:00 — Прогулка по набережной реки Белой", "action": "[ri_details:attr_symbols:Колоннада на набережной]", "place": "Колоннада на набережной"}
        ]
    },
    "bad_weather_offer": {
        "title": "🏛 История и музеи (в помещении)",
        "steps": [
            {"text": "🕒 10:00 — Музей истории города Уфы (ул. Ленина, 72)", "action": "[ri_details:attr_history:Музей истории города Уфы]", "place": "Музей истории города Уфы"},
            {"text": "🕒 13:00 — Обед в «Доме башкирской кухни» (ул. Ленина, 72)", "action": "[ri_details:cat_budget:Дом башкирской кухни]", "place": "Дом башкирской кухни"},
            {"text": "🕒 15:00 — Республиканский музей Боевой Славы", "action": "[ri_details:attr_history:Республиканский музей Боевой Славы]", "place": "Республиканский музей Боевой Славы"}
        ]
    }
}