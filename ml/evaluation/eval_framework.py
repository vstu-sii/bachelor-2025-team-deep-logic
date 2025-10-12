import json
import os
from ml.models.baseline import Gemma3Text, LLaVAVision

def compute_precision_recall_f1(predicted, reference):
    predicted_set = set([p.lower() for p in predicted])
    reference_set = set([r.lower() for r in reference])

    tp = len(predicted_set & reference_set)
    fp = len(predicted_set - reference_set)
    fn = len(reference_set - predicted_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return precision, recall, f1

def compute_coverage(predicted, reference):
    reference_set = set([r.lower() for r in reference])
    predicted_set = set([p.lower() for p in predicted])
    covered = reference_set & predicted_set
    coverage = len(covered) / len(reference_set) if reference_set else 0.0
    return coverage

def compute_excess(predicted, reference):
    reference_set = set([r.lower() for r in reference])
    predicted_set = set([p.lower() for p in predicted])
    excess = predicted_set - reference_set
    excess_ratio = len(excess) / len(predicted_set) if predicted_set else 0.0
    return excess_ratio

def extract_diversity_levels(recipes):
    difficulties = set()
    for recipe in recipes:
        difficulties.add(recipe.get("difficulty"))
    return {
        "difficulty_levels": list(difficulties),
    }

def evaluate_vlm(eval_file="C:/Users/Наталья/Desktop/lab2-AI Engineer-deliverables/ml/evaluation/vlm_eval_cases.json"):
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    vlm = LLaVAVision()
    llm = Gemma3Text()

    results = []
    precision_scores, recall_scores, f1_scores = [], [], []
    coverage_scores, excess_scores = [], []

    for case in eval_cases:
        image_path = case["image_path"]
        reference = case["reference_ingredients"]

        print(f"\n📷 Обработка изображения: {image_path}")
        print(f"🎯 Эталонные ингредиенты: {reference}")

        # Шаг 1: распознавание ингредиентов
        pred = vlm.infer(image_path)
        predicted = [ing["name"] if isinstance(ing, dict) else ing
                     for ing in pred.get("ingredients", [])]

        # Шаг 2: генерация рецептов
        llm_result = llm.generate_recipe(
            ingredients=pred.get("ingredients", []),
            dietary=None,
            feedback=None
        )

        recipes = llm_result
        diversity = extract_diversity_levels(recipes)

        # Метрики по ингредиентам
        precision, recall, f1 = compute_precision_recall_f1(predicted, reference)
        coverage = compute_coverage(predicted, reference)
        excess = compute_excess(predicted, reference)

        precision_scores.append(precision)
        recall_scores.append(recall)
        f1_scores.append(f1)
        coverage_scores.append(coverage)
        excess_scores.append(excess)

        results.append({
            "image": os.path.basename(image_path),
            "reference": reference,
            "predicted": predicted,
            "Precision": round(precision, 3),
            "Recall": round(recall, 3),
            "F1": round(f1, 3),
            "Coverage": round(coverage, 3),
            "Excess": round(excess, 3),
            "Diversity": diversity
        })

    avg_precision = sum(precision_scores) / len(precision_scores)
    avg_recall = sum(recall_scores) / len(recall_scores)
    avg_f1 = sum(f1_scores) / len(f1_scores)
    avg_coverage = sum(coverage_scores) / len(coverage_scores)
    avg_excess = sum(excess_scores) / len(excess_scores)

    return {
        "results": results,
        "avg_precision": round(avg_precision, 3),
        "avg_recall": round(avg_recall, 3),
        "avg_f1": round(avg_f1, 3),
        "avg_coverage": round(avg_coverage, 3),
        "avg_excess": round(avg_excess, 3)
    }

if __name__ == "__main__":
    report = evaluate_vlm()
    print(json.dumps(report, ensure_ascii=False, indent=2))
