# Parking Accessibility Model

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Итеративная модель распределения спроса по парковкам с учётом конкуренции и времени пешего доступа по улично-дорожной сети.

## Описание

Этот проект реализует модель доступности парковок, которая:

- Строит граф пешеходной доступности из улично-дорожной сети
- Вычисляет матрицу происхождение-назначение (OD matrix) с учетом времени ходьбы
- Распределяет спрос на парковки итеративным методом с учетом конкуренции
- Визуализирует результаты на картах и графиках

### Основные возможности

- 🗺️ Построение графа из геопространственных данных (GeoPackage, Shapefile, GeoJSON)
- ⏱️ Расчет кратчайших путей с учетом времени ходьбы
- 📊 Итеративное распределение спроса с конкуренцией между парковками
- 📈 Визуализация результатов: карты загрузки, покрытия, распределения
- ⚙️ Гибкая конфигурация через JSON файл
- 🔧 Поддержка пользовательских функций вероятности

## Установка

### Требования

- Python 3.9 или выше
- Геопространственные библиотеки (geopandas, shapely)

### Установка зависимостей

```bash
pip install -r requirements.txt
```

Или через conda:

```bash
conda install geopandas shapely networkx numpy pandas matplotlib
```

### Установка пакета (опционально)

```bash
pip install -e .
```

## Быстрый старт

1. **Подготовьте данные:**

   Поместите ваши входные файлы в папку `input_data/`:
   - `roads.gpkg` - улично-дорожная сеть (LineString/MultiLineString)
   - `origins.gpkg` - кварталы/точки происхождения (Point) с полем спроса
   - `parks.gpkg` - парковки (Point) с полем вместимости

2. **Настройте конфигурацию:**

   Скопируйте `config.json.example` в `config.json` и отредактируйте параметры:

   ```bash
   cp config.json.example config.json
   ```

3. **Запустите модель:**

   ```bash
   python parking_model.py
   ```

4. **Результаты:**

   Результаты будут сохранены в `output_data/`:
   - `parking_results.gpkg` - результаты расчетов
   - `parking_results_iter_logs.csv` - логи итераций
   - `visualizations/` - карты и графики

## Структура проекта

```
parking-accessibility-model/
├── input_data/              # Входные данные
├── output_data/             # Результаты расчетов
│   ├── parking_results.gpkg
│   ├── parking_results_iter_logs.csv
│   └── visualizations/     # Визуализации
├── parking_model_pkg/       # Пакет с модулями модели
│   ├── __init__.py
│   ├── probability.py       # Функции вероятности
│   ├── parking_config.py   # Конфигурации
│   ├── graph_utils.py       # Утилиты для графа
│   ├── parking_core.py      # Ядро модели
│   ├── parking_project.py   # Высокоуровневый API
│   └── visualization.py     # Визуализация
├── parking_model.py         # Фасадный модуль
├── config.json              # Конфигурация (создается пользователем)
├── config.json.example      # Пример конфигурации
├── requirements.txt         # Зависимости
├── setup.py                 # Установка пакета
├── LICENSE                  # Лицензия MIT
└── README.md                # Документация
```

## Использование

### 1. Запуск через скрипт с конфигурацией из JSON

Самый простой способ - использовать конфигурационный файл:

```bash
python parking_model.py
```

Скрипт автоматически загрузит конфигурацию из `config.json` и выполнит все расчеты.

**Пример конфигурации (`config.json`):**

```json
{
  "paths": {
    "input_dir": "input_data",
    "output_dir": "output_data",
    "roads_file": "roads.gpkg",
    "origins_file": "origins.gpkg",
    "parks_file": "parks.gpkg",
    "output_file": "parking_results.gpkg"
  },
  "model_config": {
    "cutoff_min": 10.0,
    "max_iter": 300,
    "probability_function": {
      "type": "builtin",
      "name": "p_walk_exponential",
      "parameters": {
        "t0": 5.0,
        "t1": 10.0,
        "p_at_t1": 0.2
      }
    }
  }
}
```

### 2. Использование в Python коде

#### Простой запуск

```python
from parking_model import run_from_files

run_from_files(
    roads_path="input_data/roads.gpkg",
    origins_path="input_data/origins.gpkg",
    parks_path="input_data/parks.gpkg",
    out_gpkg_path="output_data/parking_results.gpkg",
    roads_layer="roads",
    origins_layer="origins",
    parks_layer="parks",
    origin_id_col="origin_id",
    origin_demand_col="D",
    park_id_col="parking_id",
    park_capacity_col="C",
)
```

