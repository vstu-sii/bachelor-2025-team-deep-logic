
## 🔐 Аутентификация и авторизация

### 📋 Получить форму авторизации
```http
GET /
Описание: Возвращает HTML страницу для входа в систему

Параметры: Нет

Заголовки:

Content-Type: text/html
```
Пример запроса:

```http
GET / HTTP/1.1
Host: 127.0.0.1:8000
```
Успешный ответ:
```
html
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
    <title>Авторизация - AI Chef</title>
</head>
<body>
    <form action="/auth" method="post">
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Войти</button>
    </form>
    <a href="/registration">Регистрация</a>
</body>
</html>
```
Коды ответов:

200 - Успешно возвращена форма авторизации

### 🔑 Авторизация пользователя
```http
POST /auth
Content-Type: application/x-www-form-urlencoded
```

Описание: Выполняет аутентификацию пользователя и устанавливает сессионную cookie

Параметры формы:

email (string, required) - Email пользователя

password (string, required) - Пароль пользователя

Заголовки:

Content-Type: application/x-www-form-urlencoded
```
Пример запроса:
http
POST /auth HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/x-www-form-urlencoded
Content-Length: 45

email=user%40example.com&password=mysecretpassword
```
Успешный ответ:

```http
HTTP/1.1 303 See Other
Location: /upload
Set-Cookie: session=eyJpZF91c2VyIjoxMjN9; HttpOnly; Path=/; Max-Age=3600
```
Ошибка аутентификации:

```html
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<body>
    <div class="error">Неверный email или пароль</div>
    <form action="/auth" method="post">
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Войти</button>
    </form>
</body>
</html>
```
Коды ответов:

303 - Успешная авторизация, redirect на /upload

200 - Ошибка аутентификации, форма с сообщением об ошибке

### 📝 Получить форму регистрации
```http
GET /registration
Описание: Возвращает HTML страницу для регистрации нового пользователя

Параметры: Нет

Заголовки:

Content-Type: text/html
```
Пример запроса:

```http
GET /registration HTTP/1.1
Host: 127.0.0.1:8000
```
Успешный ответ:

```html
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
    <title>Регистрация - AI Chef</title>
</head>
<body>
    <form action="/reg" method="post">
        <input type="text" name="name" placeholder="Имя" required>
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Зарегистрироваться</button>
    </form>
    <a href="/">Войти</a>
</body>
</html>
```
Коды ответов:

200 - Успешно возвращена форма регистрации

### 👤 Регистрация нового пользователя
```http
POST /reg
Content-Type: application/x-www-form-urlencoded
```
Описание: Создает нового пользователя и выполняет автоматическую авторизацию

Параметры формы:

name (string, required) - Имя пользователя (2-50 символов)

email (string, required) - Email для входа (валидный email)

password (string, required) - Пароль (минимум 6 символов)

Заголовки:

Content-Type: application/x-www-form-urlencoded
```
Пример запроса:

http
POST /reg HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/x-www-form-urlencoded
Content-Length: 67

name=Ivan%20Ivanov&email=ivan%40example.com&password=securepass123
```
Успешный ответ:

```http
HTTP/1.1 303 See Other
Location: /upload
Set-Cookie: session=eyJpZF91c2VyIjoxMjN9; HttpOnly; Path=/; Max-Age=3600
```
Ошибка регистрации (пользователь существует):

```html
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<body>
    <div class="error">Пользователь с таким email уже существует</div>
    <form action="/reg" method="post">
        <input type="text" name="name" placeholder="Имя" required>
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Зарегистрироваться</button>
    </form>
</body>
</html>
```
Ошибка регистрации (невалидные данные):

```html
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<body>
    <div class="error">Пароль должен содержать минимум 6 символов</div>
    <form action="/reg" method="post">
        <input type="text" name="name" placeholder="Имя" required>
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Зарегистрироваться</button>
    </form>
</body>
</html>
```
Коды ответов:

303 - Успешная регистрация, redirect на /upload

200 - Ошибка регистрации, форма с сообщением об ошибке

---

## 🖼️ Анализ изображений
### 📤 Загрузить изображение для анализа
```http
POST /test-vlm
Content-Type: multipart/form-data
```
Описание: Загружает изображение для анализа и перенаправляет на страницу результатов

Параметры формы:

file (file, required) - Изображение в формате JPG, JPEG или PNG (максимальный размер 10MB)

Заголовки:

Content-Type: multipart/form-data
```
Пример запроса:

http
POST /test-vlm HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Length: 10240

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="food.jpg"
Content-Type: image/jpeg

(binary image data)
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```
Успешный ответ:

```http
HTTP/1.1 303 See Other
Location: /results/food.jpg
```
Ошибка (неверный формат файла):
```html
HTTP/1.1 400 Bad Request
Content-Type: text/html

<!DOCTYPE html>
<html>
<body>
    <div class="error">Ошибка загрузки файла: неверный формат изображения. Поддерживаются только JPG, JPEG, PNG</div>
</body>
</html>
Ошибка (файл слишком большой):
```
```html
HTTP/1.1 400 Bad Request
Content-Type: text/html

<!DOCTYPE html>
<html>
<body>
    <div class="error">Ошибка загрузки файла: размер файла превышает 10MB</div>
</body>
</html>
```
Коды ответов:

