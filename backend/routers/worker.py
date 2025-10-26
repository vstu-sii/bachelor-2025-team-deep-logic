import pika
import json
import logging
import time
from pathlib import Path
from ml.models.baseline import LLaVAVision

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MAX_RETRIES = 3
RETRY_DELAY = 2  # секунды

def process_task(task_id: str, image_path: str) -> dict:
    """Обработка одного задания с retry логикой."""
    vlm = LLaVAVision()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = vlm.infer(image_path)
            if result and "error" not in result:
                return result
            logging.warning(f"[{task_id}] Попытка {attempt}: ошибка или пустой результат {result}")
        except Exception as e:
            logging.error(f"[{task_id}] Попытка {attempt}: исключение {e}")
        time.sleep(RETRY_DELAY)
    return {"error": f"Не удалось обработать {image_path} после {MAX_RETRIES} попыток"}

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        task_id = message["task_id"]
        image_path = message["image_path"]
        logging.info(f"[{task_id}] Получено задание, файл: {image_path}")

        result = process_task(task_id, image_path)

        # сохраняем результат
        result_path = Path(f"./results/{task_id}.json")
        result_path.parent.mkdir(parents=True, exist_ok=True)
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logging.info(f"[{task_id}] Результат сохранён в {result_path}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logging.error(f"Ошибка обработки сообщения: {e}")
        # подтверждаем, чтобы сообщение не зацикливалось
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        channel = connection.channel()
        channel.queue_declare(queue="ingredient_queue")
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue="ingredient_queue", on_message_callback=callback)
        logging.info(" [*] Worker запущен. Ожидание сообщений...")
        channel.start_consuming()
    except KeyboardInterrupt:
        logging.info("Остановка воркера по Ctrl+C")
    except Exception as e:
        logging.error(f"Ошибка соединения с RabbitMQ: {e}")

if __name__ == "__main__":
    main()
