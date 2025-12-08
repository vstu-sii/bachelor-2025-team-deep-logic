import sqlite3
from datetime import datetime

# Устанавливаем соединение с базой данных
connection = sqlite3.connect('my_database.db')
cursor = connection.cursor()

try:
    # Проверяем, существует ли колонка date_added
    cursor.execute("PRAGMA table_info(History)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    if 'date_added' not in column_names:
        # Добавляем новую колонку date_added типа TEXT (будем хранить дату в формате YYYY-MM-DD)
        cursor.execute("""
        ALTER TABLE History ADD COLUMN date_added TEXT;
        """)
        print("✅ Колонка 'date_added' добавлена в таблицу History")
    else:
        print("⚠️ Колонка 'date_added' уже существует в таблице History")
    
    # Получаем сегодняшнюю дату в формате YYYY-MM-DD
    today_date = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 Сегодняшняя дата: {today_date}")
    
    # Находим все записи с пустой датой (NULL) и заполняем сегодняшней датой
    cursor.execute("""
    UPDATE History 
    SET date_added = ? 
    WHERE date_added IS NULL OR date_added = '';
    """, (today_date,))
    
    # Получаем количество обновленных записей
    updated_count = cursor.rowcount
    print(f"✅ Обновлено {updated_count} записей в таблице History")
    
    # Проверяем, сколько всего записей в таблице History
    cursor.execute("SELECT COUNT(*) FROM History")
    total_records = cursor.fetchone()[0]
    print(f"📊 Всего записей в таблице History: {total_records}")
    
    # Проверяем, сколько записей с датой и без даты
    cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(date_added) as with_date,
        COUNT(*) - COUNT(date_added) as without_date
    FROM History
    """)
    
    stats = cursor.fetchone()
    print(f"📊 Статистика по датам:")
    print(f"  • Всего записей: {stats[0]}")
    print(f"  • С указанной датой: {stats[1]}")
    print(f"  • Без даты: {stats[2]}")
    
    # Показываем примеры записей (первые 5)
    cursor.execute("""
    SELECT id_history, id_user, id_recipes, date_added 
    FROM History 
    ORDER BY id_history 
    LIMIT 5
    """)
    
    sample_records = cursor.fetchall()
    if sample_records:
        print("\n📋 Примеры записей (первые 5):")
        for record in sample_records:
            print(f"  • ID: {record[0]}, User: {record[1]}, Recipe: {record[2]}, Date: {record[3] or 'Нет даты'}")
    
    # Проверяем, что колонка действительно добавлена
    cursor.execute("PRAGMA table_info(History)")
    updated_columns = cursor.fetchall()
    print("\n📋 Структура таблицы History после изменений:")
    for col in updated_columns:
        print(f"  • {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'} - Default: {col[4]}")
    
    # Сохраняем изменения
    connection.commit()
    print("\n✅ Изменения успешно сохранены в базе данных")
    
except sqlite3.Error as e:
    print(f"❌ Ошибка SQLite: {e}")
    connection.rollback()
    
except Exception as e:
    print(f"❌ Общая ошибка: {e}")
    connection.rollback()
    
finally:
    # Закрываем соединение
    connection.close()
    print("🔒 Соединение с базой данных закрыто")