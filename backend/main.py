import asyncio
import json
from typing import List
from fastapi import FastAPI, File, HTTPException, Body, status, Request, Form, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import httpx
from pydantic import BaseModel
import sqlite3
from itsdangerous import URLSafeTimedSerializer
import os
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid

# В начало main.py добавьте:
import concurrent.futures

# Создаем пул потоков для параллельной обработки
THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=10)
# Импортируем structlog
import structlog
def log_user_action(user_id: int, prompt_name: str, action: str, recipe_name: str = None):
    con = sqlite3.connect("../bd/my_database.db", timeout=30, check_same_thread=False)
    cursor = con.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute(
        "INSERT INTO PromptUsage (id_user, prompt_name, user_action, recipe_name) VALUES (?, ?, ?, ?)",
        (user_id, prompt_name, action, recipe_name)
    )
    con.commit()
    con.close()


# Настройка structlog
def setup_structlog():
    """Простая и рабочая настройка structlog"""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer()  # Читаемый вывод в консоль
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

def setup_file_logging():
    """Настройка записи логов в файл"""
    import logging
    
    # Создаем директорию для логов
    Path("./logs").mkdir(exist_ok=True)
    
    # Настраиваем базовый logging для файла
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("./logs/app.log", encoding='utf-8'),
            logging.StreamHandler()  # Также выводим в консоль
        ]
    )

# Инициализация логирования
setup_structlog()
setup_file_logging()  # Добавьте эту строку
logger = structlog.get_logger()

# Тестовое сообщение при запуске
logger.info("Structlog инициализирован", status="ready")



# Секретный ключ (в реальном проекте храните в переменных окружения!)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
serializer = URLSafeTimedSerializer(SECRET_KEY)

app = FastAPI()

# Логирование запуска приложения
logger.info("FastAPI application starting", secret_key_configured=bool(SECRET_KEY))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или список доверенных доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем шаблоны
templates = Jinja2Templates(directory="../public")

# Подключаем статические файлы (CSS, JS, изображения и т.д.)
app.mount("/static", StaticFiles(directory="../public"), name="static")
app.mount("/uploads", StaticFiles(directory="../public/uploads"), name="uploads")

# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    request_id = str(uuid.uuid4())[:8]
    
    # Добавляем request_id в контекст
    structlog.contextvars.bind_contextvars(request_id=request_id)
    
    # Логируем входящий запрос
    logger.info(
        "request_started",
        method=request.method,
        url=str(request.url),
        client_host=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        
        # Логируем успешный ответ
        logger.info(
            "request_completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time
        )
        
        return response
        
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        
        # Логируем ошибку
        logger.error(
            "request_failed",
            method=request.method,
            url=str(request.url),
            error=str(e),
            process_time=process_time,
            exc_info=True
        )
        
        raise
    finally:
        # Очищаем контекст
        structlog.contextvars.clear_contextvars()

# авторизация
@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request, error: str = None):
    logger.info("auth_page_accessed", error_present=error is not None)
    return templates.TemplateResponse("auth.html", {"request": request, "error": error})

@app.post("/auth")
async def handle_form(request: Request, email: str = Form(...), password: str = Form(...)):
    logger.info("auth_attempt", email=email)
    
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    # Ищем пользователя по email
    cursor.execute("SELECT id_user, password FROM User WHERE email = ?", (email,))
    result = cursor.fetchone()
    
    con.close()

    if result is None:
        # Пользователь не найден
        logger.warning("auth_failed", reason="user_not_found", email=email)
        return templates.TemplateResponse("auth.html", {
            "request": request,
            "error": "Пользователь с таким email не найден",
            "email": email
        })
    
    if result[1] != password:
        # Неверный пароль
        logger.warning("auth_failed", reason="invalid_password", email=email, user_id=result[0])
        return templates.TemplateResponse("auth.html", {
            "request": request,
            "error": "Неверный пароль",
            "email": email
        })

    # Успешная авторизация
    logger.info("auth_successful", user_id=result[0], email=email)
    
    # Создаём подписанную cookie с user_id
    session_data = serializer.dumps(result[0])

    response = RedirectResponse(url="/upload", status_code=303)
    response.set_cookie(key="session", value=session_data, httponly=True, max_age=3600)
    return response

# Регистрация
@app.get("/registration", response_class=HTMLResponse)
async def get_form(request: Request):
    logger.info("registration_page_accessed")
    return templates.TemplateResponse("reg.html", {"request": request})

