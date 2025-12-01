import os
from pathlib import Path
from PIL import Image
import numpy as np

# Папка с обработанными фото
PROCESSED_DIR = Path("C:\\Users\\Наталья\\Desktop\\lab2-AI Engineer-deliverables\\data\\processed_images")

IMG_SIZE = (512, 512)   # ожидаемый размер
EXPECTED_FORMAT = "JPEG"

def validate_images():
    issues = []
    files = [f for f in os.listdir(PROCESSED_DIR) if f.lower().endswith(".jpg")]
    files.sort(key=lambda x: int(Path(x).stem))  # сортировка по числу в имени

    # Проверка последовательности имён (1.jpg, 2.jpg, ...)
    for idx, file in enumerate(files, start=1):
        expected_name = f"{idx}.jpg"
        if file != expected_name:
            issues.append((file, f"Ожидалось имя {expected_name}"))

    for file in files:
        path = PROCESSED_DIR / file
        try:
            img = Image.open(path)
            # Проверка формата
            if img.mode != "RGB":
                issues.append((file, f"Неверный цветовой режим: {img.mode}"))
            # Проверка размера
            if img.size != IMG_SIZE:
                issues.append((file, f"Неверный размер: {img.size}"))
            # Проверка на пустое/однотонное изображение
            arr = np.array(img)
            if arr.min() == arr.max():
                issues.append((file, "Изображение однотонное"))
        except Exception as e:
            issues.append((file, f"Ошибка чтения: {e}"))

    return issues

if __name__ == "__main__":
    problems = validate_images()
    if problems:
        print("[WARN] Найдены проблемы:")
        for p in problems:
            print(" -", p)
    else:
        print("[OK] Все изображения прошли валидацию и проверки качества")
