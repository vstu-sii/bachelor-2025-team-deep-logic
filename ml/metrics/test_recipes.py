import json
import os
import re
import time
import random
import asyncio
import requests
from dotenv import load_dotenv
from ml.service.baseline import MistralText

# Загружаем ключи
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small"

llm = MistralText()

def clean_mistral_output(output: str) -> str:
    """Очищает вывод модели от Markdown-обёртки и мусора, оставляя JSON."""
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
        clean = clean[:end + 1]

    return clean.strip()

def post_with_retries(url, headers, payload, timeout=60, max_retries=5, base_delay=0.8):
    """
    Простые ретраи с экспоненциальной задержкой и джиттером.
    Обрабатывает 429 и временные 5xx. Уважает Retry-After, если он есть.
    """
    last_resp = None
    for attempt in range(1, max_retries + 1):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        last_resp = resp

        if resp.status_code == 200:
            return resp

        retry_after = resp.headers.get("Retry-After")
        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt == max_retries:
                break
            if retry_after:
                try:
                    delay = float(retry_after)
                except Exception:
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            else:
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            time.sleep(delay)
            continue

        # Для прочих статусов — не ретраим
        break

    return last_resp

def check_with_mistral(recipes, dietary, preferred_difficulty, preferred_time, preferred_calories):
    """
    Проверка рецептов по четырём критериям:
    - диетические ограничения,
    - соответствие сложности (легко/средне/сложно),
    - соответствие времени готовки (быстро/средне/долго),
    - соответствие калорийности (низкокалорийное/среднекалорийное/высококалорийное).
    Возвращает словарь с флагами *_ok.
    """
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    # Строго описываем категории в промпте
    prompt = (
        "Ты проверяющий ассистент. Верни строго валидный JSON без Markdown.\n\n"
        "Задача: проверить список рецептов по четырём критериям и вернуть булевы флаги.\n"
        "Категории для проверки:\n"
        " - Сложность: легко / средне / сложно\n"
        " - Время готовки: быстро / средне / долго\n"
        " - Калорийность: низкокалорийное / среднекалорийное / высококалорийное\n\n"
        f"Рецепты (JSON):\n{json.dumps(recipes, ensure_ascii=False, indent=2)}\n\n"
        f"Диетические ограничения: {dietary or 'нет'}\n"
        f"Предпочитаемая сложность (легко/средне/сложно): {preferred_difficulty or 'нет'}\n"
        f"Предпочитаемое время готовки (быстро/средне/долго): {preferred_time or 'нет'}\n"
        f"Предпочитаемая калорийность (низкокалорийное/среднекалорийное/высококалорийное): {preferred_calories or 'нет'}\n\n"
        "Проверь:\n"
        "1) Нет ли запрещённых ингредиентов или их производных (например, 'лактоза' запрещает молочные продукты).\n"
        "2) Соответствует ли сложность рецептов заданной категории (если задана).\n"
        "3) Соответствует ли время готовки заданной категории (если задана).\n"
        "4) Соответствует ли калорийность заданной категории (если задана).\n\n"
        "Ответь ТОЛЬКО JSON следующей формы:\n"
        "{\n"
        '  "dietary_ok": true,\n'
        '  "difficulty_ok": true,\n'
        '  "time_ok": true,\n'
        '  "calories_ok": true\n'
        "}\n"
    )

    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": "Ты проверяющий ассистент. Возвращай только чистый валидный JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 192,  # немного снизим нагрузку
    }

    response = post_with_retries(MISTRAL_URL, headers, payload, timeout=60, max_retries=5, base_delay=0.8)
    if response is None or response.status_code != 200:
        details = None if response is None else response.text
        return {"error": f"Mistral API error: {getattr(response, 'status_code', 'unknown')}", "details": details}

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
        "time_ok": bool(parsed.get("time_ok", False)),
        "calories_ok": bool(parsed.get("calories_ok", False)),
    }

