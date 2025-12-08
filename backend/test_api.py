import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

class TestAuthentication:
    """Тесты аутентификации - не требуют изображений"""
    
    def test_auth_page_accessible(self, client):
        """Тест доступности страницы авторизации"""
        response = client.get("/")
        assert response.status_code == 200
        # Проверяем что это HTML страница
        assert "text/html" in response.headers["content-type"]
        # Проверяем наличие ключевых элементов на странице авторизации
        assert "email" in response.text  # Поле email
        assert "password" in response.text  # Поле password
    
    
    
    def test_failed_auth_wrong_password(self, client, mock_db):
        """Тест неудачной авторизации"""

        
        mock_con, mock_cursor = mock_db
        
        # Настраиваем мок: пользователь найден, но пароль не совпадает
        mock_cursor.fetchone.side_effect = [
            (1, "correct_password"),  # Для проверки пользователя
        ]
        
        response = client.post("/auth", data={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 200
        # Проверяем что остаемся на странице авторизации с ошибкой
        assert "text/html" in response.headers["content-type"]
        # Проверяем сообщение об ошибке (может быть на русском)
        assert "Неверный" in response.text or "парол" in response.text.lower()



class TestImageProcessing:
    """Тесты обработки изображений - с моками"""
    
    
    
    def test_file_validation(self, client):
        """Тест валидации типа файла"""
        # Пытаемся загрузить не изображение
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = client.post("/start-processing", files=files)
        
        # Должна быть ошибка валидации
        assert response.status_code == 400
        assert "Файл должен быть изображением" in response.text
    
    
class TestRecipeGeneration:
    """Тесты генерации рецептов"""
    
    def test_generate_test_recipes(self, authenticated_client, mock_db):
        """Тест генерации тестовых рецептов"""
        mock_con, mock_cursor = mock_db
        
        response = authenticated_client.post(
            "/generate-test-recipes/test-task-123",
            data={
                "dietary": "нет",
                "user_feedback": "быстрое приготовление",
                "preferred_calorie_level": "средне",
                "preferred_cooking_time": "быстро", 
                "preferred_difficulty": "легко",
                "existing_recipes": "нет"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "recipes" in data
        assert len(data["recipes"]) > 0
        # Проверяем структуру тестового рецепта
        assert data["recipes"][0]["name"] == "Курица с брокколи в соусе терияки"
    
    def test_complete_recipe(self, authenticated_client, mock_db):
        """Тест сохранения завершенного рецепта"""
        mock_con, mock_cursor = mock_db
        
        # Настраиваем мок для проверки существования файла рецептов
        with patch('main.Path.exists', return_value=True):
            with patch('main.json.load') as mock_json:
                mock_json.return_value = {
                    "recipes": [
                        {
                            "name": "Курица с брокколи в соусе терияки",
                            "steps": [
                                {"order": 1, "instruction": "Шаг 1"},
                                {"order": 2, "instruction": "Шаг 2"}
                            ],
                            "prompt_version": "test_v1"
                        }
                    ]
                }
                
                response = authenticated_client.post(
                    "/complete-recipe/test-task-123",
                    data={"completed_steps_0": "on", "completed_steps_1": "on"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["success"] == True
                assert "saved_count" in data

class TestHistoryAndFavorites:
    """Тесты истории и избранного"""
    
    def test_history_page(self, authenticated_client, mock_db):
        """Тест страницы истории"""
        mock_con, mock_cursor = mock_db
        
        # Настраиваем данные истории
        mock_cursor.fetchall.return_value = [
            (1, "Рецепт 1", "Описание 1", 0, None),
            (2, "Рецепт 2", "Описание 2", 1, "Хороший рецепт")
        ]
        
        response = authenticated_client.get("/history")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "История" in response.text or "history" in response.text.lower()
    
    def test_favorites_page(self, authenticated_client, mock_db):
        """Тест страницы избранного"""
        mock_con, mock_cursor = mock_db
        
        # Настраиваем данные избранного
        mock_cursor.fetchall.return_value = [
            (1, "Избранный рецепт 1", "Описание 1"),
            (2, "Избранный рецепт 2", "Описание 2")
        ]
        
        response = authenticated_client.get("/favorite")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    

class TestAPIEndpoints:
    """Тесты JSON API endpoints"""
    
    def test_get_preferences_api(self, authenticated_client, mock_db):
        """Тест API получения предпочтений"""
        mock_con, mock_cursor = mock_db
        
        # Настраиваем данные предпочтений
        mock_cursor.fetchall.side_effect = [
            [(1, "быстро"), (2, "медленно")],  # cooking_times
            [(1, "легко"), (2, "сложно")],     # difficulties
            [(1, "низкая"), (2, "высокая")]    # calorie_contents
        ]
        
        # Для пользовательских предпочтений
        mock_cursor.fetchone.return_value = (1, 2, 3, "быстро", "легко", "низкая")
        
        response = authenticated_client.get("/api/preferences")
        assert response.status_code == 200
        data = response.json()
        assert "all_preferences" in data
        assert "user_preferences" in data
        assert data["user_id"] == 1
    
    def test_get_forbidden_products_api(self, authenticated_client, mock_db):
        """Тест API получения запрещенных продуктов"""
        mock_con, mock_cursor = mock_db
        
        # Настраиваем запрещенные продукты
        mock_cursor.fetchall.return_value = [
            ("орехи",),
            ("молоко",)
        ]
        
        response = authenticated_client.get("/user/forbidden-products")
        assert response.status_code == 200
        data = response.json()
        assert "forbidden_products" in data
        assert len(data["forbidden_products"]) == 2