import json

# Загружаем файл
with open("ab_test_results_calories_fixed.txt", "r", encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]

# --- VLM ---
vlm_a = [r for r in rows if r["prompt_variant"] == "vlm_prompt_a"]
vlm_b = [r for r in rows if r["prompt_variant"] == "vlm_prompt_b"]

avg_f1_a = sum(r["vlm_f1"] for r in vlm_a) / len(vlm_a)
avg_f1_b = sum(r["vlm_f1"] for r in vlm_b) / len(vlm_b)

avg_excess_a = sum(r["vlm_excess_ratio"] for r in vlm_a) / len(vlm_a)
avg_excess_b = sum(r["vlm_excess_ratio"] for r in vlm_b) / len(vlm_b)

avg_delay_a = sum(r["vlm_duration_sec"] for r in vlm_a) / len(vlm_a)
avg_delay_b = sum(r["vlm_duration_sec"] for r in vlm_b) / len(vlm_b)

# --- LLM ---
llm_a = [r for r in rows if r["llm_variant"] == "llm_prompt_a"]
llm_b = [r for r in rows if r["llm_variant"] == "llm_prompt_b"]

# фильтруем короткие ответы и минимальную цену
llm_a_filtered = [r for r in llm_a if r["tokens"] != 80 and r["cost"] != 0.00002]
llm_b_filtered = [r for r in llm_b if r["tokens"] != 80 and r["cost"] != 0.00002]

avg_tokens_a = sum(r["tokens"] for r in llm_a_filtered) / len(llm_a_filtered)
avg_tokens_b = sum(r["tokens"] for r in llm_b_filtered) / len(llm_b_filtered)

avg_cost_a = sum(r["cost"] for r in llm_a_filtered) / len(llm_a_filtered)
avg_cost_b = sum(r["cost"] for r in llm_b_filtered) / len(llm_b_filtered)

avg_duration_a = sum(r["duration_sec"] for r in llm_a_filtered) / len(llm_a_filtered)
avg_duration_b = sum(r["duration_sec"] for r in llm_b_filtered) / len(llm_b_filtered)

# проценты true для каждого флага
def percent_true(group, key):
    return sum(1 for r in group if r[key]) / len(group) * 100

perc_dietary_a = percent_true(llm_a, "dietary_ok")
perc_difficulty_a = percent_true(llm_a, "difficulty_ok")
perc_time_a = percent_true(llm_a, "time_ok")
perc_calories_a = percent_true(llm_a, "calories_ok")

perc_dietary_b = percent_true(llm_b, "dietary_ok")
perc_difficulty_b = percent_true(llm_b, "difficulty_ok")
perc_time_b = percent_true(llm_b, "time_ok")
perc_calories_b = percent_true(llm_b, "calories_ok")

# --- Итог ---
results = {
    "vlm_prompt_a": {
        "avg_f1": avg_f1_a,
        "avg_excess_ratio": avg_excess_a,
        "avg_delay_sec": avg_delay_a
    },
    "vlm_prompt_b": {
        "avg_f1": avg_f1_b,
        "avg_excess_ratio": avg_excess_b,
        "avg_delay_sec": avg_delay_b
    },
    "llm_prompt_a": {
        "avg_tokens": avg_tokens_a,
        "avg_cost": avg_cost_a,
        "avg_duration_sec": avg_duration_a,
        "perc_dietary_ok": perc_dietary_a,
        "perc_difficulty_ok": perc_difficulty_a,
        "perc_time_ok": perc_time_a,
        "perc_calories_ok": perc_calories_a
    },
    "llm_prompt_b": {
        "avg_tokens": avg_tokens_b,
        "avg_cost": avg_cost_b,
        "avg_duration_sec": avg_duration_b,
        "perc_dietary_ok": perc_dietary_b,
        "perc_difficulty_ok": perc_difficulty_b,
        "perc_time_ok": perc_time_b,
        "perc_calories_ok": perc_calories_b
    }
}

# Печать в консоль
print(json.dumps(results, indent=2, ensure_ascii=False))

# Запись в TXT в более читаемом виде
with open("analysis_results.txt", "w", encoding="utf-8") as out:
    for section, metrics in results.items():
        out.write(f"[{section}]\n")
        for key, value in metrics.items():
            out.write(f"{key}: {value}\n")
        out.write("\n")
