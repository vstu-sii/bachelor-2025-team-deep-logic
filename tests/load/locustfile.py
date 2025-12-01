from locust import HttpUser, task, between, events
import os
import random
import time
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

IMAGE_DIR = r"C:\Users\Наталья\Desktop\lab4-AiEngineer-infrastructure\data\processed_images"
MAX_ITERATIONS = 1

os.makedirs("reports", exist_ok=True)
os.makedirs("results", exist_ok=True)

class FullPipelineUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.iterations = 0

    @task
    def full_pipeline(self):
        if self.iterations >= MAX_ITERATIONS:
            self.environment.runner.quit()
            return

        self.iterations += 1
        image_files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if not image_files:
            return

        image_path = os.path.join(IMAGE_DIR, random.choice(image_files))
        with open(image_path, "rb") as image_file:
            files = {"file": (os.path.basename(image_path), image_file, "image/jpeg")}
            response = self.client.post("/test-vlm", files=files)

        if response.status_code != 200 or "task_id" not in response.json():
            return

        task_id = response.json()["task_id"]
        logging.info(f"[{task_id}] Задача поставлена в очередь")

        # 🔹 Ожидание результата VLM
        result_data = None
        for attempt in range(1000):  # до 100 минут
            result = self.client.get(f"/task-result/{task_id}")
            if result.status_code == 200:
                result_json = result.json()
                if result_json.get("status") == "done":
                    result_data = result_json
                    logging.info(f"[{task_id}] Распознавание завершено")
                    break
                elif result_json.get("status") == "error":
                    logging.error(f"[{task_id}] Ошибка VLM: {result_json.get('error')}")
                    return
            time.sleep(10)

        if not result_data:
            logging.warning(f"[{task_id}] Распознавание не завершено — рецепт не запускается")
            return

        # 🔹 Генерация рецепта сразу после VLM
        form_data = {
            "dietary": "нет",
            "user_feedback": "нет",
            "preferred_calorie_level": "нет",
            "preferred_cooking_time": "нет",
            "preferred_difficulty": "нет",
            "existing_recipes": "нет"
        }

        cook_response = self.client.post(f"/cook-from-image/{task_id}", data=form_data)
        if cook_response.status_code != 200:
            logging.error(f"[{task_id}] Ошибка генерации рецепта: {cook_response.text}")
            return

        cook_json = cook_response.json()
        if cook_json.get("status") == "done":
            result_path = f"results/{task_id}_recipe.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(cook_json, f, ensure_ascii=False, indent=2)
            logging.info(f"[{task_id}] Рецепт сохранён в {result_path}")
        else:
            # 🔁 Ожидание готовности рецепта
            recipe_data = None
            for attempt in range(1000):  # до 20 минут
                result = self.client.get(f"/recipe-result/{task_id}")
                if result.status_code == 200:
                    result_json = result.json()
                    if result_json.get("status") == "done":
                        recipe_data = result_json
                        break
                    elif result_json.get("status") == "error":
                        logging.error(f"[{task_id}] Ошибка рецепта: {result_json.get('error')}")
                        return
                elif result.status_code == 404:
                    logging.warning(f"[{task_id}] Рецепт ещё не найден — повтор через 20 сек")
                time.sleep(5)

            if recipe_data:
                result_path = f"results/{task_id}_recipe.json"
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump(recipe_data, f, ensure_ascii=False, indent=2)
                logging.info(f"[{task_id}] Рецепт сохранён в {result_path}")
            else:
                logging.warning(f"[{task_id}] Рецепт не был готов в отведённое время")


@events.quitting.add_listener
def generate_report(environment, **kwargs):
    stats = environment.stats
    summary_path = "reports/summary.txt"

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("📊 Итоговый отчёт Locust\n\n")
        total = stats.total
        f.write(f"Запросов: {total.num_requests}\n")
        f.write(f"Ошибок: {total.num_failures}\n")
        f.write(f"Средняя задержка: {total.avg_response_time:.2f} ms\n")
        f.write(f"Максимальная задержка: {total.max_response_time:.2f} ms\n")
        f.write(f"RPS: {total.total_rps:.2f}\n")
        f.write(f"95-й перцентиль: {total.get_response_time_percentile(0.95):.2f} ms\n")
        f.write(f"99-й перцентиль: {total.get_response_time_percentile(0.99):.2f} ms\n\n")
        f.write("=== Detailed stats ===\n")
        f.write(stats.report_stats())
        f.write("\n\n=== Error report ===\n")
        f.write(stats.report_errors())

    print(f"\n✅ Полный отчёт сохранён: {summary_path}")
