import json
import os
import time
from ml.models.baseline import LLaVAVision

def compute_precision_recall_f1(predicted, reference):
    predicted_set = set([p.lower() for p in predicted])
    reference_set = set([r.lower() for r in reference])

    tp = len(predicted_set & reference_set)
    fp = len(predicted_set - reference_set)
    fn = len(reference_set - predicted_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return f1

def compute_excess(predicted, reference):
    reference_set = set([r.lower() for r in reference])
    predicted_set = set([p.lower() for p in predicted])
    excess = predicted_set - reference_set
    excess_ratio = len(excess) / len(predicted_set) if predicted_set else 0.0
    return excess_ratio

def evaluate_vlm(eval_file="ml/evaluation/vlm_eval_cases.json", report_file="report.txt"):
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    vlm = LLaVAVision()

    results = []
    f1_scores, excess_scores = [], []

    for idx, case in enumerate(eval_cases, start=1):
        image_path = case["image_path"]
        reference = case["reference_ingredients"]

        # Вывод прогресса на экран
        print(f"\n▶️ Тест #{idx}: {os.path.basename(image_path)}")
        print(f"   Эталонные ингредиенты: {reference}")

        start = time.time()
        pred = vlm.infer(image_path)
        latency = time.time() - start

        predicted = [ing["name"] if isinstance(ing, dict) else ing
                     for ing in pred.get("ingredients", [])]

        print(f"   Распознанные ингредиенты: {predicted}")

        f1 = compute_precision_recall_f1(predicted, reference)
        excess = compute_excess(predicted, reference)

        print(f"   F1: {f1:.3f}, Excess: {excess:.3f}, Latency: {latency:.2f} сек")

        f1_scores.append(f1)
        excess_scores.append(excess)

        results.append({
            "id": idx,
            "image": os.path.basename(image_path),
            "reference": reference,
            "predicted": predicted,
            "F1": round(f1, 3),
            "Excess": round(excess, 3)
        })

    avg_f1 = round(sum(f1_scores) / len(f1_scores), 3)
    avg_excess = round(sum(excess_scores) / len(excess_scores), 3)

    # Формируем текстовый отчёт
    lines = []
    for r in results:
        lines.append(f"Тест #{r['id']} ({r['image']})")
        lines.append("  Эталонные ингредиенты:")
        for item in r["reference"]:
            lines.append(f"    - {item}")
        lines.append("  Распознанные ингредиенты:")
        for item in r["predicted"]:
            lines.append(f"    - {item}")
        lines.append(f"  F1: {r['F1']}")
        lines.append(f"  Excess: {r['Excess']}")
        lines.append("")

    lines.append("📊 Сводка по всем тестам")
    lines.append(f"  Средний F1: {avg_f1}")
    lines.append(f"  Средний Excess: {avg_excess}")

    # Сохраняем в файл
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {
        "results": results,
        "avg_f1": avg_f1,
        "avg_excess": avg_excess
    }

if __name__ == "__main__":
    report = evaluate_vlm()
    print("\n✅ Отчёт сохранён в report.txt")
