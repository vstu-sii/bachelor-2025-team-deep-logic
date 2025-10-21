# C4 Architecture

## Context
![Context](../generated/C4_context.png)

## Containers
![Containers](../generated/C4_container.png)

## Model Manager
![Model Manager](../generated/C4_component.png)

## Model Manager Components

| Компонент          | Назначение                                   | Входные данные           | Выходные данные         |
|--------------------|----------------------------------------------|--------------------------|-------------------------|
| **Task Handler**   | Получает задачи из RabbitMQ и инициирует обработку | Сообщения (AMQP, JSON) | Задачи для коннекторов  |
| **VLM Connector**  | Отправляет фото в Ollama                     | Фото (HTTP/gRPC)         | Список ингредиентов     |
| **LLM Connector**  | Отправляет ингредиенты в Mistral API         | Ингредиенты (JSON)       | Сгенерированный рецепт  |
| **Aggregator**     | Собирает результаты от VLM и LLM             | Частичные результаты     | Итоговый ответ (JSON)   |

