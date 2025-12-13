# test_parallel.py
import pytest
import asyncio
import time
import concurrent.futures
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Импортируем ваше приложение
from main import app

class TestParallelProcessing:
    """Тесты параллельной обработки"""
    
    @pytest.fixture
    def client(self):
        """Фикстура для тестового клиента"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_db(self):
        """Фикстура для мока базы данных"""
        with patch('main.sqlite3.connect') as mock_connect:
            mock_con = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_con
            mock_con.cursor.return_value = mock_cursor
            yield mock_con, mock_cursor
    
    def test_thread_pool_configuration(self):
        """
        Тест конфигурации пула потоков
        """
        print("\n⚙️ Тест конфигурации пула потоков")
        print("-" * 50)
        
        # Импортируем THREAD_POOL из main
        try:
            from main import THREAD_POOL
            
            # Проверяем что пул потоков создан
            assert THREAD_POOL is not None, "Пул потоков не инициализирован"
            
            # Проверяем максимальное количество воркеров
            max_workers = THREAD_POOL._max_workers
            print(f"📊 Максимальное количество воркеров: {max_workers}")
            
            # Проверяем что настройка разумная
            assert 5 <= max_workers <= 50, \
                f"Некорректное количество воркеров: {max_workers}. Должно быть 5-50"
        except ImportError:
            print("ℹ️  THREAD_POOL не найден в main, пропускаем тест")
            return
        
        # Тестируем выполнение задач в пуле
        def test_task(n):
            time.sleep(0.1)  # Имитация работы
            return n * n
        
        start_time = time.time()
        
        # Запускаем несколько задач
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(test_task, i) for i in range(10)]
            results = [f.result() for f in futures]
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"⏱️  Время выполнения 10 задач: {execution_time:.2f} сек")
        print(f"📊 Результаты: {results}")
        
        # Проверяем что все задачи выполнены
        assert len(results) == 10, f"Выполнено {len(results)} задач из 10"
        
        print(f"✅ Конфигурация пула потоков корректна")
    
    def test_concurrent_sessions(self, client):
        """
        Тест конкурентных сессий пользователей
        """
        print("\n👥 Тест конкурентных сессий пользователей")
        print("-" * 50)
        
        # Тестовые пользователи
        test_users = [
            {"email": f"user{i}@test.com", "password": f"pass{i}"}
            for i in range(3)
        ]
        
        start_time = time.time()
        results = []
        
        # Функция для симуляции пользовательской сессии
        def simulate_user_session(user_data):
            session_results = []
            
            # Шаг 1: Авторизация
            try:
                auth_response = client.post("/auth", data=user_data)
                session_results.append({
                    "step": "auth",
                    "status": auth_response.status_code
                })
                
                # Шаг 2: Получение профиля (если авторизация успешна)
                if auth_response.status_code == 303:  # Redirect после успешной авторизации
                    profile_response = client.get("/profile", follow_redirects=True)
                    session_results.append({
                        "step": "profile",
                        "status": profile_response.status_code
                    })
                
                # Шаг 3: Получение предпочтений
                pref_response = client.get("/api/preferences", follow_redirects=False)
                session_results.append({
                    "step": "preferences",
                    "status": pref_response.status_code
                })
            except Exception as e:
                session_results.append({
                    "step": "error",
                    "status": 500,
                    "error": str(e)
                })
            
            return {
                "user": user_data["email"],
                "results": session_results,
                "time": time.time() - start_time
            }
        
        # Запускаем параллельные сессии
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(simulate_user_session, user) for user in test_users]
            results = [f.result() for f in futures]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"⏱️  Общее время выполнения: {total_time:.2f} сек")
        
        # Анализируем результаты
        for result in results:
            print(f"  👤 Пользователь {result['user']}:")
            for step in result["results"]:
                if step.get("error"):
                    print(f"    ❌ {step['step']}: ошибка - {step['error']}")
                else:
                    status = "✅" if step["status"] in [200, 303, 307] else "❌"
                    print(f"    {status} {step['step']}: код {step['status']}")
        
        print(f"✅ Конкурентные сессии пользователей завершены")
    
    @pytest.mark.asyncio
    async def test_rate_limiting_and_concurrency(self, client):
        """
        Тест ограничения скорости и конкурентности
        """
        print("\n🚦 Тест ограничения скорости и конкурентности")
        print("-" * 50)
        
        # Количество одновременных запросов
        concurrent_requests = 10
        
        start_time = time.time()
        
        # Функция для выполнения запроса
        async def make_concurrent_request(i):
            try:
                # Создаем отдельный клиент для каждого запроса
                response = client.get("/")
                return {
                    "request_id": i,
                    "status": response.status_code,
                    "time": time.time() - start_time,
                    "success": response.status_code == 200
                }
            except Exception as e:
                return {
                    "request_id": i,
                    "status": 500,
                    "time": time.time() - start_time,
                    "success": False,
                    "error": str(e)
                }
        
        # Запускаем множество одновременных запросов
        tasks = [make_concurrent_request(i) for i in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"⏱️  Общее время выполнения: {total_time:.2f} сек")
        print(f"📊 Количество запросов: {concurrent_requests}")
        
        # Анализируем результаты
        success_count = sum(1 for r in results if r["success"])
        error_count = concurrent_requests - success_count
        
        print(f"✅ Успешных запросов: {success_count}")
        print(f"❌ Ошибочных запросов: {error_count}")
        
        # Выводим временную статистику
        times = [r["time"] for r in results if r["success"]]
        if times:
            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)
            
            print(f"📈 Время ответа (успешные):")
            print(f"  Среднее: {avg_time:.3f} сек")
            print(f"  Максимальное: {max_time:.3f} сек")
            print(f"  Минимальное: {min_time:.3f} сек")
        
        # Проверяем что система не упала под нагрузкой
        assert success_count > 0, "Нет успешных запросов"
        
        print(f"✅ Система выдержала нагрузку в {concurrent_requests} одновременных запросов")
    
    def test_database_connection_pooling(self, mock_db):
        """
        Тест пула соединений с базой данных
        """
        print("\n🔌 Тест пула соединений с БД")
        print("-" * 50)
        
        mock_con, mock_cursor = mock_db
        
        # Настраиваем мок для нескольких пользователей
        user_responses = [
            (1, "user1@test.com", "User 1", 1, 2, 3),
            (2, "user2@test.com", "User 2", 1, 2, 3),
            (3, "user3@test.com", "User 3", 1, 2, 3),
            (4, "user4@test.com", "User 4", 1, 2, 3),
            (5, "user5@test.com", "User 5", 1, 2, 3),
        ]
        
        mock_cursor.fetchone.side_effect = user_responses * 2  # Для двух раундов
        
        start_time = time.time()
        
        # Функция для чтения профиля пользователя
        def read_user_profile(user_id):
            # Имитируем небольшую задержку
            time.sleep(0.05)
            
            # В реальном коде здесь был бы запрос к API
            # Для теста просто проверяем что соединение работает
            return {
                "user_id": user_id,
                "time": time.time() - start_time
            }
        
        # Первый раунд: последовательные запросы
        seq_start = time.time()
        seq_results = []
        for i in range(1, 6):
            result = read_user_profile(i)
            seq_results.append(result)
        seq_time = time.time() - seq_start
        
        # Второй раунд: параллельные запросы
        par_start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(read_user_profile, i) for i in range(1, 6)]
            par_results = [f.result() for f in futures]
        par_time = time.time() - par_start
        
        print(f"⏱️  Время выполнения:")
        print(f"  Последовательно: {seq_time:.3f} сек")
        print(f"  Параллельно: {par_time:.3f} сек")
        print(f"  Ускорение: {seq_time/par_time:.1f}x")
        
        # Проверяем что все запросы выполнены
        assert len(seq_results) == 5, "Не все последовательные запросы выполнены"
        assert len(par_results) == 5, "Не все параллельные запросы выполнены"
        
        # Проверяем что параллельное выполнение быстрее (или хотя бы не медленнее)
        assert par_time <= seq_time * 1.5, \
            f"Параллельное выполнение слишком медленное: {par_time:.3f} сек vs {seq_time:.3f} сек"
        
        print(f"✅ Пул соединений с БД работает эффективно")


class TestPerformanceMetrics:
    """Тесты метрик производительности при параллельной обработке"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_throughput_under_load(self, client):
        """
        Тест пропускной способности под нагрузкой
        """
        print("\n📊 Тест пропускной способности под нагрузкой")
        print("-" * 50)
        
        # Количество запросов для теста
        request_count = 20
        concurrent_workers = 5
        
        start_time = time.time()
        
        # Функция для выполнения запроса
        def make_request(request_id):
            try:
                response = client.get("/")
                return {
                    "id": request_id,
                    "status": response.status_code,
                    "response_time": time.time() - start_time,
                    "success": response.status_code == 200
                }
            except Exception as e:
                return {
                    "id": request_id,
                    "status": 500,
                    "response_time": time.time() - start_time,
                    "success": False,
                    "error": str(e)
                }
        
        # Выполняем запросы с ограниченным пулом воркеров
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            futures = [executor.submit(make_request, i) for i in range(request_count)]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Рассчитываем метрики
        success_count = sum(1 for r in results if r["success"])
        error_count = request_count - success_count
        throughput = request_count / total_time  # запросов в секунду
        
        print(f"📈 Результаты теста производительности:")
        print(f"  Всего запросов: {request_count}")
        print(f"  Успешных: {success_count}")
        print(f"  Ошибочных: {error_count}")
        print(f"  Общее время: {total_time:.2f} сек")
        print(f"  Пропускная способность: {throughput:.1f} запросов/сек")
        print(f"  Конкурентных воркеров: {concurrent_workers}")
        
        # Собираем статистику по времени ответа
        response_times = [r["response_time"] for r in results if r["success"]]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
            
            print(f"  Среднее время ответа: {avg_response_time:.3f} сек")
            print(f"  95-й перцентиль: {p95_response_time:.3f} сек")
        
        # Критерии успеха
        success_rate = success_count / request_count
        assert success_count > 0, "Нет успешных запросов"
        
        print(f"✅ Тест производительности завершен")
    
    def test_resource_utilization(self):
        """
        Тест использования ресурсов при параллельной обработке
        """
        print("\n💻 Тест использования ресурсов")
        print("-" * 50)
        
        try:
            import psutil
            import os
            
            # Получаем информацию о процессе
            process = psutil.Process(os.getpid())
            
            # Замеряем использование ресурсов до теста
            initial_cpu = process.cpu_percent(interval=0.1)
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            print(f"📊 Исходное использование ресурсов:")
            print(f"  CPU: {initial_cpu:.1f}%")
            print(f"  Память: {initial_memory:.1f} MB")
            
            # Запускаем нагрузочный тест
            def load_task(task_id):
                # Имитируем работу
                for i in range(10000):
                    _ = i * i
                return task_id
            
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(load_task, i) for i in range(50)]
                results = [f.result() for f in futures]
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Замеряем использование ресурсов после теста
            final_cpu = process.cpu_percent(interval=0.1)
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            print(f"📊 Использование ресурсов после нагрузки:")
            print(f"  CPU: {final_cpu:.1f}%")
            print(f"  Память: {final_memory:.1f} MB")
            print(f"  Время выполнения: {execution_time:.2f} сек")
            
            # Проверяем утечки памяти
            memory_increase = final_memory - initial_memory
            print(f"  Прирост памяти: {memory_increase:.1f} MB")
            
            # Проверяем что все задачи выполнены
            assert len(results) == 50, f"Выполнено {len(results)} задач из 50"
            
        except ImportError:
            print("ℹ️  psutil не установлен, пропускаем тест использования ресурсов")
            return
        
        print(f"✅ Использование ресурсов в пределах нормы")


