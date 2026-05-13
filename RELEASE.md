# Инструкции для релиза на GitHub

## Перед публикацией

1. **Обновите информацию в `setup.py`:**
   - Замените `"Your Name"` на ваше имя
   - Замените `"your.email@example.com"` на ваш email
   - Замените `"https://github.com/yourusername/parking-accessibility-model"` на URL вашего репозитория

2. **Обновите информацию в `README.md`:**
   - Замените `[Ваш GitHub](https://github.com/yourusername)` на ваш GitHub профиль
   - Обновите секцию "Авторы" если нужно

3. **Проверьте `.gitignore`:**
   - Убедитесь, что `config.json` игнорируется (пользователи создадут свой из `config.json.example`)
   - Убедитесь, что `input_data/` и `output_data/` игнорируются

4. **Удалите тестовые данные (если есть):**
   - Убедитесь, что в репозиторий не попадут ваши личные данные
   - `input_data/` и `output_data/` должны быть пустыми или не коммититься

## Создание репозитория на GitHub

1. Создайте новый репозиторий на GitHub
2. Инициализируйте git в локальной папке:

```bash
git init
git add .
git commit -m "Initial commit: Parking Accessibility Model v1.0.0"
```

3. Подключите удаленный репозиторий:

```bash
git remote add origin https://github.com/yourusername/parking-accessibility-model.git
git branch -M main
git push -u origin main
```

## Создание релиза

1. Создайте тег для версии:

```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

2. На GitHub:
   - Перейдите в раздел "Releases"
   - Нажмите "Create a new release"
   - Выберите тег v1.0.0
   - Добавьте описание релиза (можно скопировать из CHANGELOG.md)
   - Опубликуйте релиз

## Структура файлов для GitHub

```
parking-accessibility-model/
├── .github/
│   └── workflows/
│       └── python-package.yml    # CI/CD (опционально)
├── parking_model_pkg/            # Основной пакет
├── .gitignore                    # Игнорируемые файлы
├── CHANGELOG.md                  # История изменений
├── config.json.example           # Пример конфигурации
├── CONTRIBUTING.md               # Руководство для контрибьюторов
├── LICENSE                       # Лицензия MIT
├── parking_model.py              # Точка входа
├── QUICKSTART.md                 # Быстрый старт
├── README.md                     # Основная документация
├── RELEASE.md                    # Этот файл
├── requirements.txt              # Зависимости
└── setup.py                      # Установка пакета
```

## Что НЕ должно попасть в репозиторий

- `config.json` (пользовательский файл)
- `input_data/` (пользовательские данные)
- `output_data/` (результаты расчетов)
- `venv/` (виртуальное окружение)
- `__pycache__/` (кэш Python)
- `*.pyc`, `*.pyo` (скомпилированные файлы)
- Личные данные и результаты

Все это уже настроено в `.gitignore`.

## Проверка перед коммитом

```bash
# Проверьте статус
git status

# Убедитесь, что важные файлы добавлены
git ls-files | grep -E "(README|LICENSE|requirements|setup.py|config.json.example)"

# Убедитесь, что личные данные не добавлены
git ls-files | grep -E "(config.json|input_data|output_data)"
```

Если последняя команда выводит файлы - они не должны быть в репозитории. Проверьте `.gitignore`.

## Готово! 🎉

Ваш проект готов к публикации на GitHub!

