## ⚙️ Установка и запуск

### План запуска
1. Запустить **nginx сервер** (reverse proxy).  
2. Запустить **клиентский сервер** из директории `backend`:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   uvicorn backend.routers.ai:app --reload --host 127.0.0.1 --port 8001
Дополнительно включаются Ollama и RabbitMQ.
Фронтенд запускается как статический HTML из папки public
