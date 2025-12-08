import sqlite3
from datetime import datetime, timedelta
import pandas as pd

def calculate_avg_recipes_per_active_user_per_week(db_path='my_database.db'):
    """
    Рассчитывает среднее количество приготовленных рецептов 
    на одного активного пользователя в неделю.
    
    Формула: 
    среднее = количество приготовленных рецептов за неделю / 
             количество активных пользователей за неделю
    
    Активный пользователь = пользователь, который приготовил хотя бы 1 рецепт за неделю
    """
    
    print("=" * 70)
    print("📊 РАСЧЕТ СРЕДНЕГО КОЛИЧЕСТВА РЕЦЕПТОВ НА АКТИВНОГО ПОЛЬЗОВАТЕЛЯ В НЕДЕЛЮ")
    print("=" * 70)
    
    connection = None
    try:
        # Подключаемся к базе данных
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        # Проверяем наличие необходимых таблиц и колонок
        cursor.execute("PRAGMA table_info(History)")
        history_columns = [col[1] for col in cursor.fetchall()]
        
        if 'date_added' not in history_columns:
            print("❌ ОШИБКА: В таблице History отсутствует колонка date_added")
            print("   Необходимо добать колонку date_added типа DATE/TEXT")
            return None
        
        print("✅ Подключение к базе данных установлено")
        
        # Определяем дату начала и конца недели
        # Можно анализировать разные периоды
        periods = [
            ("Текущая неделя", datetime.now() - timedelta(days=7), datetime.now()),
            ("Прошлая неделя", datetime.now() - timedelta(days=14), datetime.now() - timedelta(days=7)),
            ("Последние 30 дней", datetime.now() - timedelta(days=30), datetime.now()),
        ]
        
        results = []
        
        for period_name, start_date, end_date in periods:
            print(f"\n📅 Анализ периода: {period_name}")
            print(f"   с {start_date.strftime('%Y-%m-%d')} по {end_date.strftime('%Y-%m-%d')}")
            
            # Форматируем даты для SQL запроса
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # 1. Количество приготовленных рецептов за период
            cursor.execute("""
            SELECT COUNT(*) as total_recipes
            FROM History h
            WHERE h.done = 1 
                AND h.date_added >= ? 
                AND h.date_added <= ?
            """, (start_date_str, end_date_str))
            
            total_recipes = cursor.fetchone()[0]
            
            # 2. Количество активных пользователей за период
            cursor.execute("""
            SELECT COUNT(DISTINCT h.id_user) as active_users
            FROM History h
            WHERE h.done = 1 
                AND h.date_added >= ? 
                AND h.date_added <= ?
            """, (start_date_str, end_date_str))
            
            active_users = cursor.fetchone()[0]
            
            # 3. Детальная статистика по пользователям
            cursor.execute("""
            SELECT 
                h.id_user,
                u.login,
                COUNT(*) as recipes_count
            FROM History h
            LEFT JOIN User u ON h.id_user = u.id_user
            WHERE h.done = 1 
                AND h.date_added >= ? 
                AND h.date_added <= ?
            GROUP BY h.id_user
            ORDER BY recipes_count DESC
            """, (start_date_str, end_date_str))
            
            user_stats = cursor.fetchall()
            
            # 4. Рассчитываем среднее значение
            if active_users > 0:
                average_recipes = total_recipes / active_users
            else:
                average_recipes = 0
            
            results.append({
                'period': period_name,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'total_recipes': total_recipes,
                'active_users': active_users,
                'avg_recipes_per_user': round(average_recipes, 2),
                'user_stats': user_stats
            })
            
            # Выводим результаты для периода
            print(f"   📈 Приготовлено рецептов: {total_recipes}")
            print(f"   👥 Активных пользователей: {active_users}")
            print(f"   📊 Среднее на пользователя: {average_recipes:.2f}")
            
            # Детальная статистика по пользователям (первые 5)
            if user_stats:
                print(f"   👤 Детальная статистика (первые 5 пользователей):")
                for user_id, login, count in user_stats[:5]:
                    print(f"      • {login or f'User {user_id}'}: {count} рецептов")
            
            print(f"   {'─' * 50}")
        
        # 5. Выводим итоговый отчет
        print("\n" + "=" * 70)
        print("📋 ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 70)
        
        df_results = pd.DataFrame(results)
        print("\n📊 Сводная таблица по периодам:")
        print(df_results[['period', 'total_recipes', 'active_users', 'avg_recipes_per_user']])
        
        # Находим лучший и худший периоды
        if len(results) > 1:
            best_period = max(results, key=lambda x: x['avg_recipes_per_user'])
            worst_period = min(results, key=lambda x: x['avg_recipes_per_user'])
            
            print(f"\n🏆 Лучший период: {best_period['period']}")
            print(f"   Среднее: {best_period['avg_recipes_per_user']:.2f} рецептов/пользователь")
            
            print(f"\n📉 Худший период: {worst_period['period']}")
            print(f"   Среднее: {worst_period['avg_recipes_per_user']:.2f} рецептов/пользователь")
        
        # 6. Рассчитываем среднее за все время
        print("\n📈 ОБЩАЯ СТАТИСТИКА ЗА ВСЕ ВРЕМЯ:")
        
        # Все приготовленные рецепты
        cursor.execute("""
        SELECT COUNT(*) as total_all_recipes
        FROM History h
        WHERE h.done = 1
        """)
        total_all_recipes = cursor.fetchone()[0]
        
        # Все активные пользователи (когда-либо готовившие)
        cursor.execute("""
        SELECT COUNT(DISTINCT h.id_user) as total_active_users
        FROM History h
        WHERE h.done = 1
        """)
        total_active_users = cursor.fetchone()[0]
        
        # Среднее за все время
        if total_active_users > 0:
            overall_average = total_all_recipes / total_active_users
            print(f"   Всего приготовлено рецептов: {total_all_recipes}")
            print(f"   Всего активных пользователей: {total_active_users}")
            print(f"   Среднее за все время: {overall_average:.2f} рецептов/пользователь")
        
        # 7. Статистика по дням недели
        print("\n📅 СТАТИСТИКА ПО ДНЯМ НЕДЕЛИ:")
        
        cursor.execute("""
        SELECT 
            strftime('%w', date_added) as day_of_week,
            CASE strftime('%w', date_added)
                WHEN '0' THEN 'Воскресенье'
                WHEN '1' THEN 'Понедельник'
                WHEN '2' THEN 'Вторник'
                WHEN '3' THEN 'Среда'
                WHEN '4' THEN 'Четверг'
                WHEN '5' THEN 'Пятница'
                WHEN '6' THEN 'Суббота'
            END as day_name,
            COUNT(*) as recipe_count,
            COUNT(DISTINCT id_user) as unique_users
        FROM History
        WHERE done = 1
        GROUP BY strftime('%w', date_added)
        ORDER BY day_of_week
        """)
        
        daily_stats = cursor.fetchall()
        
        if daily_stats:
            for day_num, day_name, recipe_count, unique_users in daily_stats:
                avg_per_user = recipe_count / unique_users if unique_users > 0 else 0
                print(f"   {day_name:<12}: {recipe_count:3} рецептов, {unique_users:2} пользователей, "
                      f"среднее: {avg_per_user:.2f}")
        
        # 8. Возвращаем результаты
        return results
        
    except sqlite3.Error as e:
        print(f"❌ ОШИБКА SQLite: {e}")
        return None
        
    except Exception as e:
        print(f"❌ ОБЩАЯ ОШИБКА: {e}")
        return None
        
    finally:
        if connection:
            connection.close()
            print("\n🔒 Соединение с базой данных закрыто")


def calculate_weekly_average_with_details(db_path='my_database.db', weeks_to_analyze=4):
    """
    Расширенная версия с анализом по неделям
    """
    
    print("=" * 70)
    print("📈 ПОНЕДЕЛЬНЫЙ АНАЛИЗ СРЕДНЕГО КОЛИЧЕСТВА РЕЦЕПТОВ")
    print("=" * 70)
    
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        weekly_results = []
        
        # Анализируем последние N недель
        for week_num in range(weeks_to_analyze):
            # Определяем границы недели
            end_date = datetime.now() - timedelta(weeks=week_num)
            start_date = end_date - timedelta(days=7)
            
            week_label = f"Неделя {weeks_to_analyze - week_num}" if week_num > 0 else "Текущая неделя"
            
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            # Основные метрики
            cursor.execute("""
            SELECT COUNT(*) as recipes_count
            FROM History 
            WHERE done = 1 
                AND date_added >= ? 
                AND date_added < ?
            """, (start_str, end_str))
            
            recipes_count = cursor.fetchone()[0]
            
            cursor.execute("""
            SELECT COUNT(DISTINCT id_user) as active_users
            FROM History 
            WHERE done = 1 
                AND date_added >= ? 
                AND date_added < ?
            """, (start_str, end_str))
            
            active_users = cursor.fetchone()[0]
            
            # Среднее
            avg_recipes = recipes_count / active_users if active_users > 0 else 0
            
            # Топ пользователей недели
            cursor.execute("""
            SELECT 
                h.id_user,
                u.login,
                COUNT(*) as user_recipes
            FROM History h
            LEFT JOIN User u ON h.id_user = u.id_user
            WHERE h.done = 1 
                AND h.date_added >= ? 
                AND h.date_added < ?
            GROUP BY h.id_user
            HAVING COUNT(*) > 0
            ORDER BY user_recipes DESC
            LIMIT 3
            """, (start_str, end_str))
            
            top_users = cursor.fetchall()
            
            weekly_results.append({
                'week': week_label,
                'period': f"{start_str} - {end_str}",
                'recipes': recipes_count,
                'active_users': active_users,
                'avg_per_user': round(avg_recipes, 2),
                'top_users': top_users
            })
        
        # Выводим результаты
        print("\n📊 ПОНЕДЕЛЬНАЯ СТАТИСТИКА:")
        print("-" * 80)
        print(f"{'Неделя':<15} {'Период':<23} {'Рецепты':<10} {'Пользователи':<12} {'Среднее':<10}")
        print("-" * 80)
        
        for result in weekly_results:
            print(f"{result['week']:<15} {result['period']:<23} "
                  f"{result['recipes']:<10} {result['active_users']:<12} "
                  f"{result['avg_per_user']:<10}")
            
            # Показываем топ пользователей недели
            if result['top_users']:
                print(f"   🏆 Топ пользователей: ", end="")
                for user_id, login, count in result['top_users']:
                    user_name = login if login else f"User {user_id}"
                    print(f"{user_name} ({count}), ", end="")
                print()
        
        print("-" * 80)
        
        # Рассчитываем среднее за все анализируемые недели
        total_recipes = sum(r['recipes'] for r in weekly_results)
        total_active_weeks = sum(1 for r in weekly_results if r['active_users'] > 0)
        
        if total_active_weeks > 0:
            avg_weekly_recipes = sum(r['recipes'] for r in weekly_results) / total_active_weeks
            avg_weekly_users = sum(r['active_users'] for r in weekly_results) / total_active_weeks
            overall_weekly_avg = avg_weekly_recipes / avg_weekly_users if avg_weekly_users > 0 else 0
            
            print(f"\n📈 СРЕДНИЕ ЗА {weeks_to_analyze} НЕДЕЛИ:")
            print(f"   Среднее рецептов в неделю: {avg_weekly_recipes:.1f}")
            print(f"   Среднее пользователей в неделю: {avg_weekly_users:.1f}")
            print(f"   Среднее рецептов на пользователя: {overall_weekly_avg:.2f}")
        
        connection.close()
        return weekly_results
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None


def export_results_to_csv(results, filename='avg_recipes_report.csv'):
    """
    Экспорт результатов в CSV файл
    """
    if results:
        try:
            import pandas as pd
            
            # Преобразуем результаты в DataFrame
            df = pd.DataFrame(results)
            
            # Упрощаем структуру для экспорта
            export_df = pd.DataFrame([
                {
                    'Период': r['period'],
                    'Начало': r['start_date'],
                    'Конец': r['end_date'],
                    'Рецепты': r['total_recipes'],
                    'Активные_пользователи': r['active_users'],
                    'Среднее_рецептов_на_пользователя': r['avg_recipes_per_user']
                }
                for r in results
            ])
            
            export_df.to_csv(filename, index=False, encoding='utf-8')
            print(f"\n💾 Результаты экспортированы в файл: {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при экспорте в CSV: {e}")


if __name__ == "__main__":
    # Основной расчет
    print("🚀 ЗАПУСК РАСЧЕТА СРЕДНЕГО КОЛИЧЕСТВА РЕЦЕПТОВ")
    print("=" * 70)
    
    # Запускаем основной расчет
    results = calculate_avg_recipes_per_active_user_per_week()
    
    if results:
        # Экспортируем результаты
        export_results_to_csv(results)
        
        # Запускаем понедельный анализ
        print("\n" + "=" * 70)
        print("📈 ДОПОЛНИТЕЛЬНЫЙ ПОНЕДЕЛЬНЫЙ АНАЛИЗ")
        print("=" * 70)
        
        weekly_results = calculate_weekly_average_with_details(weeks_to_analyze=8)
    
    print("\n✅ Расчет завершен!")