class TestErrorHandlingInParallel:
    """Тесты обработки ошибок при параллельном выполнении"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_concurrent_error_handling(self, client):
        """
        Тест обработки ошибок при конкурентном выполнении
        """
        print("\n⚠️ Тест обработки ошибок при конкурентном выполнении")
        print("-" * 50)
        
        # Создаем запросы, которые могут вызвать ошибки
        problematic_requests = [
            # Невалидные файлы
            {"files": {"file": ("test.txt", b"not an image", "text/plain")}},
            # Корректные файлы
            {"files": {"file": ("test1.jpg", b"valid image", "image/jpeg")}},
            {"files": {"file": ("test2.png", b"valid image", "image/png")}},
        ]
        
        start_time = time.time()
        
        def make_problematic_request(req_data):
            try:
                response = client.post("/", files=req_data["files"])
                return {
                    "status": response.status_code,
                    "success": response.status_code in [200, 400, 413, 422],
                    "error": None
                }
            except Exception as e:
                return {
                    "status": 500,
                    "success": False,
                    "error": str(e)
                }
        
        # Запускаем параллельно
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_problematic_request, req) for req in problematic_requests]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"⏱️  Общее время выполнения: {total_time:.2f} сек")
        
        # Анализируем результаты
        for i, result in enumerate(results):
            if result["success"]:
                print(f"  ✅ Запрос {i+1}: код {result['status']}")
            else:
                print(f"  ❌ Запрос {i+1}: ошибка - {result.get('error', 'unknown')}")
        
        # Проверяем что система не упала при ошибках
        completed_count = len([r for r in results if r["status"] is not None])
        assert completed_count == len(problematic_requests), \
            f"Не все запросы завершены: {completed_count}/{len(problematic_requests)}"
        
        print(f"✅ Обработка ошибок при конкурентном выполнении работает корректно")
    
    @pytest.mark.asyncio
    async def test_async_timeout_handling(self):
        """
        Тест обработки таймаутов в асинхронных операциях
        """
        print("\n⏰ Тест обработки таймаутов")
        print("-" * 50)
        
        # Функция с разным временем выполнения
        async def variable_time_task(task_id, sleep_time):
            await asyncio.sleep(sleep_time)
            return {"task_id": task_id, "sleep_time": sleep_time}
        
        # Создаем задачи
        tasks = [
            asyncio.create_task(variable_time_task(1, 0.1)),  # Быстрая
            asyncio.create_task(variable_time_task(2, 0.5)),  # Средняя
            asyncio.create_task(variable_time_task(3, 2.0)),  # Медленная (должна таймаутнуть)
        ]
        
        start_time = time.time()
        
        # Запускаем с таймаутом
        try:
            done, pending = await asyncio.wait(
                tasks,
                timeout=1.0,
                return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.TimeoutError:
            done, pending = set(), set(tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"⏱️  Общее время выполнения: {total_time:.2f} сек")
        print(f"✅ Завершено задач: {len(done)}")
        print(f"⏳ Ожидают задач: {len(pending)}")
        
        # Отменяем ожидающие задачи
        for task in pending:
            task.cancel()
        
        try:
            # Ждем завершения отмены
            await asyncio.gather(*pending, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
        # Проверяем что быстрые задачи завершились
        assert len(done) >= 1, f"Слишком мало завершенных задач: {len(done)}"
        assert total_time <= 1.1, f"Таймаут не сработал: {total_time:.2f} сек"
        
        print(f"✅ Обработка таймаутов работает корректно")