import os
import time
import json
import random
import re
import asyncio
import requests
from dotenv import load_dotenv
from langfuse.langchain import CallbackHandler
from langchain_core.runnables import Runnable, RunnableSequence
from transformers import AutoTokenizer
from langfuse import Langfuse

# --- Загрузка окружения и инициализация Langfuse + токенайзера ---
load_dotenv()
lf = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)
langfuse_handler = CallbackHandler()
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.2")

# --- Константы для Mistral проверки LLM ---
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small"

# --- Утилита нормализации текста ингредиентов ---
def normalize(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())

# --- Подсчёт токенов и стоимости ---
def count_tokens_and_cost(prompt: str, output: str, model: str = "mistral-small"):
    input_tokens = len(tokenizer.encode(prompt))
    output_tokens = len(tokenizer.encode(output))
    total_tokens = input_tokens + output_tokens

    # Примерные цены-фикстуры (замени на реальные при необходимости)
    price_per_input = 0.25 / 1_000_000
    price_per_output = 0.25 / 1_000_000
    cost = input_tokens * price_per_input + output_tokens * price_per_output

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }, cost

# --- Метрики VLM ---
def compute_f1(predicted, reference):
    predicted_set = set(normalize(p) for p in predicted if p)
    reference_set = set(normalize(r) for r in reference if r)

    tp = len(predicted_set & reference_set)
    fp = len(predicted_set - reference_set)
    fn = len(reference_set - predicted_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return f1

def compute_excess(predicted, reference):
    predicted_set = set(normalize(p) for p in predicted if p)
    reference_set = set(normalize(r) for r in reference if r)
    excess = predicted_set - reference_set
    excess_ratio = len(excess) / len(predicted_set) if predicted_set else 0.0
    return excess_ratio

# --- Утилиты очистки вывода Mistral + ретраи ---
def clean_mistral_output(output: str) -> str:
    if not isinstance(output, str):
        return ""
    clean = re.sub(r"^```(?:json)?", "", output.strip(), flags=re.IGNORECASE | re.MULTILINE)
    clean = re.sub(r"```$", "", clean.strip(), flags=re.MULTILINE)
    end = clean.rfind("}")
    if end != -1:
        clean = clean[:end + 1]
    return clean.strip()

def post_with_retries(url, headers, payload, timeout=60, max_retries=5, base_delay=0.8):
    last_resp = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except Exception:
            last_resp = None
            time.sleep(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5))
            continue
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
        break
    return last_resp

# --- Проверка рецептов для LLM (диета/сложность/время/калорийность) ---
def check_with_mistral(recipes, dietary, preferred_difficulty, preferred_time, preferred_calories):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = (
        "Ты проверяющий ассистент. Верни строго валидный JSON без Markdown.\n\n"
        "Задача: проверить список рецептов по четырём критериям и вернуть булевы флаги.\n"
        "Категории:\n"
        " - Сложность: легко / средне / сложно\n"
        " - Время готовки: быстро / средне / долго\n"
        " - Калорийность: низкокалорийное / среднекалорийное / высококалорийное\n\n"
        f"Рецепты (JSON):\n{json.dumps(recipes, ensure_ascii=False, indent=2)}\n\n"
        f"Диетические ограничения: {dietary or 'нет'}\n"
        f"Предпочитаемая сложность: {preferred_difficulty or 'нет'}\n"
        f"Предпочитаемое время: {preferred_time or 'нет'}\n"
        f"Предпочитаемая калорийность: {preferred_calories or 'нет'}\n\n"
        "Ответь ТОЛЬКО JSON:\n"
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
        "max_tokens": 192,
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

# --- Варианты A/B ---
def pick_vlm_variant():
    return random.choice(["vlm_prompt_a", "vlm_prompt_b"])

def pick_llm_variant():
    return random.choice(["llm_prompt_a", "llm_prompt_b"])

# --- Адаптер для VLM ---
class VLMRunnable(Runnable):
    def __init__(self, vlm):
        self.vlm = vlm

    def invoke(self, inputs, config=None):
        start = time.time()
        image_path = inputs["image_path"]

        variant = pick_vlm_variant()
        try:
            prompt_text = self.vlm.build_prompt(image_path)
        except Exception:
            prompt_text = ""

        result = self.vlm.infer(image_path)
        duration = round(time.time() - start, 2)

        reference_ingredients = inputs.get("reference_ingredients", []) or []
        predicted_ingredients = [
            (i.get("name", "") if isinstance(i, dict) else str(i))
            for i in result.get("ingredients", [])
        ]
        predicted_ingredients = [p for p in predicted_ingredients if p]

        f1 = compute_f1(predicted_ingredients, reference_ingredients)
        excess_ratio = compute_excess(predicted_ingredients, reference_ingredients)

        metrics_payload = {
            "duration_sec": float(duration),
            "f1": float(f1),
            "excess_ratio": float(excess_ratio)
        }

        try:
            lf.log_event(
                name="vlm_infer",
                input={"image_path": image_path, "prompt": prompt_text},
                output={"ingredients": result.get("ingredients", [])},
                metadata={"variant": variant},
                metrics=metrics_payload
            )
        except Exception as e:
            print("DEBUG: vlm lf.log_event failed:", repr(e))
            with open("lf_vlm_log_debug.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "time": time.time(),
                    "variant": variant,
                    "metrics": metrics_payload,
                    "error": repr(e)
                }, ensure_ascii=False) + "\n")

        return {
            "vlm_variant": variant,
            "input": {
                "image_path": image_path,
                "prompt": prompt_text
            },
            "output": {"ingredients": result.get("ingredients", [])},
            "vlm_duration_sec": duration,
            "dietary": inputs.get("dietary"),
            "feedback": inputs.get("feedback"),
            "preferred_calorie_level": inputs.get("preferred_calorie_level"),
            "preferred_cooking_time": inputs.get("preferred_cooking_time"),
            "preferred_difficulty": inputs.get("preferred_difficulty"),
            "existing_recipes": inputs.get("existing_recipes"),
            "vlm_checks": {
                "f1": f1,
                "excess_ratio": excess_ratio
            }
        }

