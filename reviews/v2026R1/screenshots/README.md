# Visual QA screenshots

Store only useful control screenshots here. Use one folder per Fluent window, for example:

```text
velocity-inlet/
  2026-09-07-main.png
  2026-09-07-species.png
```

Add screenshots after a meaningful translation change or when an issue needs visual evidence. Do not add screenshots that expose personal paths, case data, or unrelated application windows. Reference the relevant images in `../windows.yml` when they are added.

## Автоматический локальный захват

На Windows можно не создавать снимки вручную. Пока вы открываете окна Fluent, запустите в отдельном PowerShell:

```powershell
python scripts/capture_fluent_window.py --watch --output-dir build/visual-qa
```

Скрипт сохраняет только изменившиеся кадры окна Fluent и `capture-manifest.json` в локальный каталог `build/visual-qa`, который исключён из Git. Остановите наблюдение сочетанием `Ctrl+C`. Затем агент может просмотреть эти локальные кадры непосредственно из рабочей папки.
