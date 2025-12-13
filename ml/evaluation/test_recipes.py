import json
import os
import re
import requests
from dotenv import load_dotenv
from ml.models.baseline import MistralText

# Загружаем ключи
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-medium"

llm = MistralText()

def clean_mistral_output(output: str) -> str:
    if not isinstance(output, str):
        return ""

    # убираем Markdown-обёртку
    clean = re.sub(r"^```(?:json)?", "", output.strip(), flags=re.IGNORECASE | re.MULTILINE)
    clean = re.sub(r"```$", "", clean.strip(), flags=re.MULTILINE)

    # убираем дефисы между объектами
    clean = re.sub(r"\n\s*-\s*\n", "\n", clean)
    clean = re.sub(r"^\s*-\s*{", "{", clean, flags=re.MULTILINE)

    # убираем управляющие символы (ASCII 0–31 и 127)
    clean = re.sub(r'[\x00-\x1f\x7f]', ' ', clean)

    # обрезаем всё после последней закрывающей скобки
    end = clean.rfind("}")
    if end != -1:
        clean = clean[:end+1]

    return clean.strip()



def check_with_mistral(recipes, dietary):
    """Проверка рецептов через Mistral (диета + уровни сложности)."""
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = (
        "Ты проверяющий ассистент. Верни строго валидный JSON без Markdown.\n\n"
        f"Рецепты (JSON):\n{json.dumps(recipes, ensure_ascii=False, indent=2)}\n\n"
        f"Диетические ограничения: {dietary or 'нет'}\n\n"
        "Проверь:\n"
        "1) Нет ли в рецептах запрещённых ингредиентов.\n"
        "   Учитывай производные: если указано 'лактоза', то нельзя использовать молочные продукты.\n"
        "2) Есть ли среди рецептов все уровни сложности: легкое, среднее, сложное.\n\n"
        "Ответь ТОЛЬКО JSON следующей формы:\n"
        "{\n"
        '  "dietary_ok": true,\n'
        '  "difficulty_ok": true\n'
        "}\n"
    )

    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": "Ты проверяющий ассистент. Возвращай только чистый валидный JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 256,
    }

    response = requests.post(MISTRAL_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        return {"error": f"Mistral API error: {response.status_code}", "details": response.text}

    data = response.json()
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    if not content:
        return {"error": "Empty response content from Mistral"}

    cleaned = clean_mistral_output(content)
    try:
        parsed = json.loads(cleaned)
    except Exception as e:
        return {"error": f"Invalid JSON from Mistral: {e}", "raw_output": content, "cleaned": cleaned}

    return {
        "dietary_ok": bool(parsed.get("dietary_ok", False)),
        "difficulty_ok": bool(parsed.get("difficulty_ok", False)),
    }

def run_tests(report_file="recipes_test_report.txt"):
    tests_path = os.path.join("ml", "evaluation", "test_recipes.json")
    with open(tests_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    total = len(test_cases)
    passed_both = 0
    passed_diet = 0
    passed_diff = 0
    lines = []

    for idx, case in enumerate(test_cases, start=1):
        print(f"\n▶️ Тест {idx}: ингредиенты={case['ingredients']}, диета={case['dietary']}")
        recipes = llm.generate_recipe(
            case["ingredients"],
            dietary=case.get("dietary", "нет"),
            feedback=case.get("user_feedback", "нет")
        )

        if isinstance(recipes, dict) and "error" in recipes:
            result_line = f"Тест {idx}: ❌ Ошибка генерации ({recipes})"
            print("  " + result_line)
            lines.append(result_line)
            continue

        check_result = check_with_mistral(recipes, case.get("dietary", "нет"))

        if "error" in check_result:
            print(f"  ❌ Ошибка проверки: {check_result}")
            lines.append(f"Тест {idx}: Ошибка проверки: {check_result}")
            continue

        dietary_ok = check_result.get("dietary_ok", False)
        difficulty_ok = check_result.get("difficulty_ok", False)

        # обновляем счётчики
        if dietary_ok:
            passed_diet += 1
        if difficulty_ok:
            passed_diff += 1
        if dietary_ok and difficulty_ok:
            passed_both += 1

        print(f"  Проверка диеты: {'✅' if dietary_ok else '❌'}")
        print(f"  Проверка сложностей: {'✅' if difficulty_ok else '❌'}")

        lines.append(f"Тест {idx}:")
        lines.append(f"  Ингредиенты: {case['ingredients']}")
        lines.append(f"  Диета: {case.get('dietary', 'нет')}")
        lines.append(f"  Проверка диеты: {'OK' if dietary_ok else 'FAIL'}")
        lines.append(f"  Проверка сложностей: {'OK' if difficulty_ok else 'FAIL'}")

        # сохраняем рецепты
        # сохраняем рецепты
        lines.append("  Сгенерированные рецепты:")
        for r in recipes:
            lines.append(f"    - {r.get('name', 'без названия')}")
            if "ingredients" in r:
                ingr_list = ", ".join(i.get("name", "") for i in r["ingredients"])
                lines.append(f"      ингредиенты: {ingr_list}")
            if "difficulty" in r:
                lines.append(f"      сложность: {r['difficulty']}")
        lines.append("")


    # считаем проценты
    percent_diet = (passed_diet / total) * 100 if total else 0.0
    percent_diff = (passed_diff / total) * 100 if total else 0.0
    percent_both = (passed_both / total) * 100 if total else 0.0

    summary = (
        f"📊 Итог по {total} тестам:\n"
        f"  ✅ Диета: {passed_diet}/{total} ({percent_diet:.1f}%)\n"
        f"  ✅ Сложности: {passed_diff}/{total} ({percent_diff:.1f}%)\n"
        f"  ✅ Оба условия: {passed_both}/{total} ({percent_both:.1f}%)"
    )

    print("\n" + summary)
    lines.append(summary)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run_tests()