#### ООП подход с визуализацией

```python
from parking_model import ParkingProject, GraphBuildConfig, ModelConfig

project = ParkingProject.from_files(
    roads_path="input_data/roads.gpkg",
    origins_path="input_data/origins.gpkg",
    parks_path="input_data/parks.gpkg",
    roads_layer="roads",
    origins_layer="origins",
    parks_layer="parks",
    origin_id_col="origin_id",
    origin_demand_col="D",
    park_id_col="parking_id",
    park_capacity_col="C",
    graph_cfg=GraphBuildConfig(walking_speed_kmh=4.8),
    model_cfg=ModelConfig(cutoff_min=10.0, max_iter=300),
    out_gpkg_path="output_data/parking_results.gpkg",
)

project.run()
project.save_results()
project.save_logs()

# Создаем визуализации
project.visualize(
    output_dir="output_data/visualizations",
    roads_path="input_data/roads.gpkg",
)
```

### 3. Пользовательские функции вероятности

Вы можете задать свою функцию вероятности для расчета вероятности пойти к парковке в зависимости от времени ходьбы:

#### В коде Python

```python
import numpy as np
from parking_model import ParkingProject, ModelConfig

def my_custom_probability(times):
    """
    times: numpy array времени в минутах
    returns: numpy array вероятностей (0-1)
    """
    t = np.asarray(times)
    p = np.exp(-t / 4.0)  # Экспоненциальный спад
    return np.clip(p, 0.0, 1.0)

project = ParkingProject.from_files(
    ...,
    model_cfg=ModelConfig(p_func=my_custom_probability),
)
```

#### В config.json

```json
{
  "model_config": {
    "probability_function": {
      "type": "custom",
      "name": "my_module.my_custom_function"
    }
  }
}
```

Где `my_module` - это Python модуль, а `my_custom_function` - функция, принимающая numpy array времени и возвращающая numpy array вероятностей.

## Встроенные функции вероятности

### p_walk_exponential (по умолчанию)

Экспоненциальная функция вероятности:
- p(t) = 1 для t ≤ t0 (по умолчанию 5 мин)
- p(t) = exp(-k * (t - t0)) для t0 < t ≤ t1 (по умолчанию 5-10 мин)
- p(t) = 0 для t > t1

### p_walk_piecewise (legacy)

Линейная функция вероятности (для совместимости):
- p(t) = 1 для t ≤ t0
- Линейный спад от 1 до p_at_t1 для t0 < t ≤ t1
- p(t) = 0 для t > t1

## Визуализация

Модель автоматически создает следующие визуализации:

- **parking_load_map.png** - Карта загрузки парковок (цветовая схема)
- **origin_coverage_map.png** - Карта покрытия кварталов
- **parking_load_distribution.png** - Гистограмма распределения загрузки
- **coverage_distribution.png** - Гистограмма распределения покрытия

Все визуализации сохраняются в `output_data/visualizations/`.

## Формат входных данных

### Roads (Улично-дорожная сеть)

- **Формат:** GeoPackage, Shapefile, GeoJSON
- **Геометрия:** LineString или MultiLineString
- **CRS:** Любая (автоматически преобразуется в метрическую)
- **Опциональные поля:**
  - Поле времени (минуты) - если указано в `graph_config.time_field`
  - Поле скорости (км/ч) - если указано в `graph_config.speed_field_kmh`

### Origins (Кварталы/точки происхождения)

- **Формат:** GeoPackage, Shapefile, GeoJSON
- **Геометрия:** Point
- **Обязательные поля:**
  - ID квартала (указывается в `columns.origin_id_col`)
  - Спрос (указывается в `columns.origin_demand_col`)

### Parks (Парковки)

- **Формат:** GeoPackage, Shapefile, GeoJSON
- **Геометрия:** Point
- **Обязательные поля:**
  - ID парковки (указывается в `columns.park_id_col`)
  - Вместимость (указывается в `columns.park_capacity_col`)

## Формат выходных данных

### Origins Result

Слой с результатами для кварталов:
- `demand` - исходный спрос
- `served` - обслуженный спрос
- `unserved` - необслуженный спрос
- `coverage` - покрытие (served / demand)
- `search_load` - нагрузка поиска (demand / provided)

### Parks Result

Слой с результатами для парковок:
- `capacity_init` - исходная вместимость
- `used` - использованная вместимость
- `capacity_rem` - оставшаяся вместимость
- `park_load` - загрузка (used / capacity_init)

## Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.
