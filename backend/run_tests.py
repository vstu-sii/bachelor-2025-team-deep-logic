"""
Файл: test_simple.py
Простой скрипт для запуска тестов через pytest
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Добавляем текущую папку в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app

class TestSimple:
    """Простые тесты для проверки работы приложения"""
    
    @pytest.fixture
    def client(self):
        with TestClient(app) as test_client:
            yield test_client
    
    def test_main_page(self, client):
        """Тест главной страницы"""
        print("1. Тестируем главную страницу...")
        response = client.get("/")
        assert response.status_code == 200, f"Ожидался статус 200, получил {response.status_code}"
        print("   ✅ Главная страница работает")
    
    def test_registration_page(self, client):
        """Тест страницы регистрации"""
        print("2. Тестируем страницу регистрации...")
        response = client.get("/registration")
        assert response.status_code == 200, f"Ожидался статус 200, получил {response.status_code}"
        print("   ✅ Страница регистрации работает")
    
    def test_upload_page(self, client):
        """Тест страницы загрузки"""
        print("3. Тестируем страницу загрузки...")
        response = client.get("/upload")
        # Может быть 200 или редирект на авторизацию
        assert response.status_code in [200, 303, 401], f"Неожиданный статус: {response.status_code}"
        print("   ✅ Страница загрузки отвечает")
    
    def test_preferences_api(self, client):
        """Тест API предпочтений"""
        print("4. Тестируем API предпочтений...")
        response = client.get("/api/preferences")
        # Может требовать авторизацию
        assert response.status_code in [200, 401], f"Неожиданный статус: {response.status_code}"
        print("   ✅ API предпочтений отвечает")

if __name__ == "__main__":
    # Если запускаем напрямую, используем pytest
    pytest.main([__file__, "-v", "-s"])