import sqlite3
import json
from collections import defaultdict
from pathlib import Path

DB_PATH = "my_database.db"
OUTPUT_PATH = "./prompt_scores.json"

ACTION_WEIGHTS = {
    "Приготовил рецепт": 2.5,
    "Сохранение завершенных рецептов": 2,
    "Добавлен рецепт в избранное": 3,
    "Удален рецепт из избранного": -1.5,
}

def evaluate_prompt_quality():
    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Структура: prompt → {action → count}
    prompt_actions = defaultdict(lambda: defaultdict(int))

    try:
        cursor.execute("SELECT prompt_name, user_action FROM PromptUsage")
        rows = cursor.fetchall()

        for prompt_name, user_action in rows:
            action = user_action.strip()
            prompt_actions[prompt_name][action] += 1

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        con.close()

    results = {}

    # Подсчёт баллов
    print("📊 Оценка промптов по действиям:")
    print("{:<10} {:>10} {:>10}".format("Промпт", "Баллы", "Действий"))
    print("-" * 32)

    for prompt, actions in prompt_actions.items():
        total_score = 0
        total_count = 0
        action_details = {}

        for action, count in actions.items():
            weight = ACTION_WEIGHTS.get(action, 0)
            score = weight * count
            total_score += score
            total_count += count
            action_details[action] = {"count": count, "weight": weight, "score": score}

        print("{:<10} {:>10} {:>10}".format(prompt, round(total_score, 2), total_count))

        results[prompt] = {
            "total_score": round(total_score, 2),
            "total_count": total_count,
            "actions": action_details
        }

    # Сохраняем в JSON
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ Результаты сохранены в {OUTPUT_PATH}")
    return results


# Запуск
evaluate_prompt_quality()
