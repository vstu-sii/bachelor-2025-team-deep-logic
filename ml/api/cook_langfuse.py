from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv()
langfuse = Langfuse()

def cook_from_image(image_path, vlm, llm, prompt_version="v1", dietary=None, feedback=None):
    # Корневой спан (trace)
    with langfuse.start_as_current_span(
        name="cook_from_image",
        input={"image_path": image_path, "dietary": dietary, "feedback": feedback},
        metadata={"prompt_version": prompt_version}
    ) as root:

        # Шаг 1: VLM (распознавание продуктов)
        with langfuse.start_as_current_span(
            name="vlm_infer",
            input={"image_path": image_path}
        ) as vlm_span:
            vlm_out = vlm.infer(image_path)
            vlm_span.output = vlm_out

        # Список распознанных ингредиентов
        predicted = [ing["name"] if isinstance(ing, dict) else ing
                     for ing in vlm_out.get("ingredients", [])]

        # Шаг 2: LLM (генерация рецептов)
        with langfuse.start_as_current_generation(
            name="llm_generate_recipe",
            input={"ingredients": predicted, "dietary": dietary, "feedback": feedback}
        ) as gen:
            recipe = llm.generate_recipe(
                ingredients=vlm_out.get("ingredients", []),
                dietary=dietary,
                feedback=feedback
            )
            gen.output = recipe

        # Финальный результат корневого спана
        root.output = {"ingredients": predicted, "recipe": recipe}

    return {
        "ingredients": predicted,
        "recipe": recipe,
        "vlm_raw": vlm_out,
        "prompt_version": prompt_version
    }
