-- ==================== БАЗОВЫЕ ТАБЛИЦЫ ====================

-- Пользователи
CREATE TABLE Users (
    id_user SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    login VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Продукты
CREATE TABLE Products (
    id_product SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Время приготовления (справочник)
CREATE TABLE CookingTime (
    id_cooking_time SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    min_minutes INTEGER,
    max_minutes INTEGER
);

-- Сложность (справочник)
CREATE TABLE Difficulty (
    id_difficulty SERIAL PRIMARY KEY,
    title VARCHAR(50) NOT NULL,
    description TEXT
);

-- Калорийность (справочник)
CREATE TABLE CalorieContent (
    id_calorie_content SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    min_calories INTEGER,
    max_calories INTEGER
);

-- ==================== ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЕЙ ====================

-- Предпочтения пользователей
CREATE TABLE UserPreferences (
    id_preference SERIAL PRIMARY KEY,
    id_user INTEGER NOT NULL REFERENCES Users(id_user) ON DELETE CASCADE,
    preference_type VARCHAR(50) NOT NULL, -- 'prohibited_product', 'cooking_time', 'difficulty', 'calorie'
    id_product INTEGER REFERENCES Products(id_product) ON DELETE CASCADE,
    id_cooking_time INTEGER REFERENCES CookingTime(id_cooking_time) ON DELETE SET NULL,
    id_difficulty INTEGER REFERENCES Difficulty(id_difficulty) ON DELETE SET NULL,
    id_calorie_content INTEGER REFERENCES CalorieContent(id_calorie_content) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== РЕЦЕПТЫ И ИНГРЕДИЕНТЫ ====================

-- Рецепты
CREATE TABLE Recipes (
    id_recipe SERIAL PRIMARY KEY,
    title VARCHAR(300) NOT NULL,
    description TEXT NOT NULL, -- исправлено опечатку dessciption → description
    id_cooking_time INTEGER NOT NULL REFERENCES CookingTime(id_cooking_time),
    id_difficulty INTEGER NOT NULL REFERENCES Difficulty(id_difficulty),
    id_calorie_content INTEGER NOT NULL REFERENCES CalorieContent(id_calorie_content),
    image_url VARCHAR(500),
    instructions TEXT, -- пошаговые инструкции
    servings INTEGER DEFAULT 2,
    rating DECIMAL(3,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Продукты в рецептах (связь многие-ко-многим)
CREATE TABLE RecipeIngredients (
    id_recipe_ingredient SERIAL PRIMARY KEY,
    id_recipe INTEGER NOT NULL REFERENCES Recipes(id_recipe) ON DELETE CASCADE,
    id_product INTEGER NOT NULL REFERENCES Products(id_product) ON DELETE CASCADE,
    quantity DECIMAL(8,2),
    unit VARCHAR(50),
    is_optional BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    
    UNIQUE(id_recipe, id_product) -- чтобы один продукт не повторялся в рецепте
);

-- ==================== ИСТОРИЯ И ВЗАИМОДЕЙСТВИЯ ====================

-- История просмотров и приготовлений
CREATE TABLE UserHistory (
    id_history SERIAL PRIMARY KEY,
    id_user INTEGER NOT NULL REFERENCES Users(id_user) ON DELETE CASCADE,
    id_recipe INTEGER NOT NULL REFERENCES Recipes(id_recipe) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL, -- 'viewed', 'cooked', 'saved', 'rated'
    rating_value INTEGER CHECK (rating_value >= 1 AND rating_value <= 5),
    cooked_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== ИНДЕКСЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ ====================

-- Индексы для пользователей
CREATE INDEX idx_users_email ON Users(email);
CREATE INDEX idx_users_login ON Users(login);
CREATE INDEX idx_users_created_at ON Users(created_at);

-- Индексы для продуктов
CREATE INDEX idx_products_title ON Products(title);
CREATE INDEX idx_products_category ON Products(category);

-- Индексы для рецептов
CREATE INDEX idx_recipes_title ON Recipes(title);
CREATE INDEX idx_recipes_cooking_time ON Recipes(id_cooking_time);
CREATE INDEX idx_recipes_difficulty ON Recipes(id_difficulty);
CREATE INDEX idx_recipes_calorie ON Recipes(id_calorie_content);
CREATE INDEX idx_recipes_rating ON Recipes(rating DESC);
CREATE INDEX idx_recipes_created_at ON Recipes(created_at);

-- Индексы для связей многие-ко-многим
CREATE INDEX idx_recipe_ingredients_recipe ON RecipeIngredients(id_recipe);
CREATE INDEX idx_recipe_ingredients_product ON RecipeIngredients(id_product);
CREATE INDEX idx_recipe_ingredients_composite ON RecipeIngredients(id_recipe, id_product);

-- Индексы для предпочтений
CREATE INDEX idx_user_preferences_user ON UserPreferences(id_user);
CREATE INDEX idx_user_preferences_type ON UserPreferences(preference_type);
CREATE INDEX idx_user_preferences_product ON UserPreferences(id_product) WHERE id_product IS NOT NULL;

-- Индексы для истории
CREATE INDEX idx_user_history_user ON UserHistory(id_user);
CREATE INDEX idx_user_history_recipe ON UserHistory(id_recipe);
CREATE INDEX idx_user_history_action ON UserHistory(action_type);
CREATE INDEX idx_user_history_date ON UserHistory(created_at DESC);
CREATE INDEX idx_user_history_user_recipe ON UserHistory(id_user, id_recipe);

-- ==================== ТРИГГЕРЫ ====================

-- Автоматическое обновление updated_at в рецептах
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_recipes_updated_at 
    BEFORE UPDATE ON Recipes 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =================═══ ВСТАВКА ТЕСТОВЫХ ДАННЫХ ====================

-- Заполняем справочники
INSERT INTO CookingTime (title, min_minutes, max_minutes) VALUES
('Быстро (до 15 мин)', 5, 15),
('Среднее (15-30 мин)', 15, 30),
('Долго (30+ мин)', 30, 120);

INSERT INTO Difficulty (title, description) VALUES
('Легко', 'Для начинающих'),
('Средне', 'Требует некоторого опыта'),
('Сложно', 'Для опытных кулинаров');

INSERT INTO CalorieContent (title, min_calories, max_calories) VALUES
('Низкокалорийные', 100, 300),
('Средние', 300, 600), 
('Высококалорийные', 600, 1000);

-- Добавляем тестовые продукты
INSERT INTO Products (title, category) VALUES
('Помидор', 'Овощи'),
('Курица', 'Мясо'),
('Лук', 'Овощи'),
('Рис', 'Крупы'),
('Сыр', 'Молочные продукты');
