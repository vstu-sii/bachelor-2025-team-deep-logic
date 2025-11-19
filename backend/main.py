import asyncio
import json
from typing import List
from fastapi import FastAPI, File, HTTPException, Body, status, Request, Form,UploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import httpx


from pydantic import BaseModel

import sqlite3;

from itsdangerous import URLSafeTimedSerializer
import os

from fastapi.middleware.cors import CORSMiddleware



# Секретный ключ (в реальном проекте храните в переменных окружения!)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
serializer = URLSafeTimedSerializer(SECRET_KEY)

app = FastAPI()

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

# авторизация
# авторизация
@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request, error: str = None):
    return templates.TemplateResponse("auth.html", {"request": request, "error": error})

@app.post("/auth")
async def handle_form(request: Request, email: str = Form(...), password: str = Form(...)):
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    # Ищем пользователя по email
    cursor.execute("SELECT id_user, password FROM User WHERE email = ?", (email,))
    result = cursor.fetchone()
    
    con.close()

    if result is None:
        # Пользователь не найден
        return templates.TemplateResponse("auth.html", {
            "request": request,
            "error": "Пользователь с таким email не найден",
            "email": email  # Сохраняем введенный email для удобства
        })
    
    if result[1] != password:
        # Неверный пароль
        return templates.TemplateResponse("auth.html", {
            "request": request,
            "error": "Неверный пароль",
            "email": email  # Сохраняем введенный email для удобства
        })

    # Успешная авторизация
    print(f"Успешная авторизация для пользователя {result[0]}")
    
    # Создаём подписанную cookie с user_id
    session_data = serializer.dumps(result[0])

    response = RedirectResponse(url="/result", status_code=303)
    response.set_cookie(key="session", value=session_data, httponly=True, max_age=3600)  # 1 час
    return response


# Регистрация
@app.get("/registration", response_class=HTMLResponse)
async def get_form(request: Request):
    return templates.TemplateResponse("reg.html", {"request": request})


@app.post("/reg")
async def handle_form(name: str = Form(...), email: str = Form(...),password: str = Form(...)):
    data = (email, name, password)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    # добавляем строку в таблицу User
    cursor.execute("INSERT INTO User (email, login, password) VALUES (?, ?, ?)", data)
    # выполняем транзакцию
    con.commit() 
    cursor.execute("select id_user, password from User where email = (?)", (email,))
    result = cursor.fetchone()
    con.close()

    # Автоматическая авторизация после регистрации
    session_data = serializer.dumps(result[0])
    response = RedirectResponse(url="/result", status_code=303)
    response.set_cookie(key="session", value=session_data, httponly=True, max_age=3600)
    return response


def get_current_user(request: Request):
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        return None
    try:
        id_user = serializer.loads(session_cookie, max_age=3600)
        return id_user
    except Exception:
        return None

#Главная страница
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
    return templates.TemplateResponse("main.html", {"request": request})

@app.post("/test-vlm", response_class=RedirectResponse)
async def test_vlm(file: UploadFile):
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением (jpg/png)")

    save_path = Path(f"./public/uploads/{file.filename}")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    # Перенаправляем на страницу с результатами, передаём имя файла
    return RedirectResponse(url=f"/results/{file.filename}", status_code=status.HTTP_303_SEE_OTHER)


# Профиль
@app.get("/profile", response_class=HTMLResponse)
async def get_form(request: Request):
    id_user = get_current_user(request)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    
    # Данные пользователя
    cursor.execute("SELECT email, login, preferences_time, preferences_difficulty, preferences_calorie FROM User WHERE id_user = ?", (id_user,))
    user_data = cursor.fetchone()
    email, login, preferences_time, preferences_difficulty, preferences_calorie = user_data

    # Получаем все опции для селекторов
    cursor.execute("SELECT id_cooking_time, title FROM CookingTime")
    cooking_times = cursor.fetchall()

    cursor.execute("SELECT id_difficulty, title FROM Difficulty")
    difficulties = cursor.fetchall()

    cursor.execute("SELECT id_calorie_content, title FROM CalorieContent")
    calorie_contents = cursor.fetchall()

    # Получение запрещённых продуктов (ДОБАВЛЕНО В GET ЗАПРОС)
    cursor.execute("""
        SELECT p.title 
        FROM ProductsInProhibited pip 
        JOIN Product p ON pip.id_product = p.id_product
        WHERE pip.id_user = ?
    """, (id_user,))
    forbidden_products = [row[0] for row in cursor.fetchall()]
    
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
        "forbidden_products": forbidden_products  # ДОБАВЛЕНО ЭТО
    })

