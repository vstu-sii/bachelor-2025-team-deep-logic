from fastapi import FastAPI, UploadFile, Form, HTTPException
from ml.models.baseline import MistralText
from pathlib import Path
import uuid
import pika
import json
import subprocess
import logging
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="Baseline API",
    description="API для работы с VLM (распознавание ингредиентов) и LLM (генерация рецептов)",
    version="1.0"
)

pipeline = MistralText()
logging.basicConfig(level=logging.INFO)

# Запуск воркера при старте сервера
@app.on_event("startup")
def launch_worker():
    subprocess.Popen(["python", "-m", "backend.routers.worker"])

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
        connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        channel = connection.channel()
        channel.queue_declare(queue="ingredient_queue")
        message = {"task_id": task_id, "image_path": str(save_path)}
        channel.basic_publish(exchange="", routing_key="ingredient_queue", body=json.dumps(message))
        connection.close()
    except Exception as e:
        logging.error(f"Ошибка очереди: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка очереди: {e}")

    return {"task_id": task_id, "status": "queued"}

@app.get("/task-result/{task_id}", tags=["AI"], summary="Получить результат распознавания")
async def get_result(task_id: str):
    result_path = Path(f"./results/{task_id}.json")
    if not result_path.exists():
        return {"status": "processing"}

    with open(result_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    # если воркер сохранил ошибку
    if result.get("status") == "error":
        return {"status": "error", "error": result.get("error", "Неизвестная ошибка")}

    return {"status": "done", "ingredients": result.get("ingredients", [])}

@app.post("/cook-from-image/{task_id}", tags=["AI"], summary="Сгенерировать рецепт по ингредиентам")
async def generate_recipe(task_id: str, dietary: str = Form("нет"), user_feedback: str = Form("нет")):
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

    recipes = pipeline.generate_recipe(ingredients, dietary=dietary, feedback=user_feedback)

    if isinstance(recipes, dict) and "error" in recipes:
        logging.error(f"Ошибка генерации рецепта: {recipes}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации рецепта: {recipes['error']}")

    recipes_path = Path(f"./recipes/{task_id}_recipes.json")
    recipes_path.parent.mkdir(parents=True, exist_ok=True)
    with open(recipes_path, "w", encoding="utf-8") as f:
        json.dump(
            {"ingredients": ingredients, "recipes": recipes, "feedback_used": user_feedback},
            f,
            ensure_ascii=False,
            indent=2
        )

    return {
        "ingredients": ingredients,
        "recipes": recipes,
        "feedback_used": user_feedback,
        "saved_to": str(recipes_path)
    }
