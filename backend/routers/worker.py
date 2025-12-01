import asyncio
import json
import logging
from pathlib import Path
from ml.models.baseline import LLaVAVision
import aio_pika

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MAX_RETRIES = 3
RETRY_DELAY = 2  # секунды


async def process_task(task_id: str, image_path: str) -> dict:
    """Асинхронная обработка одного задания с retry логикой."""
    vlm = LLaVAVision()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = vlm.infer(image_path)
            if result and "error" not in result:
                return {"status": "done", "ingredients": result}
            logging.warning(f"[{task_id}] Попытка {attempt}: ошибка или пустой результат {result}")
        except Exception as e:
            logging.error(f"[{task_id}] Попытка {attempt}: исключение {e}")
        await asyncio.sleep(RETRY_DELAY)
    return {"status": "error", "error": f"Не удалось обработать {image_path} после {MAX_RETRIES} попыток"}


async def on_message(message: aio_pika.IncomingMessage):
    async with message.process():  # auto-ack при выходе из блока
        try:
            body = json.loads(message.body.decode())
            task_id = body["task_id"]
            image_path = body["image_path"]
            logging.info(f"[{task_id}] Получено задание, файл: {image_path}")

            result = await process_task(task_id, image_path)

            # сохраняем результат
            result_path = Path(f"./results/{task_id}.json")
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logging.info(f"[{task_id}] Результат сохранён в {result_path}")
        except Exception as e:
            logging.error(f"Ошибка обработки сообщения: {e}")


async def main():
    # robust = авто‑переподключение при сбоях
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()

    # ВАЖНО: очередь должна быть объявлена с теми же параметрами, что и в FastAPI
    queue = await channel.declare_queue("ingredient_queue", durable=True)

    logging.info(" [*] Async worker запущен. Ожидание сообщений...")
    await queue.consume(on_message)

    # держим воркер живым
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Остановка воркера по Ctrl+C")
