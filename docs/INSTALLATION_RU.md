# Установка

Экспериментальная установка подтверждена для Ansys Fluent Student 2026 R1. Перед использованием закройте Fluent.

## Сборка и установка

```powershell
python scripts/build_translation.py translations/v2026R1/catalog.json `
  --fluent-root "D:\путь\к\v261\fluent" `
  --output-dir "C:\временный\каталог\build"

python scripts/install.py `
  --fluent-root "D:\путь\к\v261\fluent" `
  --staging-dir "C:\временный\каталог\build" `
  --backup-dir "C:\безопасный\каталог\backup"
```

Последняя команда по умолчанию выполняет только предварительный просмотр. Проверьте список файлов и повторите её с флагом `--apply`. Не удаляйте каталог резервной копии: в нём хранится манифест отката.

## Запуск на русском языке

```powershell
python scripts/launch_fluent.py --fluent-root "D:\путь\к\v261\fluent" -- 3d -t1
```

Скрипт задаёт `lang=ru` только процессу Fluent. Глобальные переменные Windows и `languagesettings.txt` не изменяются.

## Удаление

```powershell
python scripts/uninstall.py --backup-dir "C:\безопасный\каталог\backup"
```

Сначала проверьте dry-run, затем повторите команду с `--apply`. Откат остановится, если установленный файл или резервная копия были изменены.
