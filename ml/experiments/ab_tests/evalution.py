import sqlite3
import json
from collections import defaultdict
from pathlib import Path
from scipy.stats import ttest_ind  # для расчёта p-value

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

    # prompt → user → {action → count}
    user_actions = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    try:
        cursor.execute("SELECT prompt_name, user_action, id_user FROM PromptUsage")
        rows = cursor.fetchall()

        for prompt_name, user_action, user_id in rows:
            action = user_action.strip()
            user_actions[prompt_name][user_id][action] += 1

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        con.close()

    results = {}
    user_scores = {}

    print("📊 Оценка промптов по действиям:")
    print("{:<10} {:>10} {:>10} {:>10} {:>12}".format("Промпт", "Баллы", "Действий", "Пользов.", "Норм.балл"))
    print("-" * 60)

    for prompt, users in user_actions.items():
        total_score = 0
        total_count = 0
        action_details = defaultdict(lambda: {"count": 0, "weight": 0, "score": 0})
        scores_per_user = []

        for user_id, actions in users.items():
            user_score = 0
            for action, count in actions.items():
                weight = ACTION_WEIGHTS.get(action, 0)
                score = weight * count
                user_score += score
                total_score += score
                total_count += count
                action_details[action]["count"] += count
                action_details[action]["weight"] = weight
                action_details[action]["score"] += score
            scores_per_user.append(user_score)

        user_count = len(users)
        normalized_score = round(total_score / user_count, 2) if user_count else 0

        print("{:<10} {:>10} {:>10} {:>10} {:>12}".format(
            prompt, round(total_score, 2), total_count, user_count, normalized_score
        ))

        results[prompt] = {
            "total_score": round(total_score, 2),
            "total_count": total_count,
            "user_count": user_count,
            "normalized_score": normalized_score,
            "actions": dict(action_details)
        }

        user_scores[prompt] = scores_per_user

    # 📌 Расчёт p-value между двумя промптами
    if len(user_scores) == 2:
        prompts = list(user_scores.keys())
        sample_a = user_scores[prompts[0]]
        sample_b = user_scores[prompts[1]]

        p_val = ttest_ind(sample_a, sample_b, equal_var=False).pvalue
        print(f"\n📌 p-value между {prompts[0]} и {prompts[1]}: {p_val:.4f}")
        results["p_value"] = {
            f"{prompts[0]} vs {prompts[1]}": round(p_val, 4)
        }

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ Результаты сохранены в {OUTPUT_PATH}")
    return results


# Запуск
evaluate_prompt_quality()
