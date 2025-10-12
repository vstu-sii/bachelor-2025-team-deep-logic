from fastapi import FastAPI, UploadFile, Form
from ml.models.baseline import Gemma3Text, LLaVAVision

app = FastAPI()

vlm = LLaVAVision()
pipeline = Gemma3Text()


@app.post("/test-vlm")
async def test_vlm(file: UploadFile):
    """Проверка только VLM: извлекаем ингредиенты с фото (на русском)."""
    path = f"C:/Users/Наталья/Desktop/lab2-AI Engineer-deliverables/data/processed_images/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())

    vlm_result = vlm.infer(path)
    if "error" in vlm_result:
        return vlm_result

    # В baseline.py теперь ingredients уже на русском
    ingredients = vlm_result.get("ingredients", [])

    return {
        "ingredients": ingredients
    }


@app.post("/cook-from-image")
async def generate_recipe(
    file: UploadFile,
    dietary: str = Form("нет"),
    user_feedback: str = Form("нет")
):
    """Полный пайплайн: сначала VLM (ингредиенты на русском), потом LLM (рецепты с учётом фидбека)."""
    path = f"C:/Users/Наталья/Desktop/lab2-AI Engineer-deliverables/data/processed_images/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())

    vlm_result = vlm.infer(path)
    if "error" in vlm_result:
        return vlm_result

    # Берём уже переведённый список (на русском)
    ingredients = vlm_result.get("ingredients", [])

    recipes = pipeline.generate_recipe(
        ingredients,
        dietary=dietary,
        feedback=user_feedback
    )

    return {
        "ingredients": ingredients,
        "recipes": recipes,
        "feedback_used": user_feedback
    }

