import os
import re
import json
import base64
import requests
from ml.prompt_templates import UC_VLM_PROMPT, UC_LLM_PROMPT
import subprocess

def _sanitize_json_string(s: str) -> str:
    # убираем управляющие символы ASCII 0–31 и 127
    return re.sub(r'[\x00-\x1f\x7f]', ' ', s)


class LLaVAVision:
    def infer(self, image_path: str) -> dict:
        """
        Распознаёт продукты на фото через LLaVA через HTTP API Ollama.
        """
        if not os.path.exists(image_path):
            return {"error": f"File not found: {image_path}"}

        # читаем файл и кодируем в base64
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": "llava",
            "prompt": UC_VLM_PROMPT,
            "images": [image_b64]
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

            # Попробуем извлечь JSON из текста
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                clean = text[json_start:json_end]
                clean = _sanitize_json_string(clean)
                return json.loads(clean)


        except Exception as e:
            return {"error": f"VLM execution error: {str(e)}"}


class Gemma3Text:
    def __init__(self):
        self.vlm = LLaVAVision()

    def generate_recipe(self, ingredients, dietary: str = None, existing=None) -> dict:
        """
        Генерация рецепта через Gemma3:4b (CLI).
        """
        from ml.prompt_templates import UC_LLM_PROMPT

        prompt = UC_LLM_PROMPT.format(
            ingredients_list=ingredients,
            dietary_restrictions=dietary or "нет",
            existing_recipes=existing or "нет"
        )

        try:
            result = subprocess.run(
                ["ollama", "run", "gemma3:4b"],
                input=prompt.encode("utf-8"),
                capture_output=True,
                timeout=300
            )

            if result.returncode != 0:
                return {"error": f"Ollama error: {result.stderr.decode('utf-8')}"}

            output = result.stdout.decode("utf-8").strip()

            # Очистка Markdown и извлечение JSON
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
                return {"error": f"Invalid JSON from LLM after cleaning: {e}", "raw_output": output}

        except subprocess.TimeoutExpired:
            return {"error": "LLM processing timeout"}
        except Exception as e:
            return {"error": f"LLM execution error: {str(e)}"}

