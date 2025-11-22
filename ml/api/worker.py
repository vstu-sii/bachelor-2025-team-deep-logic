import asyncio
import json
import logging
import time
from pathlib import Path
from ml.service.baseline import LLaVAVision
import aio_pika

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MAX_RETRIES = 3
RETRY_DELAY = 2
LOG_LATENCY_FILE = "./reports/vlm_latency.log"
MAX_CONCURRENT_TASKS = 3


async def process_task(task_id: str, image_path: str, queued_at: float = None) -> dict:
    vlm = LLaVAVision()
    start_time = time.perf_counter()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = vlm.infer(image_path, queued_at=queued_at)
            duration = time.perf_counter() - start_time
            completed_at = time.time()

            if result and "error" not in result:
                parsed = result.get("ingredients", [])
                logging.info(f"[{task_id}] Обработка завершена за {duration:.2f} сек")

                with open(LOG_LATENCY_FILE, "a", encoding="utf-8") as log_file:
                    log_file.write(f"{task_id},{duration:.3f}\n")

                return {
                    "status": "done",
                    "ingredients": [{"name": i} for i in parsed],
                    "queued_at": queued_at,
                    "completed_at": completed_at,
                    "duration_sec": round(duration, 3)
                }

            logging.warning(f"[{task_id}] Попытка {attempt}: ошибка или пустой результат {result}")
        except Exception as e:
            logging.error(f"[{task_id}] Попытка {attempt}: исключение {e}")
        await asyncio.sleep(RETRY_DELAY)

    duration = time.perf_counter() - start_time
    logging.warning(f"[{task_id}] Не удалось обработать за {duration:.2f} сек")
    with open(LOG_LATENCY_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(f"{task_id},ERROR,{duration:.3f}\n")
    return {
        "status": "error",
        "error": f"Не удалось обработать {image_path} после {MAX_RETRIES} попыток",
        "queued_at": queued_at,
        "completed_at": time.time(),
        "duration_sec": round(duration, 3)
    }


async def on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            task_id = body["task_id"]
            image_path = body["image_path"]
            queued_at = body.get("queued_at", time.time())
            logging.info(f"[{task_id}] Получено задание, файл: {image_path}")

            result = await process_task(task_id, image_path, queued_at)

            result_path = Path(f"./results/{task_id}.json")
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logging.info(f"[{task_id}] Результат сохранён в {result_path}")
        except Exception as e:
            logging.error(f"Ошибка обработки сообщения: {e}")


async def connect_and_consume():
    while True:
        try:
            # 🔹 robust‑подключение с heartbeat и autoreconnect
            connection = await aio_pika.connect_robust(
                "amqp://guest:guest@localhost/",
                reconnect_interval=5,
                heartbeat=60
            )
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=MAX_CONCURRENT_TASKS)
            queue = await channel.declare_queue("ingredient_queue", durable=True)

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            logging.info(f" [*] Async worker запущен. Параллельность: {MAX_CONCURRENT_TASKS}")

            async def limited_handler(message: aio_pika.IncomingMessage):
                async with semaphore:
                    await on_message(message)

            await queue.consume(limited_handler)

            # 🔹 ждём пока соединение живое
            await connection.ready()
            await asyncio.Future()

        except Exception as e:
            logging.error(f"Соединение потеряно: {e}. Повтор через 5 секунд...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(connect_and_consume())
    except KeyboardInterrupt:
        logging.info("Остановка воркера по Ctrl+C")
