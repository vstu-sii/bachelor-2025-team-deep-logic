# conftest.py
import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import Mock, patch
import sqlite3

@pytest.fixture
def client():
    """Фикстура для клиента FastAPI"""
    return TestClient(app)

@pytest.fixture
def authenticated_client():
    """Фикстура для аутентифицированного клиента"""
    client = TestClient(app)
    
    # Мокаем проверку аутентификации
    with patch('main.get_current_user', return_value=1):
        yield client

@pytest.fixture
def mock_db():
    """Фикстура для мока базы данных"""
    with patch('main.sqlite3.connect') as mock_connect:
        mock_con = Mock()
        mock_cursor = Mock()
        mock_connect.return_value = mock_con
        mock_con.cursor.return_value = mock_cursor
        yield mock_con, mock_cursor

@pytest.fixture
def mock_vlm_service():
    """Фикстура для мока VLM сервиса"""
    with patch('main.httpx.AsyncClient') as mock_client:
        mock_instance = Mock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        yield mock_instance