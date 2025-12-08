# tests/run_frontend_tests.py
#!/usr/bin/env python3
"""
Скрипт для быстрого запуска фронтенд тестов
"""

import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_frontend import run_frontend_tests

if __name__ == "__main__":
    print("🚀 Запуск фронтенд тестов...")
    print()
    
    try:
        success = run_frontend_tests()
        if success:
            print("\n✅ Все фронтенд тесты пройдены успешно!")
            sys.exit(0)
        else:
            print("\n❌ Некоторые тесты не прошли")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка при запуске тестов: {e}")
        sys.exit(1)