# Добавление запрещённого продукта
@app.post("/profile/forbidden")
async def add_forbidden_product(request: Request, product_title: str = Form(...)):
    id_user = get_current_user(request)
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

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

    # ПОСЛЕ ДОБАВЛЕНИЯ ПРОДУКТА ПЕРЕЗАГРУЖАЕМ СТРАНИЦУ
    return RedirectResponse(url="/profile", status_code=303)

# Удаление запрещённого продукта (ДОБАВЛЕНО)
@app.post("/profile/forbidden/remove")
async def remove_forbidden_product(request: Request, product_title: str = Form(...)):
    id_user = get_current_user(request)
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    # Находим id продукта
    cursor.execute("SELECT id_product FROM Product WHERE title = ?", (product_title,))
    row = cursor.fetchone()
    
    if row:
        id_product = row[0]
        # Удаляем из запрещённых
        cursor.execute("DELETE FROM ProductsInProhibited WHERE id_user = ? AND id_product = ?", (id_user, id_product))
        con.commit()

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
    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    cursor.execute("""
        UPDATE User SET preferences_time = ?, preferences_difficulty = ?, preferences_calorie = ?
        WHERE id_user = ?
    """, (preferences_time, preferences_difficulty, preferences_calorie, id_user))
    con.commit()

    # После сохранения предпочтений тоже перезагружаем страницу
    return RedirectResponse(url="/profile", status_code=303)

#результат
@app.get("/results/{filename}", response_class=HTMLResponse)
async def results(request: Request, filename: str):
    filename = filename.lower()

    # Получаем оригинальные продукты и рецепты
    original_products = products_by_file.get(filename, ["Нет данных для этого файла"])
    original_recipes = recipes_by_file.get(filename, [])

    # Получаем ID пользователя и его запрещенные продукты
    id_user = get_current_user(request)
    forbidden_products = []
    
    if id_user:
        con = sqlite3.connect("../bd/my_database.db")
        cursor = con.cursor()
        cursor.execute("""
            SELECT p.title 
            FROM ProductsInProhibited pip 
            JOIN Product p ON pip.id_product = p.id_product
            WHERE pip.id_user = ?
        """, (id_user,))
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
    if forbidden_products and id_user:
        for recipe in original_recipes:
            # Проверяем, содержит ли рецепт запрещенные продукты в названии или шагах
            recipe_text = (recipe.get("title", "") + " " + recipe.get("steps", "")).lower()
            contains_forbidden = any(forbidden in recipe_text for forbidden in forbidden_products)
            
            if not contains_forbidden:
                filtered_recipes.append(recipe)
    else:
        # Если нет запрещенных продуктов или пользователь не авторизован, показываем все рецепты
        filtered_recipes = original_recipes

    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "filename": filename,
        "products": filtered_products,
        "recipes": filtered_recipes,
        "removed_products": removed_products,
        "has_removed_products": len(removed_products) > 0
    })