303 - Успешная загрузка, redirect на страницу результатов

400 - Ошибка загрузки файла

401 - Пользователь не авторизован

### 🚀 Начать асинхронную обработку изображения
```http
POST /start-processing
Content-Type: multipart/form-data
```
Описание: Начинает асинхронную обработку изображения и возвращает ID задачи для отслеживания статуса

Параметры формы:

file (file, required) - Изображение для анализа (JPG, JPEG, PNG, макс. 10MB)

Заголовки:

Content-Type: multipart/form-data
```
Пример запроса:

http
POST /start-processing HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Length: 8192

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="ingredients.jpg"
Content-Type: image/jpeg

(binary image data)
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```
Успешный ответ:

```http
HTTP/1.1 200 OK
Content-Type: application/json
```
```json
{
  "task_id": "3192e270-1b58-4c35-8fdb-812b9ccccb58",
  "status": "queued",
  "message": "Задача поставлена в очередь на обработку",
  "estimated_time": 30,
  "created_at": "2024-01-15T10:30:00Z"
}
```

Ошибка (неверный формат файла):

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json
```
```json
{
  "detail": "Неверный формат файла. Поддерживаются только JPG, JPEG, PNG",
  "error_code": "INVALID_IMAGE_FORMAT"
}
```
Ошибка (файл слишком большой):

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json
```
```json
{
  "detail": "Размер файла превышает максимально допустимый размер 10MB",
  "error_code": "FILE_TOO_LARGE",
  "max_size_mb": 10,
  "actual_size_mb": 15.2
}
```
Коды ответов:

200 - Задача успешно создана

400 - Ошибка валидации файла

401 - Пользователь не авторизован

500 - Внутренняя ошибка сервера

### 📊 Получить результат обработки изображения
```http
GET /get-result/{task_id}
```
Описание: Получает статус и результаты обработки изображения по ID задачи. Поддерживает длительное ожидание завершения обработки.

Параметры пути:

task_id (string, required) - UUID задачи, полученный из /start-processing

Параметры query:

timeout (integer, optional) - Таймаут ожидания в секундах (по умолчанию: 30)

Заголовки:

Content-Type: application/json

Пример запроса:

```http
GET /get-result/3192e270-1b58-4c35-8fdb-812b9ccccb58 HTTP/1.1
Host: 127.0.0.1:8000
```
Ответ - обработка завершена:
```http
HTTP/1.1 200 OK
Content-Type: application/json
```
```json
{
  "status": "done",
  "ingredients": ["курица", "брокколи", "сыр", "чеснок", "оливковое масло"],
  "raw_ingredients": {
    "ingredients": [
      {
        "name": "курица",
        "amount": "300г",
        "confidence": 0.95,
        "bounding_box": [0.1, 0.2, 0.3, 0.4]
      },
      {
        "name": "брокколи", 
        "amount": "200г",
        "confidence": 0.88,
        "bounding_box": [0.5, 0.6, 0.7, 0.8]
      }
    ],
    "total_ingredients": 5,
    "detection_confidence": 0.89
  },
  "forbidden_products_removed": ["орехи", "молоко"],
  "filtered_ingredients": ["курица", "брокколи", "сыр", "чеснок", "оливковое масло"],
  "task_id": "3192e270-1b58-4c35-8fdb-812b9ccccb58",
  "processing_time": 12.5,
  "completed_at": "2024-01-15T10:30:15Z"
}
```
Ответ - обработка в процессе:

```http
HTTP/1.1 200 OK
Content-Type: application/json
```
```json
{
  "status": "processing",
  "progress": 65,
  "message": "Анализ изображения...",
  "task_id": "3192e270-1b58-4c35-8fdb-812b9ccccb58",
  "estimated_remaining_time": 8,
  "started_at": "2024-01-15T10:30:05Z"
}
```
Ответ - задача в очереди:

```http
HTTP/1.1 200 OK
Content-Type: application/json
```
```json
{
  "status": "queued",
  "position_in_queue": 2,
  "message": "Задача в очереди на обработку",
  "task_id": "3192e270-1b58-4c35-8fdb-812b9ccccb58",
  "queued_at": "2024-01-15T10:30:00Z"
}
```
Ошибка - задача не найдена:

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
```
```json
{
  "detail": "Задача с ID 3192e270-1b58-4c35-8fdb-812b9ccccb58 не найдена",
  "error_code": "TASK_NOT_FOUND"
}
```
Ошибка - доступ запрещен:

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json
```
```json
{
  "detail": "Доступ к задаче запрещен",
  "error_code": "ACCESS_DENIED"
}
```
Коды ответов:

200 - Успешный запрос (разные статусы обработки)

404 - Задача не найдена

403 - Доступ к задаче запрещен

401 - Пользователь не авторизован

