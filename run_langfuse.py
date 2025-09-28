from ml.api.cook_langfuse import cook_from_image
from ml.models.baseline import LLaVAVision, Gemma3Text  # твой код

if __name__ == "__main__":
    vlm = LLaVAVision()
    llm = Gemma3Text()
    result = cook_from_image(
        "data/processed_images/2.jpg",
        vlm,
        llm
    )
    print(result)