'''
@app.post("/complete-recipe/{filename}")
async def complete_recipe(filename: str, request: Request):
    form = await request.form()
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Получаем отфильтрованные рецепты для данного файла (уже без запрещенных)
    recipes = recipes_by_file.get(filename.lower(), [])
    
    # Но нам нужно получить оригинальные рецепты для проверки выполнения
    # или использовать те же, что отображались пользователю
    completed_recipe_indexes = set()

    # Определяем, какие рецепты пользователь выполнил, проверяя все steps
    for i, recipe in enumerate(recipes):
        steps_count = len(recipe["steps"].split("\n"))
        selected_steps = form.getlist(f"completed_steps_{i}")
        if len(selected_steps) == steps_count:
            completed_recipe_indexes.add(i)

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    for i in completed_recipe_indexes:
        recipe = recipes[i]
        # Проверяем есть ли рецепт в таблице Recipes
        cursor.execute("SELECT id_recipes FROM Recipes WHERE title=?", (recipe["title"],))
        row = cursor.fetchone()

        if row:
            id_recipes = row[0]
        else:
            # Если рецепта нет, добавляем
            cursor.execute(
                "INSERT INTO Recipes (title, description, id_cooking_time, id_difficulty, id_calorie_content) VALUES (?, ?, ?, ?, ?)",
                (recipe["title"], recipe.get("steps", ""), None, None, None)
            )
            id_recipes = cursor.lastrowid

        # Добавляем запись в историю выполнения
        cursor.execute(
            "INSERT INTO History (id_user, id_recipes, favorite, done) VALUES (?, ?, ?, ?)",
            (id_user, id_recipes, 0, 1)
        )

    con.commit()
    con.close()

    return RedirectResponse(url=f"/results/{filename}", status_code=303)
'''
#история
# История
@app.get("/history", response_class=HTMLResponse)
async def get_history(request: Request):
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

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
    con.close()

    history = [
        {
            "id_history": row[0], 
            "title": row[1], 
            "description": row[2], 
            "favorite": row[3],
            "comment": row[4]  # Комментарий может быть None
        } 
        for row in rows
    ]

    return templates.TemplateResponse("history.html", {"request": request, "history": history})


@app.post("/history/favorite/{id_history}")
async def toggle_favorite(id_history: int, request: Request):
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    # Проверяем, кому принадлежит запись
    cursor.execute("SELECT id_user, favorite FROM History WHERE id_history = ?", (id_history,))
    row = cursor.fetchone()
    if not row or row[0] != id_user:
        con.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    current_fav = row[1]
    new_fav = 0 if current_fav else 1
    cursor.execute("UPDATE History SET favorite = ? WHERE id_history = ?", (new_fav, id_history))

    con.commit()
    con.close()

    # Перенаправляем обратно на страницу истории
    return RedirectResponse(url="/history", status_code=303)

# Эндпоинты для комментариев
@app.post("/history/comment/{id_history}")
async def add_comment(id_history: int, request: Request, comment: str = Form("")):
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

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
            con.close()
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
        else:
            # Добавляем новый комментарий
            cursor.execute("""
                INSERT INTO Comment (id_user, id_recipe, comment) 
                VALUES (?, ?, ?)
            """, (id_user, id_recipes, comment))

        con.commit()
        con.close()

        # Перенаправляем обратно на страницу истории
        return RedirectResponse(url="/history", status_code=303)

    except Exception as e:
        con.close()
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении комментария: {str(e)}")

@app.delete("/history/comment/{id_history}")
async def delete_comment(id_history: int, request: Request):
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

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
            con.close()
            raise HTTPException(status_code=403, detail="Forbidden")

        id_recipes = row[1]

        # Удаляем комментарий
        cursor.execute("""
            DELETE FROM Comment 
            WHERE id_user = ? AND id_recipe = ?
        """, (id_user, id_recipes))

        con.commit()
        con.close()

        return {"success": True, "message": "Комментарий удален"}

    except Exception as e:
        con.close()
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении комментария: {str(e)}")
#избранное
@app.get("/favorite", response_class=HTMLResponse)
async def get_favorites(request: Request):
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    cursor.execute("""
        SELECT h.id_history, r.title, r.description
        FROM History h
        JOIN Recipes r ON h.id_recipes = r.id_recipes
        WHERE h.id_user = ? AND h.favorite = 1
        ORDER BY h.id_history DESC
    """, (id_user,))
    rows = cursor.fetchall()
    con.close()

    favorites = [{"id_history": row[0], "title": row[1], "description": row[2]} for row in rows]

    return templates.TemplateResponse("favorite.html", {"request": request, "favorites": favorites})


