import os
import re
import json
import base64
import requests
import subprocess
from ml.prompt_templates import UC_VLM_PROMPT, UC_LLM_PROMPT
from dotenv import load_dotenv
import time
from deep_translator import GoogleTranslator


def _sanitize_json_string(s: str) -> str:
    """Удаляем управляющие символы, которые ломают JSON."""
    return re.sub(r'[\x00-\x1f\x7f]', ' ', s)


class LLaVAVision:
    def infer(self, image_path: str) -> dict:
        if not os.path.exists(image_path):
            return {"error": f"File not found: {image_path}"}

        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        prompt_text = UC_VLM_PROMPT.format_messages(
            input="Определи продукты на фото"
        )
        prompt_text = "\n".join([m.content for m in prompt_text])

        payload = {
            "model": "qwen2.5vl:3b",
            "prompt": prompt_text,
            "images": [image_b64],
            "options": {
                "temperature": 0.3,   # низкая креативность, больше точности
                "top_p": 0.9,         # nucleus sampling: ограничивает выбор вероятных токенов
                "top_k": 50,
                "num_predict": 1200
            }
        }

        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                stream=True,
                timeout=300
            )
            
            text = ""
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    if "response" in data:
                        text += data["response"]
                    if "error" in data:
                        return {"error": data["error"]}

            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                clean = text[json_start:json_end]
                clean = _sanitize_json_string(clean)

                if not clean.strip():
                    return {"error": "Empty JSON from model", "raw_output": text}

                try:
                    parsed = json.loads(clean)
                except json.JSONDecodeError as e:
                    return {"error": f"Invalid JSON: {e}", "raw_output": clean}

                # Переводим ингредиенты на русский и сохраняем только их
                ingredients = parsed.get("ingredients", [])
                ingredients_ru = []
                for item in ingredients:
                    if isinstance(item, dict):
                        name_en = item.get("name", "")
                    else:
                        name_en = str(item)
                    if name_en:
                        try:
                            name_ru = GoogleTranslator(source="en", target="ru").translate(name_en)
                        except Exception:
                            name_ru = name_en
                        ingredients_ru.append({"name": name_ru})

                # теперь в parsed["ingredients"] только русский список
                parsed["ingredients"] = ingredients_ru
                return parsed

            return {"error": "No JSON object found in model output", "raw_output": text}

        except Exception as e:
            return {"error": f"VLM execution error: {str(e)}"}


# Загружаем переменные из .env
load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-medium"  # можно заменить на другую модель

class MistralText:
    def __init__(self):
        self.vlm = LLaVAVision()

    def _filter_ingredients(self, ingredients, dietary: str):
        """Удаляем ингредиенты, которые указаны в диетических ограничениях."""
        if not dietary or dietary.strip().lower() == "нет":
            return ingredients

        restrictions = [x.strip().lower() for x in dietary.split(",")]
        return [
            i for i in ingredients
            if i.get("name", "").lower() not in restrictions
        ]

    def generate_recipe(self, ingredients, dietary: str = None, existing=None, feedback: str = None) -> dict:
        # Фильтруем ингредиенты
        filtered_ingredients = self._filter_ingredients(ingredients, dietary)

        # Преобразуем список в строку
        ingredients_str = ", ".join([i["name"] for i in filtered_ingredients if "name" in i])

        # Формируем промпт
        prompt = UC_LLM_PROMPT.format_messages(
            ingredients_list=ingredients_str,
            dietary_restrictions=dietary or "нет",
            existing_recipes=existing or "нет",
            user_feedback=feedback or "нет"
        )
        prompt_text = "\n".join([m.content for m in prompt])

        try:
            headers = {
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": MISTRAL_MODEL,
                "messages": [
                    {"role": "system", "content": "Ты помощник, который составляет рецепты в JSON."},
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.4
            }

            response = requests.post(MISTRAL_URL, headers=headers, json=payload, timeout=60)

            if response.status_code != 200:
                return {"error": f"Mistral API error: {response.status_code}", "details": response.text}

            output = response.json()["choices"][0]["message"]["content"].strip()

            # Чистим Markdown
            clean = re.sub(r"^```(?:json)?", "", output.strip(), flags=re.IGNORECASE | re.MULTILINE)
            clean = re.sub(r"```$", "", clean.strip(), flags=re.MULTILINE)

            json_start = clean.find('{')
            json_end = clean.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                clean = clean[json_start:json_end]

            try:
                parsed = json.loads(clean)
                return parsed.get("recipes", parsed)
            except Exception as e:
                return {"error": f"Invalid JSON from Mistral: {e}", "raw_output": output}

        except requests.Timeout:
            return {"error": "Mistral API timeout"}
        except Exception as e:
            return {"error": f"Mistral API execution error: {str(e)}"}