@app.post("/reg")
async def handle_form(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    logger.info("registration_attempt", name=name, email=email)
    
    data = (email, name, password)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # добавляем строку в таблицу User
        cursor.execute("INSERT INTO User (email, login, password) VALUES (?, ?, ?)", data)
        # выполняем транзакцию
        con.commit() 
        cursor.execute("select id_user, password from User where email = (?)", (email,))
        result = cursor.fetchone()
        
        logger.info("registration_successful", user_id=result[0], email=email)
        
    except Exception as e:
        logger.error("registration_failed", email=email, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при регистрации")
    finally:
        con.close()

    # Автоматическая авторизация после регистрации
    session_data = serializer.dumps(result[0])
    response = RedirectResponse(url="/upload", status_code=303)
    response.set_cookie(key="session", value=session_data, httponly=True, max_age=3600)
    return response

def get_current_user(request: Request):
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        return None
    try:
        id_user = serializer.loads(session_cookie, max_age=3600)
        return id_user
    except Exception as e:
        logger.warning("invalid_session_cookie", error=str(e))
        return None

# Заранее заготовленные продукты и рецепты для теста
products_by_file = {
    "1.jpg": ["сыр", "перец", "броколи", "курица"],
    "2.jpg": ["сыр", "творог", "яйца", "молоко"],
    "3.jpg": ["орехи", "рыба", "яйца", "авокадо", "грибы", "яблоки"],
}

recipes_by_file = {
    "1.jpg": [
        {
            "title": "Курица с брокколи и сыром",
            "steps": "Нарежьте курицу и брокколи. Обжарьте на сковороде. Добавьте сыр, томите 15 минут."
        },
        {
            "title": "Перец, фаршированный сыром и курицей",
            "steps": "Разрежьте перец, удалите семена. Начините смесью курицы и сыра. Запеките 20 минут."
        },
        {
            "title": "Запеканка из брокколи с курицей и сыром",
            "steps": "Смешайте брокколи, курицу и сыр. Запекайте в духовке при 180°C 30 минут."
        }
    ],
    "2.jpg": [
        {
            "title": "Омлет с творогом и сыром",
            "steps": "1. Взбейте яйца с молоком.\n2. Добавьте творог и натёртый сыр.\n3. Вылейте смесь на сковороду.\n4. Готовьте под крышкой до готовности."
        },
        {
            "title": "Запечённые яйца с молоком и творогом",
            "steps": "1. В миску выложите яйца и творог.\n2. Залейте молоком.\n3. Запекайте в духовке 20 минут при 180°C."
        },
        {
            "title": "Творожная запеканка с молоком и яйцами",
            "steps": "1. Смешайте творог, яйца и молоко.\n2. Переложите в форму.\n3. Запекайте 35 минут при 180°C."
        }
    ],
    "3.jpg": [
        {
            "title": "Рыба с авокадо и орехами",
            "steps": "1. Обжарьте филе рыбы до готовности.\n2. Нарежьте авокадо кубиками.\n3. Посыпьте рыбу орехами и авокадо.\n4. Подавайте с зеленью."
        },
        {
            "title": "Яичница с грибами и яблоками",
            "steps": "1. Нарежьте грибы и яблоки.\n2. Обжарьте грибы на сковороде.\n3. Добавьте яблоки и яйца.\n4. Жарьте до готовности яиц."
        },
        {
            "title": "Салат с рыбой, орехами и авокадо",
            "steps": "1. Смешайте рыбу, орехи и нарезанное авокадо.\n2. Заправьте салат соусом по вкусу.\n3. Подавайте охлаждённым."
        }
    ],
}

@app.get("/result", response_class=HTMLResponse)
async def show_result(request: Request):
    user_id = get_current_user(request)
    logger.info("main_page_accessed", user_id=user_id)
    return templates.TemplateResponse("main.html", {"request": request})

@app.post("/test-vlm", response_class=RedirectResponse)
async def test_vlm(file: UploadFile):
    user_id = get_current_user(request)
    logger.info("file_upload_attempt", user_id=user_id, filename=file.filename, content_type=file.content_type)
    
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        logger.warning("invalid_file_type", filename=file.filename)
        raise HTTPException(status_code=400, detail="Файл должен быть изображением (jpg/png)")

    save_path = Path(f"./public/uploads/{file.filename}")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(save_path, "wb") as f:
            f.write(await file.read())
        logger.info("file_saved_successfully", filename=file.filename, save_path=str(save_path))
    except Exception as e:
        logger.error("file_save_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при сохранении файла")

    # Перенаправляем на страницу с результатами, передаём имя файла
    return RedirectResponse(url=f"/results/{file.filename}", status_code=status.HTTP_303_SEE_OTHER)

# Профиль
@app.get("/profile", response_class=HTMLResponse)
async def get_form(request: Request):
    id_user = get_current_user(request)
    logger.info("profile_page_accessed", user_id=id_user)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # Данные пользователя
        cursor.execute("SELECT email, login, preferences_time, preferences_difficulty, preferences_calorie FROM User WHERE id_user = ?", (id_user,))
        user_data = cursor.fetchone()
        
        if not user_data:
            logger.warning("user_not_found", user_id=id_user)
            raise HTTPException(status_code=404, detail="Пользователь не найден")
            
        email, login, preferences_time, preferences_difficulty, preferences_calorie = user_data

        # Получаем все опции для селекторов
        cursor.execute("SELECT id_cooking_time, title FROM CookingTime")
        cooking_times = cursor.fetchall()

        cursor.execute("SELECT id_difficulty, title FROM Difficulty")
        difficulties = cursor.fetchall()

        cursor.execute("SELECT id_calorie_content, title FROM CalorieContent")
        calorie_contents = cursor.fetchall()

        # Получение запрещённых продуктов
        cursor.execute("""
            SELECT p.title 
            FROM ProductsInProhibited pip 
            JOIN Product p ON pip.id_product = p.id_product
            WHERE pip.id_user = ?
        """, (id_user,))
        forbidden_products = [row[0] for row in cursor.fetchall()]
        
        logger.info("profile_data_loaded", 
                   user_id=id_user, 
                   forbidden_products_count=len(forbidden_products))
        
    except Exception as e:
        logger.error("profile_data_load_failed", user_id=id_user, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при загрузке данных профиля")
    finally:
        con.close()

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "email": email,
        "login": login,
        "cooking_times": cooking_times,
        "difficulties": difficulties,
        "calorie_contents": calorie_contents,
        "current_preferences": {
            "preferences_time": preferences_time,
            "preferences_difficulty": preferences_difficulty,
            "preferences_calorie": preferences_calorie
        },
        "forbidden_products": forbidden_products
    })

# Добавление запрещённого продукта
@app.post("/profile/forbidden")
async def add_forbidden_product(request: Request, product_title: str = Form(...)):
    id_user = get_current_user(request)
    logger.info("adding_forbidden_product", user_id=id_user, product_title=product_title)
    
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # Проверяем есть ли продукт в базе
        cursor.execute("SELECT id_product FROM Product WHERE title = ?", (product_title,))
        row = cursor.fetchone()

        if row:
            id_product = row[0]
        else:
            # Добавляем новый продукт
            cursor.execute("INSERT INTO Product (title) VALUES (?)", (product_title,))
            con.commit()
            id_product = cursor.lastrowid

        # Добавляем запись в запрещённые продукты пользователя, если ещё нет
        cursor.execute("SELECT 1 FROM ProductsInProhibited WHERE id_user = ? AND id_product = ?", (id_user, id_product))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("INSERT INTO ProductsInProhibited (id_user, id_product) VALUES (?, ?)", (id_user, id_product))
            con.commit()
            logger.info("forbidden_product_added", user_id=id_user, product_id=id_product, product_title=product_title)

    except Exception as e:
        logger.error("forbidden_product_add_failed", user_id=id_user, product_title=product_title, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при добавлении продукта")
    finally:
        con.close()

    return RedirectResponse(url="/profile", status_code=303)

# Удаление запрещённого продукта
@app.post("/profile/forbidden/remove")
async def remove_forbidden_product(request: Request, product_title: str = Form(...)):
    id_user = get_current_user(request)
    logger.info("removing_forbidden_product", user_id=id_user, product_title=product_title)
    
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # Находим id продукта
        cursor.execute("SELECT id_product FROM Product WHERE title = ?", (product_title,))
        row = cursor.fetchone()
        
        if row:
            id_product = row[0]
            # Удаляем из запрещённых
            cursor.execute("DELETE FROM ProductsInProhibited WHERE id_user = ? AND id_product = ?", (id_user, id_product))
            con.commit()
            logger.info("forbidden_product_removed", user_id=id_user, product_id=id_product, product_title=product_title)

    except Exception as e:
        logger.error("forbidden_product_remove_failed", user_id=id_user, product_title=product_title, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при удалении продукта")
    finally:
        con.close()

    return RedirectResponse(url="/profile", status_code=303)

@app.post("/profile/preferences")
async def save_preferences(
    request: Request,
    preferences_time: int = Form(...),
    preferences_difficulty: int = Form(...),
    preferences_calorie: int = Form(...)
):
    id_user = get_current_user(request)
    logger.info("saving_preferences", 
               user_id=id_user, 
               time_preference=preferences_time,
               difficulty_preference=preferences_difficulty,
               calorie_preference=preferences_calorie)
    
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        cursor.execute("""
            UPDATE User SET preferences_time = ?, preferences_difficulty = ?, preferences_calorie = ?
            WHERE id_user = ?
        """, (preferences_time, preferences_difficulty, preferences_calorie, id_user))
        con.commit()
        logger.info("preferences_saved_successfully", user_id=id_user)
        
    except Exception as e:
        logger.error("preferences_save_failed", user_id=id_user, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при сохранении предпочтений")
    finally:
        con.close()

    return RedirectResponse(url="/profile", status_code=303)

#результат
@app.get("/results/{filename}", response_class=HTMLResponse)
async def results(request: Request, filename: str):
    user_id = get_current_user(request)
    logger.info("results_page_accessed", user_id=user_id, filename=filename)
    
    filename = filename.lower()

    # Получаем оригинальные продукты и рецепты
    original_products = products_by_file.get(filename, ["Нет данных для этого файла"])
    original_recipes = recipes_by_file.get(filename, [])

    # Получаем ID пользователя и его запрещенные продукты
    forbidden_products = []
    
    if user_id:
        con = sqlite3.connect("../bd/my_database.db")
        cursor = con.cursor()
        cursor.execute("""
            SELECT p.title 
            FROM ProductsInProhibited pip 
            JOIN Product p ON pip.id_product = p.id_product
            WHERE pip.id_user = ?
        """, (user_id,))
        forbidden_products = [row[0].lower() for row in cursor.fetchall()]
        con.close()

    # Фильтруем продукты
    filtered_products = []
    removed_products = []
    
    for product in original_products:
        if product == "Нет данных для этого файла":
            filtered_products.append(product)
            continue
            
        product_lower = product.lower()
        is_forbidden = False
        
        # Проверяем, является ли продукт запрещенным
        for forbidden in forbidden_products:
            # Прямое совпадение или частичное вхождение
            if (forbidden == product_lower or 
                forbidden in product_lower or 
                product_lower in forbidden):
                is_forbidden = True
                break
        
        if not is_forbidden:
            filtered_products.append(product)
        else:
            removed_products.append(product)

    # Фильтруем рецепты, убирая те, которые содержат запрещенные продукты
    filtered_recipes = []
    if forbidden_products and user_id:
        for recipe in original_recipes:
            # Проверяем, содержит ли рецепт запрещенные продукты в названии или шагах
            recipe_text = (recipe.get("title", "") + " " + recipe.get("steps", "")).lower()
            contains_forbidden = any(forbidden in recipe_text for forbidden in forbidden_products)
            
            if not contains_forbidden:
                filtered_recipes.append(recipe)
    else:
        # Если нет запрещенных продуктов или пользователь не авторизован, показываем все рецепты
        filtered_recipes = original_recipes

    logger.info("results_filtered", 
               user_id=user_id,
               filename=filename,
               original_products_count=len(original_products),
               filtered_products_count=len(filtered_products),
               removed_products_count=len(removed_products),
               original_recipes_count=len(original_recipes),
               filtered_recipes_count=len(filtered_recipes))

    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "filename": filename,
        "products": filtered_products,
        "recipes": filtered_recipes,
        "removed_products": removed_products,
        "has_removed_products": len(removed_products) > 0
    })

# История
@app.get("/history", response_class=HTMLResponse)
async def get_history(request: Request):
    id_user = get_current_user(request)
    if not id_user:
        logger.warning("unauthorized_history_access")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info("history_page_accessed", user_id=id_user)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        cursor.execute("""
            SELECT 
                h.id_history, 
                r.title, 
                r.description, 
                h.favorite,
                c.comment
            FROM History h
            JOIN Recipes r ON h.id_recipes = r.id_recipes
            LEFT JOIN Comment c ON c.id_recipe = r.id_recipes AND c.id_user = h.id_user
            WHERE h.id_user = ? AND h.done = 1
            ORDER BY h.id_history DESC
        """, (id_user,))
        rows = cursor.fetchall()
        
        history = [
            {
                "id_history": row[0], 
                "title": row[1], 
                "description": row[2], 
                "favorite": row[3],
                "comment": row[4]
            } 
            for row in rows
        ]

        logger.info("history_data_loaded", user_id=id_user, history_count=len(history))
        
    except Exception as e:
        logger.error("history_data_load_failed", user_id=id_user, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при загрузке истории")
    finally:
        con.close()

    # Получаем flash сообщение из query параметров или cookies
    flash_message = request.query_params.get("message")
    if not flash_message:
        flash_message = request.cookies.get("flash_message")
    
    error_message = request.query_params.get("error")
    if not error_message:
        error_message = request.cookies.get("error_message")

    return templates.TemplateResponse("history.html", {
        "request": request, 
        "history": history,
        "flash_message": flash_message,
        "error_message": error_message
    })

@app.post("/history/favorite/{id_history}")
async def toggle_favorite(id_history: int, request: Request):
    id_user = get_current_user(request)
    if not id_user:
        logger.warning("unauthorized_favorite_toggle")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info("toggle_favorite_request", user_id=id_user, history_id=id_history)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # Проверяем, кому принадлежит запись и достаём prompt_version
        cursor.execute("SELECT id_user, favorite, id_recipes, prompt_version FROM History WHERE id_history = ?", (id_history,))
        row = cursor.fetchone()
        if not row or row[0] != id_user:
            logger.warning("forbidden_favorite_toggle", user_id=id_user, history_id=id_history)
            raise HTTPException(status_code=403, detail="Forbidden")

        current_fav = row[1]
        id_recipes = row[2]
        prompt_version = row[3] if row[3] else "unknown"

        # Получаем название рецепта
        cursor.execute("SELECT title FROM Recipes WHERE id_recipes = ?", (id_recipes,))
        recipe_row = cursor.fetchone()
        recipe_name = recipe_row[0] if recipe_row else "Неизвестный рецепт"

        # Обновляем статус избранного
        new_fav = 0 if current_fav else 1
        cursor.execute("UPDATE History SET favorite = ? WHERE id_history = ?", (new_fav, id_history))
        con.commit()

        # ✅ Логируем действие в PromptUsage
        action_text = "Добавлен рецепт в избранное" if new_fav else "Удален рецепт из избранного"
        try:
            log_user_action(
                id_user,
                prompt_version.lower(),
                action_text,
                recipe_name
            )
            con.commit()
            logger.info("prompt_usage_recorded", user_id=id_user, action=action_text, recipe_name=recipe_name)
        except Exception as e:
            logger.error("prompt_usage_insert_failed", user_id=id_user, error=str(e))

    except Exception as e:
        logger.error("favorite_toggle_failed", user_id=id_user, history_id=id_history, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при обновлении избранного")
    finally:
        con.close()

    return RedirectResponse(url="/history", status_code=303)

# Эндпоинты для комментариев
@app.post("/history/comment/{id_history}")
async def add_comment(id_history: int, request: Request, comment: str = Form("")):
    id_user = get_current_user(request)
    if not id_user:
        logger.warning("unauthorized_comment_attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info("add_comment_request", user_id=id_user, history_id=id_history, comment_length=len(comment))

    # Очищаем комментарий от лишних пробелов
    comment = comment.strip()
    
    if not comment:
        # Если комментарий пустой, удаляем его
        return await delete_comment(id_history, request)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # Проверяем, кому принадлежит запись истории
        cursor.execute("""
            SELECT h.id_user, h.id_recipes 
            FROM History h 
            WHERE h.id_history = ?
        """, (id_history,))
        row = cursor.fetchone()
        
        if not row or row[0] != id_user:
            logger.warning("forbidden_comment_attempt", user_id=id_user, history_id=id_history)
            raise HTTPException(status_code=403, detail="Forbidden")

        id_recipes = row[1]

        # Проверяем, есть ли уже комментарий
        cursor.execute("""
            SELECT id_comment FROM Comment 
            WHERE id_user = ? AND id_recipe = ?
        """, (id_user, id_recipes))
        
        existing_comment = cursor.fetchone()

        if existing_comment:
            # Обновляем существующий комментарий
            cursor.execute("""
                UPDATE Comment SET comment = ? 
                WHERE id_comment = ?
            """, (comment, existing_comment[0]))
            logger.info("comment_updated", user_id=id_user, recipe_id=id_recipes)
        else:
            # Добавляем новый комментарий
            cursor.execute("""
                INSERT INTO Comment (id_user, id_recipe, comment) 
                VALUES (?, ?, ?)
            """, (id_user, id_recipes, comment))
            logger.info("comment_added", user_id=id_user, recipe_id=id_recipes)

        con.commit()
        logger.info("comment_saved_successfully", user_id=id_user, history_id=id_history)

    except Exception as e:
        logger.error("comment_save_failed", user_id=id_user, history_id=id_history, error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении комментария: {str(e)}")
    finally:
        con.close()

    return RedirectResponse(url="/history", status_code=303)

@app.delete("/history/comment/{id_history}")
async def delete_comment(id_history: int, request: Request):
    id_user = get_current_user(request)
    if not id_user:
        logger.warning("unauthorized_comment_delete")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info("delete_comment_request", user_id=id_user, history_id=id_history)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # Проверяем, кому принадлежит запись истории и получаем id_recipe
        cursor.execute("""
            SELECT h.id_user, h.id_recipes 
            FROM History h 
            WHERE h.id_history = ?
        """, (id_history,))
        row = cursor.fetchone()
        
        if not row or row[0] != id_user:
            logger.warning("forbidden_comment_delete", user_id=id_user, history_id=id_history)
            raise HTTPException(status_code=403, detail="Forbidden")

        id_recipes = row[1]

        # Удаляем комментарий
        cursor.execute("""
            DELETE FROM Comment 
            WHERE id_user = ? AND id_recipe = ?
        """, (id_user, id_recipes))

        con.commit()
        logger.info("comment_deleted", user_id=id_user, recipe_id=id_recipes)

        return {"success": True, "message": "Комментарий удален"}

    except Exception as e:
        logger.error("comment_delete_failed", user_id=id_user, history_id=id_history, error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении комментария: {str(e)}")
    finally:
        con.close()

#избранное
@app.get("/favorite", response_class=HTMLResponse)
async def get_favorites(request: Request):
    id_user = get_current_user(request)
    if not id_user:
        logger.warning("unauthorized_favorites_access")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info("favorites_page_accessed", user_id=id_user)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        cursor.execute("""
            SELECT h.id_history, r.title, r.description
            FROM History h
            JOIN Recipes r ON h.id_recipes = r.id_recipes
            WHERE h.id_user = ? AND h.favorite = 1
            ORDER BY h.id_history DESC
        """, (id_user,))
        rows = cursor.fetchall()
        
        favorites = [{"id_history": row[0], "title": row[1], "description": row[2]} for row in rows]
        
        logger.info("favorites_data_loaded", user_id=id_user, favorites_count=len(favorites))
        
    except Exception as e:
        logger.error("favorites_data_load_failed", user_id=id_user, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при загрузке избранного")
    finally:
        con.close()

    return templates.TemplateResponse("favorite.html", {"request": request, "favorites": favorites})

@app.post("/favorite/remove/{id_history}")
async def remove_favorite(id_history: int, request: Request):
    id_user = get_current_user(request)
    if not id_user:
        logger.warning("unauthorized_favorite_remove")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info("remove_favorite_request", user_id=id_user, history_id=id_history)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    try:
        # Достаём сразу prompt_version из History
        cursor.execute("SELECT id_user, id_recipes, prompt_version FROM History WHERE id_history = ?", (id_history,))
        row = cursor.fetchone()
        if not row or row[0] != id_user:
            logger.warning("forbidden_favorite_remove", user_id=id_user, history_id=id_history)
            raise HTTPException(status_code=403, detail="Forbidden")

        id_recipes = row[1]
        prompt_version = row[2] if row[2] else "unknown"

        # Получаем название рецепта
        cursor.execute("SELECT title FROM Recipes WHERE id_recipes = ?", (id_recipes,))
        recipe_row = cursor.fetchone()
        recipe_name = recipe_row[0] if recipe_row else "Неизвестный рецепт"

        # Снимаем отметку избранного
        cursor.execute("UPDATE History SET favorite = 0 WHERE id_history = ?", (id_history,))
    
        # ✅ Логируем удаление из избранного в PromptUsage (в рамках того же соединения)
        cursor.execute(
            "INSERT INTO PromptUsage (id_user, prompt_name, user_action, recipe_name) VALUES (?, ?, ?, ?)",
            (id_user, prompt_version.lower(), "Удален рецепт из избранного", recipe_name)
        )
        con.commit()

        logger.info("prompt_usage_recorded_remove", user_id=id_user, recipe_name=recipe_name)

    except Exception as e:
        logger.error("favorite_remove_failed", user_id=id_user, history_id=id_history, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка при удалении из избранного")
    finally:
        con.close()

    return RedirectResponse(url="/favorite", status_code=303)

# URL целевого сервера
REMOTE_URL = "http://127.0.0.1:8001/test-vlm"
TASK_RESULT_URL = "http://127.0.0.1:8001/task-result/"
COOK_FROM_IMAGE_URL = "http://127.0.0.1:8001/cook-from-image/"

# Путь к базе данных
DB_PATH = "../bd/my_database.db"

import os
from pathlib import Path

# Создаем необходимые директории
Path("./local_recipes").mkdir(exist_ok=True)
Path("./recipes").mkdir(exist_ok=True)

def get_forbidden_products(user_id: int) -> List[str]:
    """
    Получает список запрещенных продуктов для пользователя из базы данных.
    """
    if not user_id:
        return []
    
    try:
        # Проверяем существование файла базы данных
        if not os.path.exists(DB_PATH):
            logger.warning("database_not_found", path=DB_PATH)
            return []
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cursor.execute("""
            SELECT p.title 
            FROM ProductsInProhibited pip 
            JOIN Product p ON pip.id_product = p.id_product
            WHERE pip.id_user = ?
        """, (user_id,))
        
        forbidden_products = [row[0].lower() for row in cursor.fetchall()]
        con.close()
        
        logger.debug("forbidden_products_retrieved", 
                    user_id=user_id, 
                    count=len(forbidden_products),
                    products=forbidden_products)
        
        return forbidden_products
        
    except sqlite3.Error as e:
        logger.error("database_error_getting_forbidden_products", user_id=user_id, error=str(e))
        return []
    except Exception as e:
        logger.error("unexpected_error_getting_forbidden_products", user_id=user_id, error=str(e))
        return []

def filter_ingredients_by_forbidden(ingredients: List[str], forbidden_products: List[str]) -> List[str]:
    """
    Фильтрует ингредиенты, исключая запрещенные продукты.
    """
    if not forbidden_products:
        return ingredients
    
    filtered_ingredients = []
    removed_ingredients = []
    
    for ingredient in ingredients:
        ingredient_lower = ingredient.lower()
        # Проверяем, содержится ли запрещенный продукт в названии ингредиента
        is_forbidden = any(forbidden_product in ingredient_lower for forbidden_product in forbidden_products)
        
        if not is_forbidden:
            filtered_ingredients.append(ingredient)
        else:
            removed_ingredients.append(ingredient)
    
    if removed_ingredients:
        logger.debug("ingredients_filtered", 
                    removed_count=len(removed_ingredients),
                    removed_ingredients=removed_ingredients)
    
    return filtered_ingredients

def get_cooking_times():
    """Получает варианты времени приготовления из базы данных"""
    try:
        if not os.path.exists(DB_PATH):
            logger.warning("database_not_found_cooking_times", path=DB_PATH)
            return []
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        cursor.execute("SELECT id_cooking_time, title FROM CookingTime")
        cooking_times = cursor.fetchall()
        con.close()
        
        logger.debug("cooking_times_retrieved", count=len(cooking_times))
        return cooking_times
        
    except sqlite3.Error as e:
        logger.error("database_error_getting_cooking_times", error=str(e))
        return []
    except Exception as e:
        logger.error("unexpected_error_getting_cooking_times", error=str(e))
        return []

def get_difficulties():
    """Получает варианты сложности из базы данных"""
    try:
        if not os.path.exists(DB_PATH):
            logger.warning("database_not_found_difficulties", path=DB_PATH)
            return []
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        cursor.execute("SELECT id_difficulty, title FROM Difficulty")
        difficulties = cursor.fetchall()
        con.close()
        
        logger.debug("difficulties_retrieved", count=len(difficulties))
        return difficulties
        
    except sqlite3.Error as e:
        logger.error("database_error_getting_difficulties", error=str(e))
        return []
    except Exception as e:
        logger.error("unexpected_error_getting_difficulties", error=str(e))
        return []

def get_calorie_contents():
    """Получает варианты калорийности из базы данных"""
    try:
        if not os.path.exists(DB_PATH):
            logger.warning("database_not_found_calorie_contents", path=DB_PATH)
            return []
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        cursor.execute("SELECT id_calorie_content, title FROM CalorieContent")
        calorie_contents = cursor.fetchall()
        con.close()
        
        logger.debug("calorie_contents_retrieved", count=len(calorie_contents))
        return calorie_contents
        
    except sqlite3.Error as e:
        logger.error("database_error_getting_calorie_contents", error=str(e))
        return []
    except Exception as e:
        logger.error("unexpected_error_getting_calorie_contents", error=str(e))
        return []

def get_recipe_preferences():
    """Получает все предпочтения для рецептов из базы данных"""
    return {
        "cooking_times": get_cooking_times(),
        "difficulties": get_difficulties(),
        "calorie_contents": get_calorie_contents()
    }

def get_user_preferences(user_id):
    """Получает предпочтения конкретного пользователя из базы данных"""
    if not user_id:
        return {}
    
    try:
        if not os.path.exists(DB_PATH):
            logger.warning("database_not_found_user_preferences", path=DB_PATH)
            return {}
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        # Получаем предпочтения пользователя с JOIN к связанным таблицам
        cursor.execute("""
            SELECT 
                u.preferences_time,
                u.preferences_difficulty, 
                u.preferences_calorie,
                ct.title as cooking_time_title,
                d.title as difficulty_title,
                cc.title as calorie_title
            FROM User u
            LEFT JOIN CookingTime ct ON u.preferences_time = ct.id_cooking_time
            LEFT JOIN Difficulty d ON u.preferences_difficulty = d.id_difficulty
            LEFT JOIN CalorieContent cc ON u.preferences_calorie = cc.id_calorie_content
            WHERE u.id_user = ?
        """, (user_id,))
        
        user_data = cursor.fetchone()
        con.close()
        
        if user_data:
            logger.debug("user_preferences_retrieved", user_id=user_id)
            return {
                "preferences_time_id": user_data[0],
                "preferences_difficulty_id": user_data[1],
                "preferences_calorie_id": user_data[2],
                "preferred_cooking_time": user_data[3],  # title из CookingTime
                "preferred_difficulty": user_data[4],    # title из Difficulty
                "preferred_calorie_level": user_data[5]  # title из CalorieContent
            }
        else:
            logger.debug("user_preferences_not_found", user_id=user_id)
            return {}
            
    except sqlite3.Error as e:
        logger.error("database_error_getting_user_preferences", user_id=user_id, error=str(e))
        return {}
    except Exception as e:
        logger.error("unexpected_error_getting_user_preferences", user_id=user_id, error=str(e))
        return {}

def get_all_preferences_with_user(user_id):
    """Получает все предпочтения вместе с настройками пользователя"""
    all_preferences = get_recipe_preferences()
    user_preferences = get_user_preferences(user_id)
    
    return {
        "all_preferences": all_preferences,
        "user_preferences": user_preferences
    }

@app.get("/upload", response_class=HTMLResponse)
async def get_upload_form(request: Request):
    user_id = get_current_user(request)
    logger.info("upload_page_accessed", user_id=user_id)
    
    # Получаем ID пользователя и его предпочтения
    preferences_data = get_all_preferences_with_user(user_id)
    
    # Получаем сообщения об ошибках
    error_message = request.query_params.get("error")
    if not error_message:
        error_message = request.cookies.get("error_message")
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "preferences": preferences_data,
        "error_message": error_message
    })

# Первый запрос - отправка файла и получение task_id
@app.post("/start-processing")
async def start_processing(request: Request, file: UploadFile = File(...)):
    user_id = get_current_user(request)
    logger.info("start_processing_request", 
               user_id=user_id, 
               filename=file.filename,
               content_type=file.content_type)
    
    # Проверка типа файла
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        logger.warning("invalid_file_type_upload", filename=file.filename)
        raise HTTPException(status_code=400, detail="Файл должен быть изображением (jpg/jpeg/png)")
    
    contents = await file.read()
    try:
        async with httpx.AsyncClient() as client:
            files = {'file': (file.filename, contents, file.content_type)}
            response = await client.post(REMOTE_URL, files=files)

        if response.status_code == 200:
            task_data = response.json()
            task_id = task_data.get("task_id")
            status = task_data.get("status", "queued")
            
            if not task_id:
                logger.error("no_task_id_received", response_data=task_data)
                raise HTTPException(status_code=500, detail="Не получен task_id")
            
            logger.info("processing_started_successfully", 
                       user_id=user_id, 
                       task_id=task_id, 
                       status=status)
            
            return {
                "task_id": task_id, 
                "status": status,
                "message": "Задача поставлена в очередь на обработку"
            }
        else:
            error_detail = "Ошибка удаленного сервера"
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", error_detail)
            except:
                pass
            
            logger.error("remote_server_error", 
                        status_code=response.status_code,
                        error_detail=error_detail)
            raise HTTPException(status_code=response.status_code, detail=error_detail)
            
    except Exception as e:
        logger.error("processing_start_failed", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка запроса: {str(e)}")

# Второй запрос - получение результата по task_id
@app.get("/get-result/{task_id}")
async def get_result(request: Request, task_id: str):
    user_id = get_current_user(request)
    logger.info("get_result_request", user_id=user_id, task_id=task_id)
    
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id обязателен")
    
    try:
        async with httpx.AsyncClient() as client:
            url = f"{TASK_RESULT_URL}{task_id}"
            
            result_response = await client.get(url)
            
            if result_response.status_code == 200:
                result_data = result_response.json()
                status = result_data.get("status")
                
                if status == "done":
                    # Обрабатываем новую структуру данных
                    ingredients_data = result_data.get("ingredients", {})
                    
                    # Если ingredients - это объект с ключом "ingredients"
                    if isinstance(ingredients_data, dict) and "ingredients" in ingredients_data:
                        ingredients_list = ingredients_data["ingredients"]
                        ingredients = [ingredient.get("name", "") for ingredient in ingredients_list if ingredient.get("name")]
                    # Если ingredients - это простой массив строк (старая структура)
                    elif isinstance(ingredients_data, list):
                        ingredients = ingredients_data
                    else:
                        ingredients = []
                    
                    # Получаем запрещенные продукты пользователя и фильтруем ингредиенты
                    forbidden_products = get_forbidden_products(user_id)
                    
                    if forbidden_products:
                        original_count = len(ingredients)
                        ingredients = filter_ingredients_by_forbidden(ingredients, forbidden_products)
                        filtered_count = len(ingredients)
                        
                        if filtered_count < original_count:
                            logger.info("ingredients_filtered", 
                                       task_id=task_id,
                                       original_count=original_count,
                                       filtered_count=filtered_count,
                                       removed_products=forbidden_products)
                    
                    logger.info("result_retrieved_successfully", 
                               task_id=task_id,
                               ingredients_count=len(ingredients))
                    
                    return {
                        "status": "done", 
                        "ingredients": ingredients,
                        "raw_ingredients": ingredients_data,
                        "forbidden_products_removed": forbidden_products if forbidden_products else [],
                        "task_id": task_id
                    }
                    
                elif status == "processing":
                    logger.debug("task_still_processing", task_id=task_id)
                    return {
                        "status": "processing",
                        "task_id": task_id,
                        "message": "Задача все еще обрабатывается"
                    }
                    
                elif status == "error":
                    error_msg = result_data.get("error", "Неизвестная ошибка")
                    logger.error("task_processing_error", task_id=task_id, error=error_msg)
                    return {
                        "status": "error",
                        "task_id": task_id,
                        "error": error_msg
                    }
                    
                else:
                    logger.warning("unknown_task_status", task_id=task_id, status=status)
                    return {
                        "status": status,
                        "task_id": task_id,
                        "data": result_data
                    }
                    
            else:
                error_detail = "Ошибка при получении результата задачи"
                try:
                    error_data = result_response.json()
                    error_detail = error_data.get("detail", error_detail)
                except:
                    pass
                    
                logger.error("result_retrieval_failed", 
                            task_id=task_id,
                            status_code=result_response.status_code,
                            error_detail=error_detail)
                    
                raise HTTPException(
                    status_code=result_response.status_code, 
                    detail=error_detail
                )
                
    except Exception as e:
        logger.error("get_result_failed", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка запроса: {str(e)}")

# Третий запрос - генерация рецептов с расширенными параметрами
@app.post("/generate-recipes/{task_id}")
async def generate_recipes(
    request: Request,
    task_id: str,
    dietary: str = Form("нет"),
    user_feedback: str = Form("нет"),
    preferred_calorie_level: str = Form("нет"),
    preferred_cooking_time: str = Form("нет"),
    preferred_difficulty: str = Form("нет"),
    existing_recipes: str = Form("нет")
):
    user_id = get_current_user(request)
    logger.info("generate_recipes_request", 
               user_id=user_id,
               task_id=task_id,
               dietary=dietary,
               user_feedback_length=len(user_feedback),
               preferred_calorie_level=preferred_calorie_level,
               preferred_cooking_time=preferred_cooking_time,
               preferred_difficulty=preferred_difficulty)
    
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id обязателен")
    
    # Получаем запрещенные продукты пользователя
    forbidden_products = get_forbidden_products(user_id)
    
    if forbidden_products:
        logger.info("considering_forbidden_products", 
                   user_id=user_id,
                   forbidden_products_count=len(forbidden_products))
        # Добавляем запрещенные продукты в feedback для учета при генерации
        if user_feedback and user_feedback != "нет":
            user_feedback += f". Исключить: {', '.join(forbidden_products)}"
        else:
            user_feedback = f"Исключить: {', '.join(forbidden_products)}"
    
    max_retries = 5
    base_retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "dietary": dietary,
                    "user_feedback": user_feedback,
                    "preferred_calorie_level": preferred_calorie_level,
                    "preferred_cooking_time": preferred_cooking_time,
                    "preferred_difficulty": preferred_difficulty,
                    "existing_recipes": existing_recipes
                }
                
                logger.debug("generate_recipes_attempt", 
                           attempt=attempt + 1,
                           max_attempts=max_retries,
                           data=data)
                
                response = await client.post(
                    f"{COOK_FROM_IMAGE_URL}{task_id}",
                    data=data,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    result_data = response.json()
                    logger.info("recipes_generated_successfully", 
                               task_id=task_id,
                               recipes_count=len(result_data.get("recipes", [])))
                    
                    # Обрабатываем ингредиенты из ответа
                    ingredients_data = result_data.get("ingredients", {})
                    
                    if isinstance(ingredients_data, dict) and "ingredients" in ingredients_data:
                        ingredients_list = ingredients_data["ingredients"]
                        ingredients = [ingredient.get("name", "") for ingredient in ingredients_list if ingredient.get("name")]
                    elif isinstance(ingredients_data, list):
                        ingredients = ingredients_data
                    else:
                        ingredients = []
                    
                    # Сохраняем рецепты локально для последующего использования
                    local_recipes_path = Path(f"./local_recipes/{task_id}_recipes.json")
                    local_recipes_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(local_recipes_path, "w", encoding="utf-8") as f:
                        json.dump(result_data, f, ensure_ascii=False, indent=2)
                    
                    logger.info("recipes_saved_locally", 
                               task_id=task_id,
                               save_path=str(local_recipes_path))
                    
                    return {
                        "ingredients": ingredients,
                        "raw_ingredients": ingredients_data,
                        "recipes": result_data.get("recipes", []),
                        "feedback_used": result_data.get("feedback_used", ""),
                        "preferred_calorie_level": result_data.get("preferred_calorie_level", ""),
                        "preferred_cooking_time": result_data.get("preferred_cooking_time", ""),
                        "preferred_difficulty": result_data.get("preferred_difficulty", ""),
                        "excluded_recipes": result_data.get("excluded_recipes", ""),
                        "saved_to": str(local_recipes_path),
                        "forbidden_products_considered": forbidden_products if forbidden_products else [],
                        "task_id": task_id
                    }
                    
                elif response.status_code == 429:
                    wait_time = base_retry_delay * (2 ** attempt)
                    logger.warning("rate_limit_exceeded", 
                                 attempt=attempt + 1,
                                 wait_time=wait_time)
                    
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        error_msg = "Превышен лимит запросов к AI-сервису. Пожалуйста, подождите несколько минут."
                        logger.error("rate_limit_final_failure", task_id=task_id)
                        raise HTTPException(status_code=429, detail=error_msg)
                        
                else:
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", f"HTTP {response.status_code}")
                    except:
                        error_detail = f"HTTP {response.status_code}"
                    
                    logger.error("recipe_generation_failed", 
                               task_id=task_id,
                               status_code=response.status_code,
                               error_detail=error_detail)
                    
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=f"Ошибка при генерации рецептов: {error_detail}"
                    )
                    
        except httpx.TimeoutException as e:
            logger.warning("generate_recipes_timeout", 
                         attempt=attempt + 1,
                         task_id=task_id)
            if attempt < max_retries - 1:
                wait_time = base_retry_delay * (attempt + 1)
                await asyncio.sleep(wait_time)
                continue
            raise HTTPException(status_code=504, detail="Таймаут при подключении к серверу")
            
        except Exception as e:
            logger.error("generate_recipes_attempt_failed", 
                       attempt=attempt + 1,
                       task_id=task_id,
                       error=str(e))
            if attempt < max_retries - 1:
                wait_time = base_retry_delay * (attempt + 1)
                await asyncio.sleep(wait_time)
                continue
            raise HTTPException(status_code=500, detail=f"Ошибка запроса: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Не удалось выполнить запрос после нескольких попыток")


# Дополнительный endpoint для получения информации о запрещенных продуктах
@app.get("/user/forbidden-products")
async def get_user_forbidden_products(request: Request):
    """
    Возвращает список запрещенных продуктов для текущего пользователя.
    """
    user_id = get_current_user(request)
    if not user_id:
        logger.warning("unauthorized_forbidden_products_request")
        return {"error": "Пользователь не авторизован"}
    
    forbidden_products = get_forbidden_products(user_id)
    
    logger.info("forbidden_products_retrieved_api", 
               user_id=user_id,
               count=len(forbidden_products))
    
    return {
        "user_id": user_id,
        "forbidden_products": forbidden_products,
        "count": len(forbidden_products)
    }

# API endpoint для получения предпочтений
@app.get("/api/preferences")
async def get_preferences_api(request: Request):
    """Возвращает предпочтения в JSON формате с учетом пользователя"""
    user_id = get_current_user(request)
    logger.info("preferences_api_request", user_id=user_id)
    
    preferences_data = get_all_preferences_with_user(user_id)
    
    # Преобразуем в удобный формат
    formatted_preferences = {
        "all_preferences": {
            "cooking_times": [{"id": row[0], "title": row[1]} for row in preferences_data["all_preferences"]["cooking_times"]],
            "difficulties": [{"id": row[0], "title": row[1]} for row in preferences_data["all_preferences"]["difficulties"]],
            "calorie_contents": [{"id": row[0], "title": row[1]} for row in preferences_data["all_preferences"]["calorie_contents"]]
        },
        "user_preferences": preferences_data["user_preferences"],
        "user_id": user_id
    }
    
    return formatted_preferences
'''
@app.post("/complete-recipe/{task_id}")
async def complete_recipe(task_id: str, request: Request):
    """
    Сохраняет завершенные рецепты в историю пользователя
    и логирует действия в PromptUsage
    """
    user_id = get_current_user(request)
    logger.info("complete_recipe_request", user_id=user_id, task_id=task_id)

    try:
        form = await request.form()

        if not user_id:
            logger.warning("unauthorized_complete_recipe_attempt", task_id=task_id)
            return JSONResponse(
                status_code=401,
                content={"success": False, "detail": "Пользователь не авторизован"}
            )

        # Загружаем данные о рецептах
        local_recipes_path = Path(f"./local_recipes/{task_id}_recipes.json")
        if not local_recipes_path.exists():
            logger.error("recipes_file_not_found", task_id=task_id, path=str(local_recipes_path))
            return JSONResponse(
                status_code=404,
                content={"success": False, "detail": f"Файл с рецептами не найден"}
            )

        with open(local_recipes_path, "r", encoding="utf-8") as f:
            recipes_data = json.load(f)

        recipes = recipes_data.get("recipes", [])
        prompt_version = recipes_data.get("prompt_version", "unknown")

        completed_recipe_indexes = set()
        saved_recipes = []

        # Определяем, какие рецепты пользователь выполнил
        for i, recipe in enumerate(recipes):
            steps_count = len(recipe.get("steps", []))
            if steps_count == 0:
                continue

            selected_steps = form.getlist(f"completed_steps_{i}")

            if len(selected_steps) == steps_count:
                completed_recipe_indexes.add(i)
                recipe_name = recipe.get("name", f"Рецепт {i+1}")
                saved_recipes.append(recipe_name)

                # ✅ Логируем приготовление каждого рецепта
                try:
                    log_user_action(
                        user_id,
                        prompt_version.lower(),
                        "Приготовил рецепт",
                        recipe_name
                    )
                    logger.info("prompt_usage_recorded", user_id=user_id, recipe_name=recipe_name)
                except Exception as e:
                    logger.error("prompt_usage_insert_failed", user_id=user_id, recipe_name=recipe_name, error=str(e))

        # Сохраняем в таблицу History
        if completed_recipe_indexes:
            con = sqlite3.connect(DB_PATH)
            cursor = con.cursor()

            for i in completed_recipe_indexes:
                recipe = recipes[i]
                recipe_name = recipe.get("name", f"Рецепт {i+1}")

                cursor.execute("SELECT id_recipes FROM Recipes WHERE title=?", (recipe_name,))
                row = cursor.fetchone()

                if row:
                    id_recipes = row[0]
                else:
                    steps_text = "\n".join([step.get("instruction", "") for step in recipe.get("steps", [])])
                    cooking_time = recipe.get("cooking_time", "")
                    difficulty = recipe.get("difficulty", "")
                    calorie_level = recipe.get("calorie_level", "")

                    cursor.execute(
                        "INSERT INTO Recipes (title, description, cooking_time, difficulty, calorie_level) VALUES (?, ?, ?, ?, ?)",
                        (recipe_name, steps_text, cooking_time, difficulty, calorie_level)
                    )
                    id_recipes = cursor.lastrowid

                cursor.execute(
                    "SELECT id_history FROM History WHERE id_user=? AND id_recipes=?",
                    (user_id, id_recipes)
                )
                existing_record = cursor.fetchone()

                if not existing_record:
                    cursor.execute(
                        "INSERT INTO History (id_user, id_recipes, favorite, done, prompt_version) VALUES (?, ?, ?, ?, ?)",
                        (user_id, id_recipes, 0, 1, prompt_version)
                    )


            con.commit()
            con.close()

            # ✅ Логируем общее действие: сохранение всех рецептов
            try:
                log_user_action(
                    user_id,
                    prompt_version.lower(),
                    "Сохранение завершенных рецептов",
                    ", ".join(saved_recipes)
                )
                logger.info("prompt_usage_recorded_all", user_id=user_id, saved_recipes=saved_recipes)
            except Exception as e:
                logger.error("prompt_usage_insert_failed_all", user_id=user_id, error=str(e))

        logger.info("recipes_saved_to_history",
                   user_id=user_id,
                   task_id=task_id,
                   saved_count=len(saved_recipes),
                   saved_recipes=saved_recipes)

        return {
            "success": True,
            "message": f"Успешно сохранено {len(saved_recipes)} рецептов в историю",
            "saved_recipes": saved_recipes,
            "task_id": task_id,
            "saved_count": len(saved_recipes)
        }

    except Exception as e:
        logger.error("complete_recipe_failed",
                    user_id=user_id,
                    task_id=task_id,
                    error=str(e))

        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Ошибка при сохранении рецептов: {str(e)}"}
        )
'''
@app.post("/complete-recipe/{task_id}")
async def complete_recipe(task_id: str, request: Request):
    """
    Сохраняет завершенные рецепты в историю пользователя
    и логирует действия в PromptUsage
    """
    user_id = get_current_user(request)
    logger.info("complete_recipe_request", user_id=user_id, task_id=task_id)

    try:
        form = await request.form()

        if not user_id:
            logger.warning("unauthorized_complete_recipe_attempt", task_id=task_id)
            return JSONResponse(
                status_code=401,
                content={"success": False, "detail": "Пользователь не авторизован"}
            )

        # Загружаем данные о рецептах
        local_recipes_path = Path(f"./local_recipes/{task_id}_recipes.json")
        if not local_recipes_path.exists():
            logger.error("recipes_file_not_found", task_id=task_id, path=str(local_recipes_path))
            return JSONResponse(
                status_code=404,
                content={"success": False, "detail": f"Файл с рецептами не найден"}
            )

        with open(local_recipes_path, "r", encoding="utf-8") as f:
            recipes_data = json.load(f)

        recipes = recipes_data.get("recipes", [])
        prompt_version = recipes_data.get("prompt_version", "unknown")

        completed_recipe_indexes = set()
        saved_recipes = []

        # Определяем, какие рецепты пользователь выполнил
        for i, recipe in enumerate(recipes):
            steps_count = len(recipe.get("steps", []))
            if steps_count == 0:
                continue

            selected_steps = form.getlist(f"completed_steps_{i}")

            if len(selected_steps) == steps_count:
                completed_recipe_indexes.add(i)
                recipe_name = recipe.get("name", f"Рецепт {i+1}")
                saved_recipes.append(recipe_name)

                # ✅ Логируем приготовление каждого рецепта
                try:
                    log_user_action(
                        user_id,
                        prompt_version.lower(),
                        "Приготовил рецепт",
                        recipe_name
                    )
                    logger.info("prompt_usage_recorded", user_id=user_id, recipe_name=recipe_name)
                except Exception as e:
                    logger.error("prompt_usage_insert_failed", user_id=user_id, recipe_name=recipe_name, error=str(e))

        # Сохраняем в таблицу History
        if completed_recipe_indexes:
            con = sqlite3.connect(DB_PATH)
            cursor = con.cursor()
            
            # Получаем текущую дату в формате YYYY-MM-DD
            current_date = datetime.now().strftime("%Y-%m-%d")
            logger.info("current_date_for_saving", date=current_date)

            for i in completed_recipe_indexes:
                recipe = recipes[i]
                recipe_name = recipe.get("name", f"Рецепт {i+1}")

                cursor.execute("SELECT id_recipes FROM Recipes WHERE title=?", (recipe_name,))
                row = cursor.fetchone()

                if row:
                    id_recipes = row[0]
                else:
                    steps_text = "\n".join([step.get("instruction", "") for step in recipe.get("steps", [])])
                    cooking_time = recipe.get("cooking_time", "")
                    difficulty = recipe.get("difficulty", "")
                    calorie_level = recipe.get("calorie_level", "")

                    cursor.execute(
                        "INSERT INTO Recipes (title, description, cooking_time, difficulty, calorie_level) VALUES (?, ?, ?, ?, ?)",
                        (recipe_name, steps_text, cooking_time, difficulty, calorie_level)
                    )
                    id_recipes = cursor.lastrowid

                cursor.execute(
                    "SELECT id_history FROM History WHERE id_user=? AND id_recipes=?",
                    (user_id, id_recipes)
                )
                existing_record = cursor.fetchone()

                if not existing_record:
                    # ВАРИАНТ 1: Использование SQLite функции date()
                    cursor.execute(
                        """
                        INSERT INTO History 
                        (id_user, id_recipes, favorite, done, prompt_version, date_added) 
                        VALUES (?, ?, ?, ?, ?, date('now'))
                        """,
                        (user_id, id_recipes, 0, 1, prompt_version)
                    )
                    
                    # ВАРИАНТ 2: Использование Python даты (раскомментировать если нужно)
                    # cursor.execute(
                    #     """
                    #     INSERT INTO History 
                    #     (id_user, id_recipes, favorite, done, prompt_version, date_added) 
                    #     VALUES (?, ?, ?, ?, ?, ?)
                    #     """,
                    #     (user_id, id_recipes, 0, 1, prompt_version, current_date)
                    # )
                    
                    logger.info("recipe_saved_with_date", 
                               user_id=user_id, 
                               recipe_id=id_recipes, 
                               recipe_name=recipe_name,
                               date=current_date)
                else:
                    # Если запись уже существует, обновляем дату
                    cursor.execute(
                        """
                        UPDATE History 
                        SET date_added = date('now'), done = 1
                        WHERE id_user = ? AND id_recipes = ?
                        """,
                        (user_id, id_recipes)
                    )
                    logger.info("recipe_date_updated", 
                               user_id=user_id, 
                               recipe_id=id_recipes,
                               date=current_date)

            con.commit()
            con.close()

            # ✅ Логируем общее действие: сохранение всех рецептов
            try:
                log_user_action(
                    user_id,
                    prompt_version.lower(),
                    "Сохранение завершенных рецептов",
                    ", ".join(saved_recipes)
                )
                logger.info("prompt_usage_recorded_all", 
                           user_id=user_id, 
                           saved_recipes=saved_recipes,
                           saved_count=len(saved_recipes))
            except Exception as e:
                logger.error("prompt_usage_insert_failed_all", user_id=user_id, error=str(e))

        logger.info("recipes_saved_to_history",
                   user_id=user_id,
                   task_id=task_id,
                   saved_count=len(saved_recipes),
                   saved_recipes=saved_recipes,
                   date=current_date if 'current_date' in locals() else "N/A")
        '''
        return {
            "success": True,
            "message": f"Успешно сохранено {len(saved_recipes)} рецептов в историю",
            "saved_recipes": saved_recipes,
            "task_id": task_id,
            "saved_count": len(saved_recipes),
            "date_added": current_date if 'current_date' in locals() else None
        }

    except sqlite3.Error as e:
        logger.error("database_error_complete_recipe",
                    user_id=user_id,
                    task_id=task_id,
                    error=str(e))
        
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Ошибка базы данных: {str(e)}"}
        )
        
    except Exception as e:
        logger.error("complete_recipe_failed",
                    user_id=user_id,
                    task_id=task_id,
                    error=str(e))

        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Ошибка при сохранении рецептов: {str(e)}"}
        )

    '''
        # ВАЖНОЕ ИЗМЕНЕНИЕ: Вместо возврата JSON делаем редирект
        return RedirectResponse(
            url="/history",  # Перенаправляем на страницу истории
            status_code=303,  # 303 See Other - для POST -> GET редиректа
            headers={"X-Saved-Count": str(len(saved_recipes))}  # Можно передать данные в заголовках
        )

    except sqlite3.Error as e:
        logger.error("database_error_complete_recipe",
                    user_id=user_id,
                    task_id=task_id,
                    error=str(e))
        
        return RedirectResponse(
            url=f"/upload?error=Ошибка базы данных: {str(e)[:100]}&task_id={task_id}",
            status_code=303
        )
        
    except Exception as e:
        logger.error("complete_recipe_failed",
                    user_id=user_id,
                    task_id=task_id,
                    error=str(e))

        return RedirectResponse(
            url=f"/upload?error=Ошибка при сохранении: {str(e)[:100]}&task_id={task_id}",
            status_code=303
        )
# Тестовый endpoint для генерации рецептов (заглушка)
@app.post("/generate-test-recipes/{task_id}")
async def generate_test_recipes(
    request: Request,
    task_id: str,
    dietary: str = Form("нет"),
    user_feedback: str = Form("нет"),
    preferred_calorie_level: str = Form("нет"),
    preferred_cooking_time: str = Form("нет"),
    preferred_difficulty: str = Form("нет"),
    existing_recipes: str = Form("нет")
):
    """
    Тестовый endpoint для демонстрации функционала без вызова внешнего API
    """
    user_id = get_current_user(request)
    logger.info("test_recipes_generation", 
               user_id=user_id,
               task_id=task_id,
               dietary=dietary,
               user_feedback=user_feedback)
    
    # Получаем запрещенные продукты пользователя
    forbidden_products = get_forbidden_products(user_id)
    
    # Тестовые данные рецептов
    test_recipes = [
        {
            "name": "Курица с брокколи в соусе терияки",
            "ingredients": [
                {"name": "куриная грудка", "amount": "300 г"},
                {"name": "брокколи", "amount": "200 г"},
                {"name": "соус терияки", "amount": "3 ст. ложки"},
                {"name": "чеснок", "amount": "2 зубчика"},
                {"name": "имбирь", "amount": "1 ч. ложка"},
                {"name": "растительное масло", "amount": "2 ст. ложки"}
            ],
            "steps": [
                {"order": 1, "instruction": "Куриную грудку нарезать кубиками. (5 минут)"},
                {"order": 2, "instruction": "Брокколи разобрать на соцветия. (3 минуты)"},
                {"order": 3, "instruction": "Разогреть сковороду с маслом, обжарить курицу до золотистой корочки. (10 минут)"},
                {"order": 4, "instruction": "Добавить чеснок и имбирь, обжарить 1 минуту. (1 минута)"},
                {"order": 5, "instruction": "Добавить брокколи и соус терияки, тушить 7-10 минут. (10 минут)"}
            ],
            "cooking_time": "29 минут",
            "difficulty": "легко",
            "calorie_content": {
                "kcal": 250,
                "protein_g": 28,
                "fat_g": 10,
                "carb_g": 12
            },
            "calorie_level": "среднекалорийное"
        }
    ]

    # Фильтруем рецепты если есть запрещенные продукты
    filtered_recipes = test_recipes
    if forbidden_products:
        logger.info("filtering_test_recipes", 
                   forbidden_products=forbidden_products)
        filtered_recipes = []
        for recipe in test_recipes:
            # Проверяем, нет ли запрещенных продуктов в ингредиентах
            has_forbidden = any(
                any(forbidden in ing["name"].lower() for forbidden in forbidden_products)
                for ing in recipe["ingredients"]
            )
            if not has_forbidden:
                filtered_recipes.append(recipe)
            else:
                logger.debug("test_recipe_filtered_out", 
                           recipe_name=recipe['name'],
                           reason="contains_forbidden_products")

    # Сохраняем рецепты локально
    local_recipes_path = Path(f"./local_recipes/{task_id}_recipes.json")
    local_recipes_path.parent.mkdir(parents=True, exist_ok=True)
    
    save_data = {
        "ingredients": {"ingredients": [{"name": "брокколи"}, {"name": "курица"}, {"name": "сыр"}]},
        "recipes": filtered_recipes,
        "feedback_used": user_feedback if user_feedback != "нет" else "",
        "preferred_calorie_level": preferred_calorie_level,
        "preferred_cooking_time": preferred_cooking_time,
        "preferred_difficulty": preferred_difficulty,
        "excluded_recipes": existing_recipes
    }
    
    with open(local_recipes_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    logger.info("test_recipes_saved", 
               task_id=task_id,
               recipes_count=len(filtered_recipes),
               save_path=str(local_recipes_path))
    
    return {
        "ingredients": ["брокколи", "курица", "сыр"],
        "raw_ingredients": {"ingredients": [{"name": "брокколи"}, {"name": "курица"}, {"name": "сыр"}]},
        "recipes": filtered_recipes,
        "feedback_used": user_feedback if user_feedback != "нет" else "",
        "preferred_calorie_level": preferred_calorie_level,
        "preferred_cooking_time": preferred_cooking_time,
        "preferred_difficulty": preferred_difficulty,
        "excluded_recipes": existing_recipes,
        "saved_to": str(local_recipes_path),
        "forbidden_products_considered": forbidden_products if forbidden_products else [],
        "task_id": task_id
    }

# GET endpoint для отображения страницы с сохраненными рецептами
@app.get("/saved-recipes/{task_id}")
async def show_saved_recipes(request: Request, task_id: str):
    """
    Отображает страницу с информацией о сохраненных рецептах
    """
    user_id = get_current_user(request)
    logger.info("saved_recipes_page_accessed", user_id=user_id, task_id=task_id)
    
    try:
        if not user_id:
            # Если пользователь не авторизован, перенаправляем на страницу авторизации
            logger.warning("unauthorized_saved_recipes_access", task_id=task_id)
            return RedirectResponse(url="/", status_code=303)

        # Получаем данные о сохраненных рецептах из базы данных
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()

        # Ищем рецепты, сохраненные для этой задачи
        cursor.execute("""
            SELECT r.title 
            FROM History h
            JOIN Recipes r ON h.id_recipes = r.id_recipes
            WHERE h.id_user = ? AND h.done = 1
            ORDER BY h.id_history DESC
            LIMIT 10
        """, (user_id,))
        
        saved_recipes = [row[0] for row in cursor.fetchall()]
        con.close()

        # Если у нас есть task_id, можем попробовать получить более точные данные
        # из локального файла с рецептами
        specific_saved_recipes = []
        local_recipes_path = Path(f"./local_recipes/{task_id}_recipes.json")
        
        if local_recipes_path.exists():
            with open(local_recipes_path, "r", encoding="utf-8") as f:
                recipes_data = json.load(f)
            
            # Получаем названия рецептов из файла
            all_recipes = recipes_data.get("recipes", [])
            recipe_names = [recipe.get("name", f"Рецепт {i+1}") for i, recipe in enumerate(all_recipes)]
            
            # Фильтруем сохраненные рецепты по названиям из файла
            specific_saved_recipes = [name for name in recipe_names if name in saved_recipes]

        # Используем специфичные рецепты если есть, иначе все сохраненные
        display_recipes = specific_saved_recipes if specific_saved_recipes else saved_recipes

        logger.info("saved_recipes_displayed", 
                   user_id=user_id,
                   task_id=task_id,
                   display_count=len(display_recipes))

        return templates.TemplateResponse("saved_recipes.html", {
            "request": request,
            "saved_recipes": display_recipes,
            "saved_count": len(display_recipes),
            "task_id": task_id,
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M")
        })

    except Exception as e:
        logger.error("saved_recipes_display_failed", 
                    user_id=user_id,
                    task_id=task_id,
                    error=str(e))
        # В случае ошибки перенаправляем на страницу истории
        return RedirectResponse(url="/history", status_code=303)

# Альтернативный endpoint для отображения без task_id
@app.get("/saved-recipes")
async def show_all_saved_recipes(request: Request):
    """
    Отображает все сохраненные рецепты пользователя
    """
    user_id = get_current_user(request)
    logger.info("all_saved_recipes_page_accessed", user_id=user_id)
    
    try:
        if not user_id:
            logger.warning("unauthorized_all_saved_recipes_access")
            return RedirectResponse(url="/", status_code=303)

        # Получаем все сохраненные рецепты пользователя
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()

        cursor.execute("""
            SELECT r.title, h.id_history
            FROM History h
            JOIN Recipes r ON h.id_recipes = r.id_recipes
            WHERE h.id_user = ? AND h.done = 1
            ORDER BY h.id_history DESC
            LIMIT 20  # Ограничиваем количество для отображения
        """, (user_id,))
        
        saved_recipes = [row[0] for row in cursor.fetchall()]
        con.close()

        logger.info("all_saved_recipes_displayed", 
                   user_id=user_id,
                   recipes_count=len(saved_recipes))

        return templates.TemplateResponse("saved_recipes.html", {
            "request": request,
            "saved_recipes": saved_recipes,
            "saved_count": len(saved_recipes),
            "task_id": None,
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M")
        })

    except Exception as e:
        logger.error("all_saved_recipes_display_failed", user_id=user_id, error=str(e))
        return RedirectResponse(url="/history", status_code=303)

# Обработчик необработанных исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        method=request.method,
        url=str(request.url),
        error_type=type(exc).__name__,
        error=str(exc),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера"}
    )

# Логирование завершения инициализации приложения
logger.info("FastAPI application started successfully")