@app.post("/favorite/remove/{id_history}")
async def remove_favorite(id_history: int, request: Request):
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    # Проверяем, что запись принадлежит пользователю
    cursor.execute("SELECT id_user FROM History WHERE id_history = ?", (id_history,))
    row = cursor.fetchone()
    if not row or row[0] != id_user:
        con.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    # Снимаем отметку избранного
    cursor.execute("UPDATE History SET favorite = 0 WHERE id_history = ?", (id_history,))

    con.commit()
    con.close()

    return RedirectResponse(url="/favorite", status_code=303)



# отправка на другой сервер
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
            print(f"⚠️ База данных не найдена по пути: {DB_PATH}")
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
        
        print(f"🔍 Для пользователя {user_id} найдено запрещенных продуктов: {len(forbidden_products)}")
        if forbidden_products:
            print(f"🚫 Запрещенные продукты: {', '.join(forbidden_products)}")
        
        return forbidden_products
        
    except sqlite3.Error as e:
        print(f"❌ Ошибка базы данных: {e}")
        return []
    except Exception as e:
        print(f"❌ Неожиданная ошибка при получении запрещенных продуктов: {e}")
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
        print(f"🚫 Удалены запрещенные ингредиенты: {', '.join(removed_ingredients)}")
    
    return filtered_ingredients

def get_cooking_times():
    """Получает варианты времени приготовления из базы данных"""
    try:
        if not os.path.exists(DB_PATH):
            print(f"⚠️ База данных не найдена по пути: {DB_PATH}")
            return []
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        cursor.execute("SELECT id_cooking_time, title FROM CookingTime")
        cooking_times = cursor.fetchall()
        con.close()
        
        print(f"🔧 Получено вариантов времени приготовления: {len(cooking_times)}")
        return cooking_times
        
    except sqlite3.Error as e:
        print(f"❌ Ошибка базы данных при получении времени приготовления: {e}")
        return []
    except Exception as e:
        print(f"❌ Неожиданная ошибка при получении времени приготовления: {e}")
        return []

def get_difficulties():
    """Получает варианты сложности из базы данных"""
    try:
        if not os.path.exists(DB_PATH):
            print(f"⚠️ База данных не найдена по пути: {DB_PATH}")
            return []
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        cursor.execute("SELECT id_difficulty, title FROM Difficulty")
        difficulties = cursor.fetchall()
        con.close()
        
        print(f"🔧 Получено вариантов сложности: {len(difficulties)}")
        return difficulties
        
    except sqlite3.Error as e:
        print(f"❌ Ошибка базы данных при получении сложности: {e}")
        return []
    except Exception as e:
        print(f"❌ Неожиданная ошибка при получении сложности: {e}")
        return []

def get_calorie_contents():
    """Получает варианты калорийности из базы данных"""
    try:
        if not os.path.exists(DB_PATH):
            print(f"⚠️ База данных не найдена по пути: {DB_PATH}")
            return []
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        cursor.execute("SELECT id_calorie_content, title FROM CalorieContent")
        calorie_contents = cursor.fetchall()
        con.close()
        
        print(f"🔧 Получено вариантов калорийности: {len(calorie_contents)}")
        return calorie_contents
        
    except sqlite3.Error as e:
        print(f"❌ Ошибка базы данных при получении калорийности: {e}")
        return []
    except Exception as e:
        print(f"❌ Неожиданная ошибка при получении калорийности: {e}")
        return []
    

def get_recipe_preferences():
    """Получает все предпочтения для рецептов из базы данных"""
    return {
        "cooking_times": get_cooking_times(),
        "difficulties": get_difficulties(),
        "calorie_contents": get_calorie_contents()
    }

@app.get("/upload", response_class=HTMLResponse)
async def get_upload_form(request: Request):
    # Получаем ID пользователя и его предпочтения
    user_id = get_current_user(request)
    preferences_data = get_all_preferences_with_user(user_id)
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "preferences": preferences_data
    })

