# Installation

Experimental installation has been verified with Ansys Fluent Student 2026 R1. Close Fluent before installing files.

## Build and install

```powershell
python scripts/build_translation.py translations/v2026R1/catalog.json `
  --fluent-root "D:\path\to\v261\fluent" `
  --output-dir "C:\temporary\build"

python scripts/install.py `
  --fluent-root "D:\path\to\v261\fluent" `
  --staging-dir "C:\temporary\build" `
  --backup-dir "C:\safe\backup"
```

The installer defaults to a preview. Review the file list, then repeat the command with `--apply`. Keep the backup directory because it contains the rollback manifest.

## Launch in Russian

```powershell
python scripts/launch_fluent.py --fluent-root "D:\path\to\v261\fluent" -- 3d -t1
```

The launcher sets `lang=ru` only for the Fluent child process. It does not modify global Windows environment variables or `languagesettings.txt`.

## Uninstall

```powershell
python scripts/uninstall.py --backup-dir "C:\safe\backup"
```

Review the dry-run first, then repeat with `--apply`. Rollback stops if an installed file or its backup has been modified.
