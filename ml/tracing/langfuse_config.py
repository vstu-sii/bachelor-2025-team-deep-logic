from langfuse import Langfuse
from dotenv import load_dotenv
import os

load_dotenv()
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST")
)

def cook_from_image(image_path, vlm, llm, prompt_version="v1", dietary=None, feedback=None):
    with langfuse.start_as_current_span(
        name="cook_from_image",
        input={"image_path": image_path, "dietary": dietary, "feedback": feedback},
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

        # Шаг 2: LLM (Mistral)
        with langfuse.start_as_current_generation(
            name="mistral_generate_recipe",
            model="mistral-medium",
            input={"ingredients": predicted, "dietary": dietary, "feedback": feedback}
        ) as gen:
            recipe = llm.generate_recipe(
                ingredients=vlm_out.get("ingredients", []),
                dietary=dietary,
                feedback=feedback
            )
            gen.output = recipe

        root.output = {"ingredients": predicted, "recipe": recipe}

    return {
        "ingredients": predicted,
        "recipe": recipe,
        "vlm_raw": vlm_out,
        "prompt_version": prompt_version
    }