# Первый запрос - отправка файла и получение task_id
@app.post("/start-processing")
async def start_processing(request: Request, file: UploadFile = File(...)):
    # Проверка типа файла
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
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
                raise HTTPException(status_code=500, detail="Не получен task_id")
            
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
            raise HTTPException(status_code=response.status_code, detail=error_detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка запроса: {str(e)}")

# Второй запрос - получение результата по task_id
@app.get("/get-result/{task_id}")
async def get_result(request: Request, task_id: str):
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id обязателен")
    
    print(f"🔧 Проверка статуса для task_id: {task_id}")
    
    try:
        async with httpx.AsyncClient() as client:
            # GET запрос с task_id в path
            url = f"{TASK_RESULT_URL}{task_id}"
            print(f"🔧 Запрос к URL: {url}")
            
            result_response = await client.get(url)
            print(f"🔧 Ответ от сервера: статус {result_response.status_code}")
            
            if result_response.status_code == 200:
                result_data = result_response.json()
                print(f"🔧 Данные ответа: {result_data}")
                
                status = result_data.get("status")
                
                if status == "done":
                    # Обрабатываем новую структуру данных
                    ingredients_data = result_data.get("ingredients", {})
                    print(f"🔧 Сырые данные ингредиентов: {ingredients_data}")
                    
                    # Если ingredients - это объект с ключом "ingredients"
                    if isinstance(ingredients_data, dict) and "ingredients" in ingredients_data:
                        ingredients_list = ingredients_data["ingredients"]
                        # Извлекаем названия ингредиентов из объектов
                        ingredients = [ingredient.get("name", "") for ingredient in ingredients_list if ingredient.get("name")]
                    # Если ingredients - это простой массив строк (старая структура)
                    elif isinstance(ingredients_data, list):
                        ingredients = ingredients_data
                    else:
                        ingredients = []
                    
                    # Получаем запрещенные продукты пользователя и фильтруем ингредиенты
                    user_id = get_current_user(request)
                    forbidden_products = get_forbidden_products(user_id)
                    
                    if forbidden_products:
                        original_count = len(ingredients)
                        ingredients = filter_ingredients_by_forbidden(ingredients, forbidden_products)
                        filtered_count = len(ingredients)
                        
                        if filtered_count < original_count:
                            print(f"🔧 Отфильтровано ингредиентов: {original_count} -> {filtered_count}")
                    
                    print(f"🔧 Обработанные ингредиенты: {ingredients}")
                    
                    return {
                        "status": "done", 
                        "ingredients": ingredients,
                        "raw_ingredients": ingredients_data,
                        "forbidden_products_removed": forbidden_products if forbidden_products else [],
                        "task_id": task_id
                    }
                    
                elif status == "processing":
                    print("⏳ Задача все еще обрабатывается")
                    return {
                        "status": "processing",
                        "task_id": task_id,
                        "message": "Задача все еще обрабатывается"
                    }
                    
                elif status == "error":
                    error_msg = result_data.get("error", "Неизвестная ошибка")
                    print(f"❌ Ошибка обработки: {error_msg}")
                    return {
                        "status": "error",
                        "task_id": task_id,
                        "error": error_msg
                    }
                    
                else:
                    print(f"⚠️ Неизвестный статус: {status}")
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
                    print(f"❌ Ошибка от сервера: {error_detail}")
                except:
                    print(f"❌ Ошибка HTTP: {result_response.status_code}")
                    pass
                    
                raise HTTPException(
                    status_code=result_response.status_code, 
                    detail=error_detail
                )
                
    except Exception as e:
        print(f"💥 Ошибка в get_result: {str(e)}")
        import traceback
        print(f"💥 Traceback: {traceback.format_exc()}")
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
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id обязателен")
    
    print(f"🔧 Начало генерации рецептов для task_id: {task_id}")
    
    # Получаем запрещенные продукты пользователя
    user_id = get_current_user(request)
    forbidden_products = get_forbidden_products(user_id)
    
    if forbidden_products:
        print(f"🚫 Учитываем запрещенные продукты пользователя: {', '.join(forbidden_products)}")
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
                
                print(f"🔧 Попытка {attempt + 1}/{max_retries}")
                print(f"🔧 Данные запроса: {data}")
                
                response = await client.post(
                    f"{COOK_FROM_IMAGE_URL}{task_id}",
                    data=data,
                    timeout=60.0
                )
                
                print(f"🔧 Получен ответ: статус {response.status_code}")
                
                if response.status_code == 200:
                    result_data = response.json()
                    print(f"🔧 Успешный ответ получен")
                    
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
                    
                    print(f"💾 Рецепты сохранены локально: {local_recipes_path}")
                    
                    return {
                        "ingredients": ingredients,
                        "raw_ingredients": ingredients_data,
                        "recipes": result_data.get("recipes", []),
                        "feedback_used": result_data.get("feedback_used", ""),
                        "preferred_calorie_level": result_data.get("preferred_calorie_level", ""),
                        "preferred_cooking_time": result_data.get("preferred_cooking_time", ""),
                        "preferred_difficulty": result_data.get("preferred_difficulty", ""),
                        "excluded_recipes": result_data.get("excluded_recipes", ""),
                        "saved_to": str(local_recipes_path),  # Сохраняем локальный путь
                        "forbidden_products_considered": forbidden_products if forbidden_products else [],
                        "task_id": task_id
                    }
                    
                elif response.status_code == 429:
                    wait_time = base_retry_delay * (2 ** attempt)
                    print(f"⚠️ Превышен лимит запросов к Mistral API. Ждем {wait_time} секунд...")
                    
                    if attempt < max_retries - 1:
                        print(f"⏳ Повторная попытка через {wait_time} секунд...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        error_msg = "Превышен лимит запросов к AI-сервису. Пожалуйста, подождите несколько минут."
                        print(f"❌ {error_msg}")
                        raise HTTPException(status_code=429, detail=error_msg)
                        
                else:
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", f"HTTP {response.status_code}")
                    except:
                        error_detail = f"HTTP {response.status_code}"
                    
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=f"Ошибка при генерации рецептов: {error_detail}"
                    )
                    
        except httpx.TimeoutException as e:
            print(f"⏰ Таймаут при попытке {attempt + 1}")
            if attempt < max_retries - 1:
                wait_time = base_retry_delay * (attempt + 1)
                await asyncio.sleep(wait_time)
                continue
            raise HTTPException(status_code=504, detail="Таймаут при подключении к серверу")
            
        except Exception as e:
            print(f"💥 Ошибка при попытке {attempt + 1}: {str(e)}")
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
        return {"error": "Пользователь не авторизован"}
    
    forbidden_products = get_forbidden_products(user_id)
    
    return {
        "user_id": user_id,
        "forbidden_products": forbidden_products,
        "count": len(forbidden_products)
    }

# Новый endpoint для завершения рецепта и сохранения в историю
@app.post("/complete-recipe/{task_id}")
async def complete_recipe(task_id: str, request: Request):
    """
    Сохраняет завершенные рецепты в историю пользователя
    """
    try:
        form = await request.form()
        user_id = get_current_user(request)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Пользователь не авторизован")

        print(f"🔧 Сохранение завершенных рецептов для пользователя {user_id}, task_id: {task_id}")
        print(f"🔧 Полученные данные формы: {dict(form)}")
        
        # Получаем данные о рецептах из локального JSON файла
        local_recipes_path = Path(f"./local_recipes/{task_id}_recipes.json")
        if not local_recipes_path.exists():
            print(f"❌ Файл не найден: {local_recipes_path}")
            # Пробуем альтернативный путь (старый формат)
            alternative_path = Path(f"./recipes/{task_id}_recipes.json")
            if alternative_path.exists():
                local_recipes_path = alternative_path
                print(f"🔧 Найден альтернативный путь: {alternative_path}")
            else:
                raise HTTPException(status_code=404, detail=f"Файл с рецептами не найден. Искали: {local_recipes_path}")

        with open(local_recipes_path, "r", encoding="utf-8") as f:
            recipes_data = json.load(f)

        recipes = recipes_data.get("recipes", [])
        print(f"🔧 Найдено рецептов: {len(recipes)}")
        
        completed_recipe_indexes = set()

        # Определяем, какие рецепты пользователь выполнил, проверяя все steps
        for i, recipe in enumerate(recipes):
            steps_count = len(recipe.get("steps", []))
            if steps_count == 0:
                print(f"⚠️ У рецепта {i} нет шагов приготовления")
                continue
                
            selected_steps = form.getlist(f"completed_steps_{i}")
            print(f"🔧 Рецепт {i}: шагов {steps_count}, выполнено {len(selected_steps)}")
            
            # Проверяем, что выполнены все шаги
            if len(selected_steps) == steps_count:
                completed_recipe_indexes.add(i)
                print(f"✅ Рецепт '{recipe.get('name', '')}' полностью выполнен")

        # Сохраняем в базу данных
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()

        saved_recipes = []
        
        for i in completed_recipe_indexes:
            recipe = recipes[i]
            recipe_name = recipe.get("name", f"Рецепт {i+1}")
            
            print(f"🔧 Обрабатываем рецепт: {recipe_name}")
            
            # Проверяем есть ли рецепт в таблице Recipes
            cursor.execute("SELECT id_recipes FROM Recipes WHERE title=?", (recipe_name,))
            row = cursor.fetchone()

            if row:
                id_recipes = row[0]
                print(f"🔧 Рецепт уже существует в базе, id: {id_recipes}")
            else:
                # Если рецепта нет, добавляем
                steps_text = "\n".join([step.get("instruction", "") for step in recipe.get("steps", [])])
                cooking_time = recipe.get("cooking_time", "")
                difficulty = recipe.get("difficulty", "")
                calorie_level = recipe.get("calorie_level", "")
                
                print(f"🔧 Добавляем новый рецепт: {recipe_name}")
                print(f"🔧 Время приготовления: {cooking_time}")
                print(f"🔧 Сложность: {difficulty}")
                
                cursor.execute(
                    "INSERT INTO Recipes (title, description, cooking_time, difficulty, calorie_level) VALUES (?, ?, ?, ?, ?)",
                    (recipe_name, steps_text, cooking_time, difficulty, calorie_level)
                )
                id_recipes = cursor.lastrowid
                print(f"📝 Добавлен новый рецепт в базу: {recipe_name}, id: {id_recipes}")

            # Проверяем, нет ли уже такой записи в истории
            cursor.execute(
                "SELECT id_history FROM History WHERE id_user=? AND id_recipes=?",
                (user_id, id_recipes)
            )
            existing_record = cursor.fetchone()
            
            if not existing_record:
                # Добавляем запись в историю выполнения
                cursor.execute(
                    "INSERT INTO History (id_user, id_recipes, favorite, done) VALUES (?, ?, ?, ?)",
                    (user_id, id_recipes, 0, 1)
                )
                saved_recipes.append(recipe_name)
                print(f"📚 Рецепт '{recipe_name}' добавлен в историю пользователя")
            else:
                print(f"ℹ️ Рецепт '{recipe_name}' уже есть в истории пользователя")

        con.commit()
        con.close()

        return {
            "success": True,
            "message": f"Успешно сохранено {len(saved_recipes)} рецептов в историю",
            "saved_recipes": saved_recipes,
            "task_id": task_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка при сохранении рецептов: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении рецептов: {str(e)}")
    

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
    print(f"🔧 Тестовая генерация рецептов для task_id: {task_id}")
    
    # Получаем запрещенные продукты пользователя
    user_id = get_current_user(request)
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
        },
        {
            "name": "Запеченная брокколи с сыром",
            "ingredients": [
                {"name": "брокколи", "amount": "400 г"},
                {"name": "сыр чеддер", "amount": "100 г"},
                {"name": "сливки", "amount": "100 мл"},
                {"name": "чеснок", "amount": "2 зубчика"},
                {"name": "оливковое масло", "amount": "2 ст. ложки"},
                {"name": "соль", "amount": "по вкусу"},
                {"name": "перец", "amount": "по вкусу"}
            ],
            "steps": [
                {"order": 1, "instruction": "Разогреть духовку до 200°C. (5 минут)"},
                {"order": 2, "instruction": "Брокколи разобрать на соцветия, выложить в форму для запекания. (5 минут)"},
                {"order": 3, "instruction": "Полить оливковым маслом, посолить и поперчить. (2 минуты)"},
                {"order": 4, "instruction": "Запекать 15 минут. (15 минут)"},
                {"order": 5, "instruction": "Достать, посыпать тертым сыром, полить сливками. (3 минуты)"},
                {"order": 6, "instruction": "Запекать еще 5 минут до золотистой корочки. (5 минут)"}
            ],
            "cooking_time": "35 минут",
            "difficulty": "легко",
            "calorie_content": {
                "kcal": 180,
                "protein_g": 12,
                "fat_g": 14,
                "carb_g": 8
            },
            "calorie_level": "среднекалорийное"
        },
        {
            "name": "Суп-пюре из брокколи",
            "ingredients": [
                {"name": "брокколи", "amount": "500 г"},
                {"name": "картофель", "amount": "2 шт."},
                {"name": "лук репчатый", "amount": "1 шт."},
                {"name": "сливки", "amount": "100 мл"},
                {"name": "овощной бульон", "amount": "1 л"},
                {"name": "соль", "amount": "по вкусу"},
                {"name": "перец", "amount": "по вкусу"}
            ],
            "steps": [
                {"order": 1, "instruction": "Лук и картофель нарезать кубиками. (7 минут)"},
                {"order": 2, "instruction": "Брокколи разобрать на соцветия. (5 минут)"},
                {"order": 3, "instruction": "В кастрюле обжарить лук до прозрачности. (5 минут)"},
                {"order": 4, "instruction": "Добавить картофель и брокколи, залить бульоном. (3 минуты)"},
                {"order": 5, "instruction": "Варить 20 минут до мягкости овощей. (20 минут)"},
                {"order": 6, "instruction": "Измельчить блендером до однородности. (5 минут)"},
                {"order": 7, "instruction": "Добавить сливки, прогреть 2 минуты. (2 минуты)"}
            ],
            "cooking_time": "47 минут",
            "difficulty": "средне",
            "calorie_content": {
                "kcal": 150,
                "protein_g": 8,
                "fat_g": 6,
                "carb_g": 18
            },
            "calorie_level": "низкокалорийное"
        }
    ]

    # Фильтруем ингредиенты если есть запрещенные продукты
    filtered_recipes = test_recipes
    if forbidden_products:
        print(f"🚫 Фильтруем рецепты по запрещенным продуктам: {forbidden_products}")
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
                print(f"🚫 Пропущен рецепт '{recipe['name']}' из-за запрещенных продуктов")

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
    
    print(f"💾 Тестовые рецепты сохранены локально: {local_recipes_path}")
    
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
# API endpoint для получения предпочтений
# API endpoint для получения предпочтений
@app.get("/api/preferences")
async def get_preferences_api(request: Request):
    """Возвращает предпочтения в JSON формате с учетом пользователя"""
    user_id = get_current_user(request)
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


