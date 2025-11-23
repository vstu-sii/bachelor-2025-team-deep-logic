import pytest
import asyncio
import sqlite3
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from httpx import AsyncClient
import pytest_asyncio

# Импортируем основное приложение
import sys
sys.path.append('..')
from main import app, get_current_user, serializer, SECRET_KEY

# Тестовые данные
TEST_USER = {
    "email": "test@example.com", 
    "name": "Test User",
    "password": "testpass123"
}

@pytest.fixture(scope="session")
def event_loop():
    """Создаем event loop для асинхронных тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def test_db():
    """Создаем временную тестовую базу данных"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    # Создаем схему тестовой БД
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Таблицы из твоей схемы
    cursor.executescript('''
        CREATE TABLE CookingTime (
            id_cooking_time INTEGER PRIMARY KEY AUTOINCREMENT,  
            title TEXT
        );
        
        CREATE TABLE Difficulty (
            id_difficulty INTEGER PRIMARY KEY AUTOINCREMENT,  
            title TEXT
        );
        
        CREATE TABLE CalorieContent (
            id_calorie_content INTEGER PRIMARY KEY AUTOINCREMENT,  
            title TEXT
        );
        
        CREATE TABLE User (
            id_user INTEGER PRIMARY KEY AUTOINCREMENT,  
            email TEXT, 
            login TEXT,
            password TEXT,
            preferences_time INTEGER,
            preferences_difficulty INTEGER,
            preferences_calorie INTEGER,
            FOREIGN KEY (preferences_time) REFERENCES CookingTime (id_cooking_time),
            FOREIGN KEY (preferences_difficulty) REFERENCES Difficulty (id_difficulty),
            FOREIGN KEY (preferences_calorie) REFERENCES CalorieContent (id_calorie_content)
        );
        
        CREATE TABLE Product (
            id_product INTEGER PRIMARY KEY AUTOINCREMENT,  
            title TEXT
        );
        
        CREATE TABLE Recipes (
            id_recipes INTEGER PRIMARY KEY AUTOINCREMENT,  
            title TEXT,
            description TEXT,
            cooking_time TEXT,
            difficulty TEXT,
            calorie_level TEXT
        );
        
        CREATE TABLE ProductsInRecipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            id_product INTEGER,
            id_recipe INTEGER,
            FOREIGN KEY (id_product) REFERENCES Product(id_product),
            FOREIGN KEY (id_recipe) REFERENCES Recipes(id_recipes)
        );
        
        CREATE TABLE ProductsInProhibited (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            id_product INTEGER,
            id_user INTEGER,
            FOREIGN KEY (id_product) REFERENCES Product(id_product),
            FOREIGN KEY (id_user) REFERENCES User(id_user)
        );
        
        CREATE TABLE History (
            id_history INTEGER PRIMARY KEY AUTOINCREMENT,  
            id_user INTEGER,
            id_recipes INTEGER,
            favorite INTEGER,
            done INTEGER,
            FOREIGN KEY (id_recipes) REFERENCES Recipes(id_recipes),
            FOREIGN KEY (id_user) REFERENCES User(id_user)
        );
        
        CREATE TABLE Comment (
            id_comment INTEGER PRIMARY KEY AUTOINCREMENT,  
            id_user INTEGER,
            id_recipe INTEGER,
            comment TEXT,
            FOREIGN KEY (id_recipe) REFERENCES Recipes(id_recipes),
            FOREIGN KEY (id_user) REFERENCES User(id_user)
        );
        
        -- Заполняем справочники
        INSERT INTO CookingTime (title) VALUES 
            ('Быстро'), ('Средне'), ('Долго');
            
        INSERT INTO Difficulty (title) VALUES 
            ('Легко'), ('Средне'), ('Сложно');
            
        INSERT INTO CalorieContent (title) VALUES 
            ('Низкокалорийное'), ('Средне'), ('Высококалорийное');
            
        -- Тестовый пользователь
        INSERT INTO User (email, login, password) VALUES 
            ('test@example.com', 'Test User', 'testpass123');
            
        -- Тестовые продукты
        INSERT INTO Product (title) VALUES 
            ('курица'), ('брокколи'), ('сыр'), ('орехи');
            
        -- Тестовый рецепт
        INSERT INTO Recipes (title, description, cooking_time, difficulty, calorie_level) VALUES 
            ('Тестовый рецепт', 'Описание тестового рецепта', '30 минут', 'Легко', 'Средне');
    ''')
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Удаляем временную БД после тестов
    os.unlink(db_path)

@pytest.fixture(scope="function")
def client(test_db):
    """Тестовый клиент FastAPI"""
    # Мокаем путь к БД
    import main
    main.DB_PATH = test_db
    
    with TestClient(app) as test_client:
        yield test_client

@pytest_asyncio.fixture(scope="function")
async def async_client(test_db):
    """Асинхронный тестовый клиент"""
    import main
    main.DB_PATH = test_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def authenticated_client(client):
    """Клиент с аутентифицированным пользователем"""
    # Создаем сессию для тестового пользователя
    session_data = serializer.dumps(1)  # ID тестового пользователя
    client.cookies.set("session", session_data)
    return client

@pytest.fixture
def test_image_path():
    """Путь к тестовому изображению - используем реальный файл или None"""
    # Пробуем найти существующее изображение
    possible_paths = [
        Path("tests/test_images/chicken_broccoli.jpg"),
        Path("tests/test_images/ingredients.jpg"), 
        Path("test_image.jpg"),
        Path("static/test_image.jpg")
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # Если нет реальных изображений - возвращаем None
    return None

@pytest.fixture
def mock_vlm_service(monkeypatch):
    """Мок для внешнего VLM сервиса"""
    
    async def mock_start_processing(*args, **kwargs):
        return {
            "task_id": "test-task-123",
            "status": "queued"
        }
    
    async def mock_get_result(*args, **kwargs):
        return {
            "status": "done",
            "ingredients": {
                "ingredients": [
                    {"name": "курица", "amount": "300г"},
                    {"name": "брокколи", "amount": "200г"},
                    {"name": "сыр", "amount": "100г"}
                ]
            }
        }
    
    # Мокаем HTTP запросы к внешним сервисам
    monkeypatch.setattr("main.REMOTE_URL", "http://mock-vlm-service")
    monkeypatch.setattr("main.TASK_RESULT_URL", "http://mock-vlm-service/task/")
    
    return {
        "start_processing": mock_start_processing,
        "get_result": mock_get_result
    }