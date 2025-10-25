import pika, json
from pathlib import Path
from ml.models.baseline import LLaVAVision

def callback(ch, method, properties, body):
    message = json.loads(body)
    task_id = message["task_id"]
    image_path = message["image_path"]

    vlm = LLaVAVision()
    result = vlm.infer(image_path)

    # сохраняем результат
    result_path = Path(f"./results/{task_id}.json")
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    ch.basic_ack(delivery_tag=method.delivery_tag)  # подтверждаем обработку

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()
    channel.queue_declare(queue="ingredient_queue")
    channel.basic_qos(prefetch_count=1)  # по одному сообщению
    channel.basic_consume(queue="ingredient_queue", on_message_callback=callback)
    print(" [*] Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()

if __name__ == "__main__":
    main()