# --- Адаптер для LLM ---
class LLMRunnable(Runnable):
    def __init__(self, llm):
        self.llm = llm

    def invoke(self, inputs, config=None):
        start = time.time()

        # Выбираем вариант промпта (A/B)
        llm_variant = pick_llm_variant()
        prompt_variant = inputs.get("vlm_variant")

        # Метрики VLM
        vlm_checks = inputs.get("vlm_checks", {}) or {}
        f1 = vlm_checks.get("f1")
        excess_ratio = vlm_checks.get("excess_ratio")

        # Формируем вход для LLM
        llm_input = {
            "ingredients": inputs["output"]["ingredients"],
            "dietary": inputs.get("dietary"),
            "feedback": inputs.get("feedback"),
            "prompt_variant": prompt_variant,
            "preferred_calorie_level": inputs.get("preferred_calorie_level"),
            "preferred_cooking_time": inputs.get("preferred_cooking_time"),
            "preferred_difficulty": inputs.get("preferred_difficulty"),
            "existing_recipes": inputs.get("existing_recipes"),
            "vlm_f1": f1,
            "vlm_excess_ratio": excess_ratio
        }

        # Получаем промпт из Langfuse (по имени варианта)
        try:
            prompt_text = self.llm.get_prompt(llm_variant)
        except Exception:
            prompt_text = "Составь рецепт на основе ингредиентов."

        # Генерация рецепта
        async def _call_mistral():
            await self.llm.init_client()
            try:
                return await self.llm.generate_recipe(prompt=prompt_text, ingredients=llm_input["ingredients"])
            finally:
                await self.llm.close_client()

        response = asyncio.run(_call_mistral())
        recipe = response[0] if isinstance(response, list) and response else response

        usage, cost = count_tokens_and_cost(prompt_text, str(recipe))
        duration = round(time.time() - start, 2)

        # Проверка предпочтений
        pref_diff = llm_input.get("preferred_difficulty")
        pref_time = llm_input.get("preferred_cooking_time")
        pref_cal = llm_input.get("preferred_calorie_level")
        dietary = llm_input.get("dietary")

        all_prefs_empty = all(
            (v is None) or (isinstance(v, str) and v.strip().lower() == "нет")
            for v in (pref_diff, pref_time, pref_cal, dietary)
        )

        if all_prefs_empty:
            dietary_ok = difficulty_ok = time_ok = calories_ok = True
            check_error = None
        else:
            check_result = check_with_mistral(
                recipe,
                dietary or "нет",
                pref_diff or "нет",
                pref_time or "нет",
                pref_cal or "нет"
            )
            if isinstance(check_result, dict) and "error" in check_result:
                dietary_ok = difficulty_ok = time_ok = calories_ok = False
                check_error = check_result
            else:
                dietary_ok = check_result.get("dietary_ok", False)
                difficulty_ok = check_result.get("difficulty_ok", False)
                time_ok = check_result.get("time_ok", False)
                calories_ok = check_result.get("calories_ok", False)
                check_error = None

        # Логируем событие в Langfuse
        try:
            lf.log_event(
                name="llm_generate_recipe",
                input=llm_input,
                output={"recipe": recipe},
                metadata={"variant": llm_variant},
                metrics={
                    "duration_sec": float(duration),
                    "tokens": float(usage["total_tokens"]),
                    "cost": float(cost),
                    "dietary_ok": bool(dietary_ok),
                    "difficulty_ok": bool(difficulty_ok),
                    "time_ok": bool(time_ok),
                    "calories_ok": bool(calories_ok),
                    "vlm_f1": float(f1) if isinstance(f1, (int, float)) else None,
                    "vlm_excess_ratio": float(excess_ratio) if isinstance(excess_ratio, (int, float)) else None
                }
            )
        except Exception as e:
            print("DEBUG: llm lf.log_event failed:", repr(e))

        return {
            "llm_variant": llm_variant,
            "input": llm_input,
            "output": {"recipe": recipe},
            "duration_sec": duration,              # задержка LLM
            "vlm_duration_sec": inputs.get("vlm_duration_sec"),  # ← добавлено
            "usage": usage,
            "cost": cost,
            "llm_checks": {
                "dietary_ok": dietary_ok,
                "difficulty_ok": difficulty_ok,
                "time_ok": time_ok,
                "calories_ok": calories_ok
            }
        }



# --- Основная функция ---
def cook_from_image(
    image_path,
    vlm,
    llm,
    dietary=None,
    feedback=None,
    preferred_calorie_level=None,
    preferred_cooking_time=None,
    preferred_difficulty=None,
    existing_recipes=None,
    reference_ingredients=None  # для VLM метрик
):
    vlm_runnable = VLMRunnable(vlm).with_config(run_name="vlm_infer")
    llm_runnable = LLMRunnable(llm).with_config(run_name="llm_generate_recipe")

    chain = RunnableSequence(first=vlm_runnable, last=llm_runnable).with_config(run_name="cook_from_image")

    result = chain.invoke(
        {
            "image_path": image_path,
            "dietary": dietary,
            "feedback": feedback,
            "preferred_calorie_level": preferred_calorie_level,
            "preferred_cooking_time": preferred_cooking_time,
            "preferred_difficulty": preferred_difficulty,
            "existing_recipes": existing_recipes,
            "reference_ingredients": reference_ingredients or []
        },
        config={"callbacks": [langfuse_handler]}
    )

    return result
