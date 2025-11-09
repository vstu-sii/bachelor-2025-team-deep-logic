import sqlite3

# Устанавливаем соединение с базой данных
connection = sqlite3.connect('my_database.db')
cursor = connection.cursor()

# создаем таблицу CookingTime
cursor.execute("""CREATE TABLE IF NOT EXISTS CookingTime
                (id_cooking_time INTEGER PRIMARY KEY AUTOINCREMENT,  
                title TEXT
                );
            """)

# создаем таблицу Difficulty
cursor.execute("""CREATE TABLE IF NOT EXISTS Difficulty
                (id_difficulty INTEGER PRIMARY KEY AUTOINCREMENT,  
                title TEXT
                );
            """)

# создаем таблицу CalorieContent
cursor.execute("""CREATE TABLE IF NOT EXISTS CalorieContent
                (id_calorie_content INTEGER PRIMARY KEY AUTOINCREMENT,  
                title TEXT
                );
            """)

# создаем таблицу User
cursor.execute("""CREATE TABLE IF NOT EXISTS User
                (id_user INTEGER PRIMARY KEY AUTOINCREMENT,  
                email TEXT, 
                login TEXT,
                password TEXT,
                preferences_time INTEGER,
                preferences_difficulty INTEGER,
                preferences_calorie INTEGER,
                FOREIGN KEY (preferences_time)  REFERENCES CookingTime (id_cooking_time),
                FOREIGN KEY (preferences_difficulty)  REFERENCES Difficulty (id_difficulty),
                FOREIGN KEY (preferences_calorie)  REFERENCES CalorieContent (id_calorie_content)
                );
            """)

# создаем таблицу Product 
cursor.execute("""CREATE TABLE IF NOT EXISTS Product 
                (id_product INTEGER PRIMARY KEY AUTOINCREMENT,  
                title TEXT
                );
            """)

# создаем таблицу Recipes  
cursor.execute("""CREATE TABLE IF NOT EXISTS Recipes  
                (id_recipes INTEGER PRIMARY KEY AUTOINCREMENT,  
                title TEXT,
                description TEXT,
                id_cooking_time INTEGER,
                id_difficulty INTEGER,
                id_calorie_content INTEGER,
                FOREIGN KEY (id_cooking_time) REFERENCES CookingTime(id_cooking_time),
                FOREIGN KEY (id_difficulty) REFERENCES Difficulty(id_difficulty),
                FOREIGN KEY (id_calorie_content) REFERENCES CalorieContent(id_calorie_content)
                );
            """)

# создаем таблицу ProductsInRecipes 
cursor.execute("""CREATE TABLE IF NOT EXISTS ProductsInRecipes 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,  
                id_product INTEGER,
                id_recipe INTEGER,
                FOREIGN KEY (id_product) REFERENCES Product(id_product),
                FOREIGN KEY (id_recipe) REFERENCES Recipes(id_recipes)
                );
            """)

# создаем таблицу ProductsInProhibited 
cursor.execute("""CREATE TABLE IF NOT EXISTS ProductsInProhibited 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,  
                id_product INTEGER,
                id_user INTEGER,
                FOREIGN KEY (id_product) REFERENCES Product(id_product),
                FOREIGN KEY (id_user) REFERENCES User(id_user)
                );
            """)

# создаем таблицу History  
cursor.execute("""CREATE TABLE IF NOT EXISTS History  
                (id_history INTEGER PRIMARY KEY AUTOINCREMENT,  
                id_user INTEGER,
                id_recipes INTEGER,
                favorite INTEGER,
                done INTEGER,
                FOREIGN KEY (id_recipes) REFERENCES Recipes(id_recipes),
                FOREIGN KEY (id_user) REFERENCES User(id_user)
                );
            """)

# создаем таблицу Comment  
cursor.execute("""CREATE TABLE IF NOT EXISTS Comment   
                (id_comment INTEGER PRIMARY KEY AUTOINCREMENT,  
                id_user INTEGER,
                id_recipe INTEGER,
                comment TEXT,
                FOREIGN KEY (id_recipe) REFERENCES Recipes(id_recipes),
                FOREIGN KEY (id_user) REFERENCES User(id_user)
                );
            """)

# добавляем строку в таблицу User
#data = ("qwe", "rty", "123")
#cursor.execute("INSERT INTO User (email, login, password) VALUES (?, ?, ?)", data)



# добавляем строку в таблицу User
email = "artem@gmail.com"
result = cursor.execute("select password from User where email = ?", (email,)).fetchone()


print(f"{email} {result}")


# Сохраняем изменения и закрываем соединение
connection.commit()
connection.close()