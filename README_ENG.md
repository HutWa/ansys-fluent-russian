# Ansys Fluent Russian Localization

This is an unofficial community project translating the Ansys Fluent interface into Russian. It is suitable for translation review, but it does not yet replace the English interface in full.

Russian version: [README.md](README.md).

## Translation progress

**23,011 of 28,786 Fluent strings are translated — 79.9% of the Fluent Student 2026 R1 interface.**

Some major windows are already displayed in Russian, while many dialogs still contain English text. A string is not considered complete until its meaning has been confirmed in the interface.

| Work status | Strings |
|---|---:|
| Translated | **23,011** |
| Needs context | 165 |
| Needs editorial review | 74 |
| Do not translate | 555 |
| Not yet added to the project catalog | 4,981 |

The [visual review log](docs/VISUAL_REVIEW_20260905.md) records which windows have been checked in Fluent and which English strings remain.

### Main menu

**Fluent ribbon (`Ribbon/*`): 1,150 of 1,150 strings are translated.** This covers the File, Domain, Physics, User-Defined, Solution, Results, View, Parallel, Design, Parametric, and Learning and Support tabs, as well as their commands.

The top ribbon was still English in a screenshot of the previously installed build. It therefore needs a visual recheck after the next build and installation.

## Automated progress and visual QA

GitHub Actions validates the catalog and publishes exact progress, PR-base deltas, and visual-QA status in its run summary. CI warns when translations in a previously verified window change without an accompanying visual-review update.

You can generate the same reports locally:

```powershell
python scripts/report_progress.py --all-modules
python scripts/check_visual_review.py
```

Window status and observations live in [reviews/v2026R1/windows.yml](reviews/v2026R1/windows.yml), with a shared checklist in [reviews/v2026R1/checklist.md](reviews/v2026R1/checklist.md). Module coverage is reported for modules already represented in the catalog.

## For Fluent users

**Fluent Student 2026 R1** is supported experimentally. The localization loads in Fluent, but visual review does not yet cover the whole interface.

Close Fluent before installing a new build. The installer creates a backup, so the original interface can be restored safely.

- [Installation, Russian-language launch, and rollback — Russian](docs/INSTALLATION_RU.md)
- [Installation, launch, and rollback — English](docs/INSTALLATION_EN.md)

## What is translated

The project translates UI labels for buttons, tabs, settings, and messages. Zone, phase, surface, material, and other object names are left unchanged. Formulas, variable names, and internal identifiers are preserved too.

This repository contains no Ansys files. It stores only project-created translations, a terminology glossary, and build tools.

## How to contribute

1. Read the [translation guide](docs/TRANSLATION_GUIDE.md) and [contribution guidelines](docs/CONTRIBUTING.md).
2. Use the [CFD glossary](dictionary/glossary_ru.json) to keep terminology consistent.
3. Check translated windows in Fluent and record remaining English strings in the visual review log.

Technical validation steps are documented in the [translation guide](docs/TRANSLATION_GUIDE.md).

## Important notice

This is an independent community project. It is not affiliated with, endorsed by, or supported by Ansys, Inc. Ansys and Fluent are trademarks of their respective owners. A project license has not yet been selected; the options are described in [LICENSE_DECISION.md](docs/LICENSE_DECISION.md).