def get_user_preferences(user_id):
    """Получает предпочтения конкретного пользователя из базы данных"""
    if not user_id:
        return {}
    
    try:
        if not os.path.exists(DB_PATH):
            print(f"⚠️ База данных не найдена по пути: {DB_PATH}")
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
            print(f"🔧 Найдены предпочтения пользователя {user_id}: {user_data}")
            return {
                "preferences_time_id": user_data[0],
                "preferences_difficulty_id": user_data[1],
                "preferences_calorie_id": user_data[2],
                "preferred_cooking_time": user_data[3],  # title из CookingTime
                "preferred_difficulty": user_data[4],    # title из Difficulty
                "preferred_calorie_level": user_data[5]  # title из CalorieContent
            }
        else:
            print(f"ℹ️ Пользователь {user_id} не найден или предпочтения не установлены")
            return {}
            
    except sqlite3.Error as e:
        print(f"❌ Ошибка базы данных при получении предпочтений пользователя: {e}")
        return {}
    except Exception as e:
        print(f"❌ Неожиданная ошибка при получении предпочтений пользователя: {e}")
        return {}

def get_all_preferences_with_user(user_id):
    """Получает все предпочтения вместе с настройками пользователя"""
    all_preferences = get_recipe_preferences()
    user_preferences = get_user_preferences(user_id)
    
    return {
        "all_preferences": all_preferences,
        "user_preferences": user_preferences
    }