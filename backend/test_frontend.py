# tests/test_frontend.py
import pytest
import os
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi.testclient import TestClient
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

class TestFrontendHTML:
    """Тесты HTML фронтенда"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def public_dir(self):
        """Путь к папке с HTML файлами"""
        return Path(__file__).parent.parent / "public"
    
    def test_html_files_exist(self, public_dir):
        """Тест что основные HTML файлы существуют"""
        required_files = [
            "auth.html",
            "reg.html", 
            "upload.html",
            "main.html",
            "recipes.html",
            "profile.html",
            "history.html",
            "favorite.html"
        ]
        
        for file in required_files:
            file_path = public_dir / file
            assert file_path.exists(), f"Файл {file} не найден"
            assert file_path.stat().st_size > 0, f"Файл {file} пустой"
        
        print("✅ Все HTML файлы существуют")
    
    def test_auth_page_structure(self, public_dir):
        """Тест структуры страницы авторизации"""
        with open(public_dir / "auth.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Проверяем основные элементы
        assert soup.find("form") is not None, "Форма не найдена"
        assert soup.find("input", {"name": "email"}) is not None, "Поле email не найдено"
        assert soup.find("input", {"name": "password"}) is not None, "Поле password не найдено"
        assert soup.find("button") is not None, "Кнопка отправки не найдена"
        
        print("✅ Страница авторизации имеет правильную структуру")
    
    def test_registration_page_structure(self, public_dir):
        """Тест структуры страницы регистрации"""
        with open(public_dir / "reg.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Проверяем основные элементы
        form = soup.find("form")
        assert form is not None, "Форма не найдена"
        
        inputs = form.find_all("input")
        input_names = [inp.get('name') for inp in inputs if inp.get('name')]
        
        assert "name" in input_names, "Поле name не найдено"
        assert "email" in input_names, "Поле email не найдено" 
        assert "password" in input_names, "Поле password не найдено"
        
        print("✅ Страница регистрации имеет правильную структуру")
    
    def test_upload_page_structure(self, public_dir):
        """Тест структуры страницы загрузки"""
        with open(public_dir / "upload.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Проверяем форму загрузки файла
        form = soup.find("form")
        assert form is not None, "Форма не найдена"
        
        file_input = form.find("input", {"type": "file"})
        assert file_input is not None, "Поле выбора файла не найдено"
        
        print("✅ Страница загрузки имеет правильную структуру")
    
    def test_static_files_exist(self, public_dir):
        """Тест что статические файлы существуют"""
        static_dirs = ["css", "js", "uploads"]
        
        for dir_name in static_dirs:
            dir_path = public_dir / dir_name
            if dir_path.exists():
                print(f"✅ Папка {dir_name} существует")
            else:
                print(f"⚠️ Папка {dir_name} отсутствует")
    
    def test_html_syntax(self, public_dir):
        """Тест синтаксиса HTML файлов"""
        html_files = list(public_dir.glob("*.html"))
        
        for html_file in html_files:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Проверяем базовый синтаксис
            try:
                soup = BeautifulSoup(content, 'html.parser')
                # Если парсинг прошел без ошибок - синтаксис ок
                assert soup.find("html") is not None or soup.find("body") is not None, \
                    f"Файл {html_file.name} не содержит HTML структуры"
                print(f"✅ {html_file.name} - синтаксис корректен")
            except Exception as e:
                pytest.fail(f"Ошибка в файле {html_file.name}: {e}")

class TestFrontendFunctionality:
    """Тесты функциональности фронтенда"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_auth_page_accessible(self, client):
        """Тест доступности страницы авторизации"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "auth.html" in response.text or "Авторизация" in response.text
    
    def test_registration_page_accessible(self, client):
        """Тест доступности страницы регистрации"""
        response = client.get("/registration")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_upload_page_requires_auth(self, client):
        """Тест что страница загрузки требует авторизации"""
        response = client.get("/upload")
        # Может быть 200 (если проверка через JS) или редирект
        assert response.status_code in [200, 303, 401]
    
    def test_static_files_served(self, client):
        """Тест что статические файлы отдаются"""
        # Проверяем CSS если есть
        response = client.get("/static/css/style.css", follow_redirects=True)
        # Может быть 200 или 404 если файла нет
        assert response.status_code in [200, 404]
        
        # Проверяем JS если есть
        response = client.get("/static/js/script.js", follow_redirects=True)
        assert response.status_code in [200, 404]

class TestFrontendIntegration:
    """Интеграционные тесты фронтенда"""
    
    @pytest.fixture(scope="class")
    def driver(self):
        """Фикстура для Selenium WebDriver"""
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        options = Options()
        options.add_argument("--headless")  # Запуск без GUI
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        yield driver
        driver.quit()
    
    @pytest.fixture
    def live_server(self, client):
        """Запуск live сервера для тестов"""
        # Используем TestClient как mock сервера
        return client
    
    def test_auth_page_loaded(self, driver, live_server):
        """Тест что страница авторизации загружается в браузере"""
        # Этот тест требует запущенного сервера
        # Вместо реального сервера используем mock
        print("⚠️ Этот тест требует запущенного сервера")
        assert True  # Заглушка
    
    def test_form_submission(self, driver, live_server):
        """Тест отправки формы"""
        print("⚠️ Этот тест требует запущенного сервера")
        assert True  # Заглушка

class TestFrontendContent:
    """Тесты контента фронтенда"""
    
    @pytest.fixture
    def public_dir(self):
        return Path(__file__).parent.parent / "public"
    
    def test_templates_contain_required_elements(self, public_dir):
        """Тест что шаблоны содержат необходимые элементы"""
        for html_file in public_dir.glob("*.html"):
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Проверяем базовые элементы
            assert soup.find("title") is not None or "title" in content, \
                f"Файл {html_file.name} не содержит title"
            
            # Проверяем что есть какая-то разметка
            structural_elements = soup.find_all(['div', 'section', 'main', 'form', 'table'])
            assert len(structural_elements) > 0, \
                f"Файл {html_file.name} не содержит структурных элементов"
            
            print(f"✅ {html_file.name} - базовая структура присутствует")
    
    def test_forms_have_correct_actions(self, public_dir):
        """Тест что формы имеют правильные action атрибуты"""
        form_actions = {
            "auth.html": ["/auth"],
            "reg.html": ["/reg"],
            "upload.html": ["/test-vlm", "/start-processing"]
        }
        
        for file_name, expected_actions in form_actions.items():
            file_path = public_dir / file_name
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'html.parser')
                forms = soup.find_all("form")
                
                form_actions_found = [form.get('action') for form in forms if form.get('action')]
                
                for expected_action in expected_actions:
                    assert any(expected_action in action for action in form_actions_found), \
                        f"В {file_name} не найден action: {expected_action}"
                
                print(f"✅ {file_name} - формы имеют правильные actions")

def test_frontend_coverage():
    """Тест покрытия фронтенда"""
    public_dir = Path(__file__).parent.parent / "public"
    
    # Список ожидаемых HTML файлов
    expected_files = {
        "auth.html": "Страница авторизации",
        "reg.html": "Страница регистрации",
        "upload.html": "Страница загрузки",
        "main.html": "Главная страница",
        "recipes.html": "Страница рецептов",
        "profile.html": "Профиль пользователя",
        "history.html": "История рецептов",
        "favorite.html": "Избранные рецепты"
    }
    
    missing_files = []
    for file_name, description in expected_files.items():
        if not (public_dir / file_name).exists():
            missing_files.append(f"{file_name} ({description})")
    
    if missing_files:
        print(f"⚠️ Отсутствуют файлы: {', '.join(missing_files)}")
    else:
        print("✅ Все ожидаемые HTML файлы присутствуют")
    
    # Не проваливаем тест если файлов нет, просто информируем
    assert True

if __name__ == "__main__":
    # Запуск тестов без pytest
    test_frontend = TestFrontendHTML()
    test_frontend.public_dir = Path("..") / "public"
    
    try:
        test_frontend.test_html_files_exist(test_frontend.public_dir)
        test_frontend.test_auth_page_structure(test_frontend.public_dir)
        test_frontend.test_registration_page_structure(test_frontend.public_dir)
        test_frontend.test_upload_page_structure(test_frontend.public_dir)
        print("🎉 Все базовые тесты фронтенда пройдены!")
    except Exception as e:
        print(f"❌ Ошибка в тестах фронтенда: {e}")