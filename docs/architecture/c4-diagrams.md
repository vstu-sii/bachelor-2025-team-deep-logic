# C4 Architecture

## Context
![Context](../generated/C4_context.png)

## Containers
![Containers](../generated/C4_container.png)

## Model Manager
![Model Manager](../generated/C4_component.png)

Интерфейсы компонентов Backend API

| Компонент | Эндпоинты / Методы | Входные данные | Выходные данные |
|-----------|--------------------|----------------|-----------------|
| **API Gateway [FastAPI Router]** | `/uploadPhoto`, `/getRecipes`, `/profile`, `/history`, `/review` | HTTP‑запросы от Flutter App (JSON, multipart/form-data) | JSON‑ответы (списки ингредиентов, рецептов, история, подтверждения) |
| **Photo Service [FastAPI Service]** | `analyzePhoto()` | Фото (binary/multipart) | Список ингредиентов |
| **Recipe Service [FastAPI Service]** | `generateRecipes(ingredients)` | Список ингредиентов (JSON) | Список рецептов (JSON) |
| **User Service [FastAPI Service]** | `register()`, `login()`, `updateProfile()` | Данные пользователя (JSON) | JWT‑токен, обновлённый профиль |
| **History Service [FastAPI Service]** | `saveHistory()`, `getHistory()` | Данные о запросах/рецептах | История пользователя (JSON) |
| **Notification Service [FastAPI Service]** | `sendNotification()` | Сообщение, ID пользователя | Подтверждение отправки |
| **DAL [Repository / ORM Layer]** | `saveUser()`, `getUser()`, `saveRecipe()`, `getHistory()` | SQL‑запросы через ORM | Данные из PostgreSQL |
| **VLM Connector [Adapter]** | `callVLM(photo)` | Фото | Список ингредиентов |
| **LLM Connector [Adapter]** | `callLLM(ingredients)` | Список ингредиентов | Сгенерированные рецепты |
| **Notification Connector [Adapter]** | `callNotificationService(message)` | Сообщение | Подтверждение от внешнего сервиса |
