

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

