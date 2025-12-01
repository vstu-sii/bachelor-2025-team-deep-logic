import json
import uuid
import logging
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, Form, HTTPException
from dotenv import load_dotenv
from ml.models.baseline import MistralText
import aio_pika

load_dotenv()

app = FastAPI(
    title="Baseline API",
    description="API для работы с VLM (распознавание ингредиентов) и LLM (генерация рецептов)",
    version="1.0"
)

pipeline = MistralText()
logging.basicConfig(level=logging.INFO)

# глобальные переменные для RabbitMQ и воркера
rabbitmq_connection = None
rabbitmq_channel = None
worker_process = None


async def get_channel():
    """Ленивая инициализация канала RabbitMQ"""
    global rabbitmq_connection, rabbitmq_channel
    if rabbitmq_channel is None or rabbitmq_channel.is_closed:
        rabbitmq_connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
        rabbitmq_channel = await rabbitmq_connection.channel()
        await rabbitmq_channel.declare_queue("ingredient_queue", durable=True)
        logging.info("RabbitMQ channel reinitialized")
    return rabbitmq_channel


@app.on_event("startup")
async def startup_event():
    global worker_process
    # запуск воркера как отдельного процесса
    worker_process = subprocess.Popen(["python", "-m", "backend.routers.worker"])

    # инициализация клиента для Mistral
    await pipeline.init_client()

    # подключение к RabbitMQ
    await get_channel()
    logging.info("RabbitMQ connection established")


@app.on_event("shutdown")
async def shutdown_event():
    global worker_process
    if worker_process:
        worker_process.terminate()
        worker_process.wait()
        logging.info("Worker process terminated")

    await pipeline.close_client()
    if rabbitmq_connection:
        await rabbitmq_connection.close()
        logging.info("RabbitMQ connection closed")


@app.post("/test-vlm", tags=["AI"], summary="Распознать ингредиенты на фото")
async def test_vlm(file: UploadFile):
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением (jpg/png)")

    task_id = str(uuid.uuid4())
    save_path = Path(f"./data/processed_images/{task_id}_{file.filename}")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    try:
        channel = await get_channel()
        message = {"task_id": task_id, "image_path": str(save_path)}
        body = json.dumps(message).encode("utf-8")
        await channel.default_exchange.publish(
            aio_pika.Message(body, content_type="application/json"),
            routing_key="ingredient_queue"
        )
        logging.info(f"Message published to queue ingredient_queue: {message}")
    except Exception as e:
        logging.error(f"Ошибка публикации: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка публикации: {e}")

    return {"task_id": task_id, "status": "queued"}


@app.get("/task-result/{task_id}", tags=["AI"], summary="Получить результат распознавания")
async def get_result(task_id: str):
    result_path = Path(f"./results/{task_id}.json")
    if not result_path.exists():
        return {"status": "processing"}

    with open(result_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    if result.get("status") == "error":
        return {"status": "error", "error": result.get("error", "Неизвестная ошибка")}

    return {"status": "done", "ingredients": result.get("ingredients", [])}


@app.post("/cook-from-image/{task_id}", tags=["AI"], summary="Сгенерировать рецепт по ингредиентам")
async def generate_recipe(
    task_id: str,
    dietary: str = Form("нет"),
    user_feedback: str = Form("нет"),
    preferred_calorie_level: str = Form("нет"),
    preferred_cooking_time: str = Form("нет"),
    preferred_difficulty: str = Form("нет"),
    existing_recipes: str = Form("нет")
):
    result_path = Path(f"./results/{task_id}.json")
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Ингредиенты ещё не распознаны. Сначала вызовите /test-vlm.")

    with open(result_path, "r", encoding="utf-8") as f:
        vlm_result = json.load(f)

    if vlm_result.get("status") == "error":
        raise HTTPException(status_code=500, detail=f"Ошибка VLM: {vlm_result.get('error')}")

    ingredients = vlm_result.get("ingredients", [])
    if not ingredients:
        raise HTTPException(status_code=400, detail="Нет ингредиентов для генерации рецепта")

    # нормализация и валидация preferred_difficulty
    allowed_difficulties = {"легко", "средне", "сложно", "нет", ""}
    pref_diff = (preferred_difficulty or "нет").strip().lower()
    if pref_diff not in allowed_difficulties:
        raise HTTPException(status_code=400, detail=f"Неверное значение preferred_difficulty: {preferred_difficulty}. Допустимо: легко, средне, сложно, нет")

    preferred_difficulty_param = None if pref_diff in ("нет", "") else pref_diff

    recipes = await pipeline.generate_recipe(
        ingredients,
        dietary=dietary,
        existing=existing_recipes,
        feedback=user_feedback,
        preferred_calorie_level=preferred_calorie_level,
        preferred_cooking_time=preferred_cooking_time,
        preferred_difficulty=preferred_difficulty_param
    )

    if isinstance(recipes, dict) and "error" in recipes:
        logging.error(f"Ошибка генерации рецепта: {recipes}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации рецепта: {recipes['error']}")

    recipes_path = Path(f"./recipes/{task_id}_recipes.json")
    recipes_path.parent.mkdir(parents=True, exist_ok=True)
    with open(recipes_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ingredients": ingredients,
                "recipes": recipes,
                "feedback_used": user_feedback,
                "preferred_calorie_level": preferred_calorie_level,
                "preferred_cooking_time": preferred_cooking_time,
                "preferred_difficulty": preferred_difficulty_param,
                "excluded_recipes": existing_recipes
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    return {
        "ingredients": ingredients,
        "recipes": recipes,
        "feedback_used": user_feedback,
        "preferred_calorie_level": preferred_calorie_level,
        "preferred_cooking_time": preferred_cooking_time,
        "preferred_difficulty": preferred_difficulty_param,
        "excluded_recipes": existing_recipes,
        "saved_to": str(recipes_path)
    }
