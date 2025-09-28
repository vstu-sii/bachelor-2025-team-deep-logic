import json
import os
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge import Rouge
from ml.models.baseline import LLaVAVision

def compute_precision_recall_f1(predicted, reference):
    """Вычисляем precision, recall, F1 для списков ингредиентов"""
    predicted_set = set(predicted)
    reference_set = set(reference)

    tp = len(predicted_set & reference_set)  # True Positives
    fp = len(predicted_set - reference_set)  # False Positives
    fn = len(reference_set - predicted_set)  # False Negatives

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return precision, recall, f1


def evaluate_vlm(eval_file="C:/Users/Наталья/Desktop/lab2-AI Engineer-deliverables/ml/evaluation/vlm_eval_cases.json"):
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    vlm = LLaVAVision()
    rouge = Rouge()
    smooth = SmoothingFunction().method1

    results = []
    bleu_scores, rouge_scores = [], []
    precision_scores, recall_scores, f1_scores = [], [], []

    for case in eval_cases:
        image_path = case["image_path"]
        reference = case["reference_ingredients"]

        # предсказание модели
        pred = vlm.infer(image_path)
        predicted = [ing["name"] if isinstance(ing, dict) else ing
                     for ing in pred.get("ingredients", [])]

        # BLEU
        bleu = sentence_bleu([reference], predicted, smoothing_function=smooth)
        bleu_scores.append(bleu)

        # ROUGE-L
        try:
            rouge_score = rouge.get_scores(" ".join(predicted), " ".join(reference))
            rouge_l = rouge_score[0]["rouge-l"]["f"]
        except Exception:
            rouge_l = 0.0
        rouge_scores.append(rouge_l)

        # Precision / Recall / F1
        precision, recall, f1 = compute_precision_recall_f1(predicted, reference)
        precision_scores.append(precision)
        recall_scores.append(recall)
        f1_scores.append(f1)

        results.append({
            "image": os.path.basename(image_path),
            "reference": reference,
            "predicted": predicted,
            "BLEU": round(bleu, 3),
            "ROUGE-L": round(rouge_l, 3),
            "Precision": round(precision, 3),
            "Recall": round(recall, 3),
            "F1": round(f1, 3),
        })

    # агрегированные метрики
    avg_bleu = sum(bleu_scores) / len(bleu_scores)
    avg_rouge = sum(rouge_scores) / len(rouge_scores)
    avg_precision = sum(precision_scores) / len(precision_scores)
    avg_recall = sum(recall_scores) / len(recall_scores)
    avg_f1 = sum(f1_scores) / len(f1_scores)

    return {
        "results": results,
        "avg_bleu": round(avg_bleu, 3),
        "avg_rouge": round(avg_rouge, 3),
        "avg_precision": round(avg_precision, 3),
        "avg_recall": round(avg_recall, 3),
        "avg_f1": round(avg_f1, 3)
    }


if __name__ == "__main__":
    report = evaluate_vlm()
    print(json.dumps(report, ensure_ascii=False, indent=2))
