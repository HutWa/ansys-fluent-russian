# Каталоги переводов

Каждая версия Fluent хранится отдельно. Промежуточный `catalog.json` использует схему `schemas/translation-catalog.schema.json` и не заменяет исходный формат ресурсов Fluent: конвертер в реальный ресурс будет добавлен после анализа локальной установки.

Пример записи первого прохода:

```json
{
  "id": "solver.example",
  "source": "Example %1",
  "translation": "Пример %1",
  "status": "translated",
  "context": "Название панели или элемента UI",
  "comment": ""
}
```

Для `needs_review` укажите причину сомнения в `comment`, а возможные варианты — в `alternatives`. Для `needs_context` укажите, какого контекста интерфейса не хватает. Запись со статусом `reviewed` обязана содержать отдельный объект `review` с полями `reviewer` и `checked_at`.