async def run_tests(report_file="recipes_test_report.txt", inter_test_delay=0.6):
    """
    Запускает тесты из ml/metrics/test_recipes.json,
    генерирует рецепты через llm (асинхронно), проверяет их по 4 критериям,
    печатает результаты и сохраняет отчёт.
    inter_test_delay — пауза между тестами для снижения вероятности 429.
    """
    tests_path = os.path.join("ml", "metrics", "test_recipes.json")
    with open(tests_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    total = len(test_cases)
    passed_all = 0
    passed_diet = 0
    passed_diff = 0
    passed_time = 0
    passed_calories = 0
    lines = []

    for idx, case in enumerate(test_cases, start=1):
        # Выводим предпочитаемые параметры в начале теста
        print(
            "\n▶️ Тест {idx}: ингредиенты={ingredients}, диета={diet}, "
            "предпочт. сложность={difficulty}, предпочт. время={time}, "
            "предпочт. калорийность={calories}".format(
                idx=idx,
                ingredients=case['ingredients'],
                diet=case.get('dietary', 'нет'),
                difficulty=case.get('preferred_difficulty', 'нет'),
                time=case.get('preferred_cooking_time', 'нет'),
                calories=case.get('preferred_calorie_level', 'нет'),
            )
        )

        # Генерация рецептов (асинхронно)
        recipes = await llm.generate_recipe(
            case["ingredients"],
            dietary=case.get("dietary", "нет"),
            feedback=case.get("user_feedback", "нет"),
            preferred_difficulty=case.get("preferred_difficulty", "нет"),
            preferred_cooking_time=case.get("preferred_cooking_time", "нет"),
            preferred_calorie_level=case.get("preferred_calorie_level", "нет")
        )

        # Если генератор вернул ошибку
        if isinstance(recipes, dict) and "error" in recipes:
            result_line = f"Тест {idx}: ❌ Ошибка генерации ({recipes})"
            print("  " + result_line)
            lines.append(result_line)
            time.sleep(inter_test_delay)
            continue

        # Проверка рецептов по условиям (синхронный вызов с ретраями)
        check_result = check_with_mistral(
            recipes,
            case.get("dietary", "нет"),
            case.get("preferred_difficulty", "нет"),
            case.get("preferred_cooking_time", "нет"),
            case.get("preferred_calorie_level", "нет")
        )

        if "error" in check_result:
            print(f"  ❌ Ошибка проверки: {check_result}")
            lines.append(f"Тест {idx}: Ошибка проверки: {check_result}")
            time.sleep(inter_test_delay)
            continue

        dietary_ok = check_result.get("dietary_ok", False)
        difficulty_ok = check_result.get("difficulty_ok", False)
        time_ok = check_result.get("time_ok", False)
        calories_ok = check_result.get("calories_ok", False)

        if dietary_ok:
            passed_diet += 1
        if difficulty_ok:
            passed_diff += 1
        if time_ok:
            passed_time += 1
        if calories_ok:
            passed_calories += 1
        if all([dietary_ok, difficulty_ok, time_ok, calories_ok]):
            passed_all += 1

        print(f"  Проверка диеты: {'✅' if dietary_ok else '❌'}")
        print(f"  Проверка сложности: {'✅' if difficulty_ok else '❌'}")
        print(f"  Проверка времени: {'✅' if time_ok else '❌'}")
        print(f"  Проверка калорийности: {'✅' if calories_ok else '❌'}")

        lines.append(f"Тест {idx}:")
        lines.append(f"  Ингредиенты: {case['ingredients']}")
        lines.append(f"  Диета: {case.get('dietary', 'нет')}")
        lines.append(
            f"  Предпочтения: сложность={case.get('preferred_difficulty','нет')}, "
            f"время={case.get('preferred_cooking_time','нет')}, "
            f"калорийность={case.get('preferred_calorie_level','нет')}"
        )
        lines.append(f"  Проверка диеты: {'OK' if dietary_ok else 'FAIL'}")
        lines.append(f"  Проверка сложности: {'OK' if difficulty_ok else 'FAIL'}")
        lines.append(f"  Проверка времени: {'OK' if time_ok else 'FAIL'}")
        lines.append(f"  Проверка калорийности: {'OK' if calories_ok else 'FAIL'}")
        lines.append("")

        # Краткая витрина рецептов (если структура ожидаемая)
        lines.append("  Сгенерированные рецепты:")
        try:
            for r in recipes:
                lines.append(f"    - {r.get('name', 'без названия')}")
                if "ingredients" in r:
                    ingr_list = ", ".join(i.get("name", "") for i in r["ingredients"])
                    lines.append(f"      ингредиенты: {ingr_list}")
                if "difficulty" in r:
                    lines.append(f"      сложность: {r['difficulty']}")
                if "time" in r or "cooking_time" in r:
                    lines.append(f"      время: {r.get('time', r.get('cooking_time', 'не указано'))}")
                if "calorie_level" in r:
                    lines.append(f"      калорийность: {r['calorie_level']}")
            lines.append("")
        except Exception:
            pass

        # Пауза между тестами, чтобы сгладить bursts и уменьшить 429
        time.sleep(inter_test_delay)

    # Считаем проценты
    percent_diet = (passed_diet / total) * 100 if total else 0.0
    percent_diff = (passed_diff / total) * 100 if total else 0.0
    percent_time = (passed_time / total) * 100 if total else 0.0
    percent_calories = (passed_calories / total) * 100 if total else 0.0
    percent_all = (passed_all / total) * 100 if total else 0.0

    summary = (
        f"📊 Итог по {total} тестам:\n"
        f"  ✅ Диета: {passed_diet}/{total} ({percent_diet:.1f}%)\n"
        f"  ✅ Сложность: {passed_diff}/{total} ({percent_diff:.1f}%)\n"
        f"  ✅ Время: {passed_time}/{total} ({percent_time:.1f}%)\n"
        f"  ✅ Калорийность: {passed_calories}/{total} ({percent_calories:.1f}%)\n"
        f"  ✅ Все условия: {passed_all}/{total} ({percent_all:.1f}%)"
    )

    print("\n" + summary)
    lines.append(summary)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    asyncio.run(run_tests())
