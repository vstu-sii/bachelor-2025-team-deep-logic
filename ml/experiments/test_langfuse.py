import time
import json
import csv
import os

from ml.experiments.ab_test_langfuse import cook_from_image
from ml.service.baseline import LLaVAVision, MistralText

# Инициализация моделей
vlm = LLaVAVision()
llm = MistralText()

def safe_float(value):
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None

def run_experiments(
    n_runs: int = 1,
    image_dir: str = "C:\\Users\\Наталья\\Desktop\\lab4-AiEngineer-infrastructure\\data\\processed_images",
    reference_file: str = "C:\\Users\\Наталья\\Desktop\\lab4-AiEngineer-infrastructure\\ml\\experiments\\reference_ingredients.json"
):
    # Загружаем эталонные ингредиенты
    with open(reference_file, "r", encoding="utf-8") as f:
        reference_map = {
            os.path.basename(entry["image_path"]): entry["reference_ingredients"]
            for entry in json.load(f)
        }

    results = []

    # Собираем список изображений
    image_files = [
        os.path.join(image_dir, f)
        for f in os.listdir(image_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not image_files:
        print("⚠️ В папке нет изображений")
        return

    run_counter = 1
    for i in range(n_runs):  # внешний цикл по числу прогонов
        for image_path in image_files:  # внутренний цикл по картинкам
            image_name = os.path.basename(image_path)
            reference_ingredients = reference_map.get(image_name, [])

            print(f"\n=== Запуск {run_counter} для {image_name} ===")
            result = cook_from_image(
                image_path=image_path,
                vlm=vlm,
                llm=llm,
                dietary="нет",
                feedback="нет",
                preferred_calorie_level="низкокалорийное",
                preferred_cooking_time="быстро",
                preferred_difficulty="легко",
                existing_recipes="нет",
                reference_ingredients=reference_ingredients
            )
            run_counter += 1

            if not result:
                print("WARN: cook_from_image вернул пустой результат")
                continue

            print(json.dumps(result, ensure_ascii=False, indent=2))

            usage = result.get("usage", {}) or {}
            llm_checks = result.get("llm_checks", {}) or {}
            llm_input = result.get("input", {}) or {}

            vlm_f1 = safe_float(llm_input.get("vlm_f1"))
            vlm_excess_ratio = safe_float(llm_input.get("vlm_excess_ratio"))

            results.append({
                "image": image_name,
                "llm_variant": result.get("llm_variant"),
                "prompt_variant": llm_input.get("prompt_variant"),
                "vlm_duration_sec": result.get("vlm_duration_sec"),
                "duration_sec": result.get("duration_sec"),
                "tokens": usage.get("total_tokens"),
                "cost": result.get("cost"),
                "vlm_f1": vlm_f1,
                "vlm_excess_ratio": vlm_excess_ratio,
                "dietary_ok": llm_checks.get("dietary_ok"),
                "difficulty_ok": llm_checks.get("difficulty_ok"),
                "time_ok": llm_checks.get("time_ok"),
                "calories_ok": llm_checks.get("calories_ok")
            })

    if results:
        results.sort(key=lambda r: r["image"])

        with open("ab_test_results.txt", "w", encoding="utf-8") as f:
            for row in results:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        print("\n✅ Результат сохранен в ab_test_results.txt")
    else:
        print("\n⚠️ Нет результатов для сохранения")

if __name__ == "__main__":
    run_experiments(n_runs=5)
