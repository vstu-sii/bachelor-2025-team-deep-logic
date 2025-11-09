from fastapi import FastAPI, HTTPException, Body, status, Request, Form,UploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path


from pydantic import BaseModel

import sqlite3;

from itsdangerous import URLSafeTimedSerializer
import os

# Секретный ключ (в реальном проекте храните в переменных окружения!)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
serializer = URLSafeTimedSerializer(SECRET_KEY)

app = FastAPI()

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

#история
@app.get("/history", response_class=HTMLResponse)
async def get_history(request: Request):
    id_user = get_current_user(request)
    if not id_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    con = sqlite3.connect("../bd/my_database.db")
    cursor = con.cursor()

    cursor.execute("""
        SELECT h.id_history, r.title, r.description, h.favorite
        FROM History h
        JOIN Recipes r ON h.id_recipes = r.id_recipes
        WHERE h.id_user = ? AND h.done = 1
        ORDER BY h.id_history DESC
    """, (id_user,))
    rows = cursor.fetchall()
    con.close()

    history = [{"id_history": row[0], "title": row[1], "description": row[2], "favorite": row[3]} for row in rows]


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
