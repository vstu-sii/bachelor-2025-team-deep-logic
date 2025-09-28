from fastapi import FastAPI, UploadFile, Form
from ml.models.baseline import Gemma3Text, LLaVAVision
import os

app = FastAPI()

vlm = LLaVAVision()
pipeline = Gemma3Text()


@app.post("/test-vlm")
async def test_vlm(file: UploadFile):
    """
    Проверка только LLaVAVision: извлекаем ингредиенты с фото.
    """
    path = f"C:/Users/Наталья/Desktop/lab2-AI Engineer-deliverables/data/processed_images/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())
    return vlm.infer(path)

@app.post("/cook-from-image")
async def generate_recipe(file: UploadFile, dietary: str = Form("нет")):
    """
    Полный пайплайн: сначала VLM, потом LLM.
    Параметр dietary можно задать на сайте (например, "vegetarian", "vegan", "безглютеновая").
    """
    path = f"C:/Users/Наталья/Desktop/lab2-AI Engineer-deliverables/data/processed_images/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())
    return pipeline.generate_recipe(path, dietary=dietary)
