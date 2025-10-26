from ml.models.baseline import LLaVAVision, MistralText
from ml.api.cook_langfuse import cook_from_image  # импортируй функцию, которую ты написала

vlm = LLaVAVision()
llm = MistralText()

result = cook_from_image(
    image_path="C:\\Users\\Наталья\\Desktop\\lab2-AI Engineer-deliverables\\data\\processed_images\\1.jpg",
    vlm=vlm,
    llm=llm,
    dietary="нет",
    feedback="нет"
)

print(result)

