from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv()
langfuse = Langfuse()

def cook_from_image(image_path, vlm, llm, prompt_version="v1"):
    # Корневой спан (создаёт trace автоматически)
    with langfuse.start_as_current_span(
        name="cook_from_image",
        input={"image_path": image_path},
        metadata={"prompt_version": prompt_version}
    ) as root:

        # Шаг 1: VLM
        with langfuse.start_as_current_span(
            name="vlm_infer",
            input={"image_path": image_path}
        ) as vlm_span:
            vlm_out = vlm.infer(image_path)
            vlm_span.output = vlm_out

        predicted = [ing["name"] if isinstance(ing, dict) else ing
                     for ing in vlm_out.get("ingredients", [])]

        # Шаг 2: LLM (как генерация)
        with langfuse.start_as_current_generation(
            name="llm_generate_recipe",
            input={"ingredients": predicted}
        ) as gen:
            recipe = llm.generate_recipe(predicted)
            gen.output = recipe

        # Финальный результат корневого спана
        root.output = {"ingredients": predicted, "recipe": recipe}

    return {"ingredients": predicted, "recipe": recipe}
