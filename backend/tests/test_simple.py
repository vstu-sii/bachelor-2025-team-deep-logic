def test_simple():
    """Простой тест для проверки работы pytest"""
    assert 1 + 1 == 2

def test_main_page(client):
    """Тест главной страницы"""
    response = client.get("/")
    assert response.status_code == 200
    assert "auth.html" in response.text

def test_registration_page(client):
    """Тест страницы регистрации"""
    response = client.get("/registration")
    assert response.status_code == 200