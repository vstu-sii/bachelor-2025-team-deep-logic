import os
import time
import json
from dotenv import load_dotenv
from langfuse.langchain import CallbackHandler
from langchain.schema.runnable import Runnable, RunnableSequence
from transformers import AutoTokenizer

# Загружаем токенайзер для Mistral
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.2")

# Загружаем ключи из .env
load_dotenv()
os.environ["LANGFUSE_PUBLIC_KEY"] = os.getenv("LANGFUSE_PUBLIC_KEY")
os.environ["LANGFUSE_SECRET_KEY"] = os.getenv("LANGFUSE_SECRET_KEY")
os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_HOST")

# Handler для LangChain
langfuse_handler = CallbackHandler()


# --- Подсчёт токенов и стоимости ---
def count_tokens_and_cost(prompt: str, output: str, model: str = "mistral-medium"):
    input_tokens = len(tokenizer.encode(prompt))
    output_tokens = len(tokenizer.encode(output))
    total_tokens = input_tokens + output_tokens

    # тарифы для mistral-medium (пример: $0.25 за 1M токенов)
    price_per_input = 0.25 / 1_000_000
    price_per_output = 0.25 / 1_000_000
    cost = input_tokens * price_per_input + output_tokens * price_per_output

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }, cost


# --- Адаптер для VLM ---
# --- Адаптер для VLM ---
class VLMRunnable(Runnable):
    def __init__(self, vlm):
        self.vlm = vlm

    def invoke(self, inputs, config=None):
        start = time.time()
        image_path = inputs["image_path"]
        prompt = self.vlm.build_prompt(image_path)
        result = self.vlm.infer(image_path)
        duration = round(time.time() - start, 2)

        return {
            "input": {"image_path": image_path, "prompt": prompt},
            "output": {"ingredients": result.get("ingredients", [])},
            "duration_sec": duration,
            "dietary": inputs.get("dietary"),
            "feedback": inputs.get("feedback")
        }


# --- Адаптер для LLM ---
class LLMRunnable(Runnable):
    def __init__(self, llm):
        self.llm = llm

    def invoke(self, inputs, config=None):
        start = time.time()

        # формируем полный вход для LLM
        llm_input = {
            "ingredients": inputs["output"]["ingredients"],
            "dietary": inputs.get("dietary"),
            "feedback": inputs.get("feedback"),
            "prompt": inputs["input"]["prompt"],
            "preferred_calorie_level": inputs.get("preferred_calorie_level"),
            "preferred_cooking_time": inputs.get("preferred_cooking_time"),
            "preferred_difficulty": inputs.get("preferred_difficulty"),
            "existing_recipes": inputs.get("existing_recipes")
        }

        # вызов LLM с учётом усиленного промпта
        response = self.llm.generate_recipe(
            ingredients=llm_input["ingredients"],
            dietary=llm_input["dietary"],
            feedback=llm_input["feedback"],
            preferred_calorie_level=llm_input["preferred_calorie_level"],
            preferred_cooking_time=llm_input["preferred_cooking_time"],
            preferred_difficulty=llm_input["preferred_difficulty"],
            existing=llm_input["existing_recipes"]
        )

        recipe = response[0] if isinstance(response, list) and response else response

        usage, cost = count_tokens_and_cost(llm_input["prompt"], str(recipe))
        duration = round(time.time() - start, 2)

        return {
            "input": llm_input,
            "output": {"recipe": recipe},
            "duration_sec": duration,
            "usage": usage,
            "cost": cost
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
    existing_recipes=None
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
            "existing_recipes": existing_recipes
        },
        config={"callbacks": [langfuse_handler]}
    )

    return result

