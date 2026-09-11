# Автоматическая визуальная проверка Fluent 2026 R1

## Назначение

`reviews/v2026R1/automation/home-navigation.jou` — безопасный Fluent GUI journal: он выбирает страницы `General`, `Materials`, `Graphics` и `Surfaces`, выдерживая паузу для захвата. Скрипт не читает и не сохраняет case, не изменяет настройки и не запускает расчёт.

Перед запуском journal проверяется статически: `python scripts/check_visual_journal.py reviews/v2026R1/automation/home-navigation.jou`. Разрешены только выбор узла дерева и паузы, поэтому в сценарий не может попасть команда изменения модели или расчёта.
`launch_fluent.py --journal` выполняет ту же проверку и откажется запускать journal с другой командой.

Вместе с `scripts/capture_fluent_window.py` это убирает ручные снимки и переходы между этими страницами. Журнал использует внутренние английские пути Fluent; на кадрах оцениваются именно отображаемые русские подписи.

## Запуск

```powershell
python scripts/launch_fluent.py --fluent-root "D:\games\ANSYS Inc\ANSYS Student\v261\fluent" `
  --capture-output build/visual-qa-journal `
  --journal reviews/v2026R1/automation/home-navigation.jou -- 3d -t1
```

После завершения journal Fluent остаётся открытым, а кадры лежат в `build/visual-qa-journal`. Наблюдатель завершится после закрытия Fluent. Кадры и манифест исключены из Git.
Если кадры не появились, точная причина записывается в `build/visual-qa-journal/watcher.log`.

## Ограничение и развитие

GUI-journal должен проверяться на каждой версии Fluent: внутренние пути элементов не являются публичным API. Если страница не открылась, это фиксируется как ошибка автоматизации, а не как результат визуальной проверки. После фактического подтверждения путей сценарий расширяется на остальные приоритетные окна beta.1.
