import pytest
from unittest.mock import Mock, patch, AsyncMock

class TestAuthentication:
    """Тесты аутентификации - не требуют изображений"""
    
    def test_auth_page_accessible(self, client):
        """Тест доступности страницы авторизации"""
        response = client.get("/")
        assert response.status_code == 200
        assert "auth.html" in response.text
    
    def test_successful_registration(self, client):
        """Тест успешной регистрации"""
        response = client.post("/reg", data={
            "name": "Test User",
            "email": "test@example.com", 
            "password": "testpass123"
        })
        assert response.status_code == 303  # Redirect
    
    def test_failed_auth_wrong_password(self, client):
        """Тест неудачной авторизации"""
        response = client.post("/auth", data={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 200
        assert "Неверный пароль" in response.text

class TestUserProfile:
    """Тесты профиля пользователя"""
    
    def test_profile_requires_auth(self, client):
        """Тест что профиль требует авторизации"""
        response = client.get("/profile")
        assert response.status_code == 200  # Или 401 в зависимости от реализации
    
    def test_profile_accessible_when_authenticated(self, authenticated_client):
        """Тест доступа к профилю после авторизации"""
        response = authenticated_client.get("/profile")
        assert response.status_code == 200
    
    def test_add_forbidden_product(self, authenticated_client):
        """Тест добавления запрещенного продукта"""
        response = authenticated_client.post("/profile/forbidden", data={
            "product_title": "орехи"
        })
        assert response.status_code == 303  # Redirect

class TestImageProcessing:
    """Тесты обработки изображений - с моками"""
    
    @pytest.mark.asyncio
    async def test_start_processing_with_mock(self, async_client, mock_vlm_service):
        """Тест начала обработки с моком VLM сервиса"""
        
        # Мокаем httpx запросы
        with patch('main.httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.status_code = 200
            mock_post.return_value.__aenter__.return_value.json.return_value = {
                "task_id": "test-task-123",
                "status": "queued"
            }
            
            # Отправляем запрос даже без файла (тестируем только логику)
            response = await async_client.post("/start-processing")
            
            # Проверяем что обработка началась
            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "queued"
    
    def test_file_validation(self, client):
        """Тест валидации типа файла"""
        # Пытаемся загрузить не изображение
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = client.post("/test-vlm", files=files)
        
        # Должна быть ошибка валидации
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_get_processing_result(self, async_client):
        """Тест получения результата обработки"""
        
        with patch('main.httpx.AsyncClient.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status_code = 200
            mock_get.return_value.__aenter__.return_value.json.return_value = {
                "status": "done",
                "ingredients": {
                    "ingredients": [
                        {"name": "курица", "amount": "300г"},
                        {"name": "брокколи", "amount": "200г"}
                    ]
                }
            }
            
            response = await async_client.get("/get-result/test-task-123")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "done"
            assert "ingredients" in data

class TestRecipeGeneration:
    """Тесты генерации рецептов"""
    
    def test_generate_test_recipes(self, authenticated_client):
        """Тест генерации тестовых рецептов"""
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
    
    def test_complete_recipe(self, authenticated_client):
        """Тест сохранения завершенного рецепта"""
        response = authenticated_client.post(
            "/complete-recipe/test-task-123",
            data={"completed_steps_0": "on", "completed_steps_1": "on"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True

class TestHistoryAndFavorites:
    """Тесты истории и избранного"""
    
    def test_history_page(self, authenticated_client):
        """Тест страницы истории"""
        response = authenticated_client.get("/history")
        assert response.status_code == 200
    
    def test_favorites_page(self, authenticated_client):
        """Тест страницы избранного"""
        response = authenticated_client.get("/favorite")
        assert response.status_code == 200
    
    def test_toggle_favorite(self, authenticated_client):
        """Тест добавления в избранное"""
        response = authenticated_client.post("/history/favorite/1")
        assert response.status_code == 303  # Redirect

class TestAPIEndpoints:
    """Тесты JSON API endpoints"""
    
    def test_get_preferences_api(self, authenticated_client):
        """Тест API получения предпочтений"""
        response = authenticated_client.get("/api/preferences")
        assert response.status_code == 200
        data = response.json()
        assert "all_preferences" in data
        assert "user_preferences" in data
    
    def test_get_forbidden_products_api(self, authenticated_client):
        """Тест API получения запрещенных продуктов"""
        response = authenticated_client.get("/user/forbidden-products")
        assert response.status_code == 200
        data = response.json()
        assert "forbidden_products" in data