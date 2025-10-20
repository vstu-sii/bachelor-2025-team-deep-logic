-- ==================== БАЗОВЫЕ ТАБЛИЦЫ ====================

-- Создание таблицы пользователей
CREATE TABLE User (
    id_user INTEGER PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    login VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    preferences_time INTEGER,
    preferences_difficulty INTEGER,
    preferences_calorie INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы времени приготовления
CREATE TABLE CookingTime (
    id_cooking_time INTEGER PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(100) NOT NULL
);

-- Создание таблицы сложности
CREATE TABLE Difficulty (
    id_difficulty INTEGER PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(100) NOT NULL
);

-- Создание таблицы калорийности
CREATE TABLE CalorieContent (
    id_calorie_content INTEGER PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(100) NOT NULL
);

-- Создание таблицы продуктов
CREATE TABLE Product (
    id_product INTEGER PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL
);

-- Создание таблицы рецептов
CREATE TABLE Recipes (
    id_recipes INTEGER PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    id_cooking_time INTEGER,
    id_difficulty INTEGER,
    id_calorie_content INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_cooking_time) REFERENCES CookingTime(id_cooking_time),
    FOREIGN KEY (id_difficulty) REFERENCES Difficulty(id_difficulty),
    FOREIGN KEY (id_calorie_content) REFERENCES CalorieContent(id_calorie_content)
);

-- Создание таблицы продуктов в рецептах
CREATE TABLE ProductsInRecipes (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    id_product INTEGER NOT NULL,
    id_recipe INTEGER NOT NULL,
    quantity VARCHAR(100),
    FOREIGN KEY (id_product) REFERENCES Product(id_product),
    FOREIGN KEY (id_recipe) REFERENCES Recipes(id_recipes),
    UNIQUE KEY unique_product_recipe (id_product, id_recipe)
);

-- Создание таблицы запрещенных продуктов
CREATE TABLE ProductsInProhibited (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    id_product INTEGER NOT NULL,
    id_user INTEGER NOT NULL,
    FOREIGN KEY (id_product) REFERENCES Product(id_product),
    FOREIGN KEY (id_user) REFERENCES User(id_user),
    UNIQUE KEY unique_prohibited_product_user (id_product, id_user)
);

-- Создание таблицы истории
CREATE TABLE History (
    id_history INTEGER PRIMARY KEY AUTO_INCREMENT,
    id_user INTEGER NOT NULL,
    id_recipes INTEGER NOT NULL,
    favorite BOOLEAN DEFAULT FALSE,
    done BOOLEAN DEFAULT FALSE,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    FOREIGN KEY (id_user) REFERENCES User(id_user),
    FOREIGN KEY (id_recipes) REFERENCES Recipes(id_recipes)
);

-- Создание таблицы комментариев
CREATE TABLE Comment (
    id_comment INTEGER PRIMARY KEY AUTO_INCREMENT,
    id_user INTEGER NOT NULL,
    id_recipes INTEGER NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_user) REFERENCES User(id_user),
    FOREIGN KEY (id_recipes) REFERENCES Recipes(id_recipes)
);

-- Добавление внешних ключей для User (которые были определены отдельно)
ALTER TABLE User 
ADD FOREIGN KEY (preferences_time) REFERENCES CookingTime(id_cooking_time),
ADD FOREIGN KEY (preferences_difficulty) REFERENCES Difficulty(id_difficulty),
ADD FOREIGN KEY (preferences_calorie) REFERENCES CalorieContent(id_calorie_content);


-- ==================== ИНДЕКСЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ ====================

-- Индексы для таблицы User
CREATE INDEX idx_user_email ON User(email);
CREATE INDEX idx_user_login ON User(login);
CREATE INDEX idx_user_preferences ON User(preferences_time, preferences_difficulty, preferences_calorie);

-- Индексы для таблицы Recipes
CREATE INDEX idx_recipes_title ON Recipes(title);
CREATE INDEX idx_recipes_cooking_time ON Recipes(id_cooking_time);
CREATE INDEX idx_recipes_difficulty ON Recipes(id_difficulty);
CREATE INDEX idx_recipes_calorie ON Recipes(id_calorie_content);

-- Индексы для таблицы ProductsInRecipes
CREATE INDEX idx_products_in_recipes_product ON ProductsInRecipes(id_product);
CREATE INDEX idx_products_in_recipes_recipe ON ProductsInRecipes(id_recipe);

-- Индексы для таблицы ProductsInProhibited
CREATE INDEX idx_prohibited_user ON ProductsInProhibited(id_user);
CREATE INDEX idx_prohibited_product ON ProductsInProhibited(id_product);

-- Индексы для таблицы History
CREATE INDEX idx_history_user ON History(id_user);
CREATE INDEX idx_history_recipe ON History(id_recipes);
CREATE INDEX idx_history_favorite ON History(favorite);
CREATE INDEX idx_history_done ON History(done);
CREATE INDEX idx_history_time ON History(time);

-- Индексы для таблицы Comment
CREATE INDEX idx_comment_user ON Comment(id_user);
CREATE INDEX idx_comment_recipe ON Comment(id_recipes);
CREATE INDEX idx_comment_created ON Comment(created_at);

-- Индексы для таблицы Product
CREATE INDEX idx_product_title ON Product(title);

-- ==================== Схема для LLM данных (промпты, ответы) ====================

-- Дополнительная таблица для хранения промптов и ответов LLM
CREATE TABLE LLMInteractions (
    id_interaction INTEGER PRIMARY KEY AUTO_INCREMENT,
    id_user INTEGER,
    prompt_text TEXT NOT NULL,
    response_text TEXT,
    model_used VARCHAR(100),
    tokens_used INTEGER,
    interaction_type ENUM('recipe_generation', 'recipe_modification', 'nutrition_advice', 'other'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_user) REFERENCES User(id_user)
);

-- Индексы для LLMInteractions
CREATE INDEX idx_llm_user ON LLMInteractions(id_user);
CREATE INDEX idx_llm_type ON LLMInteractions(interaction_type);
CREATE INDEX idx_llm_created ON LLMInteractions(created_at);

