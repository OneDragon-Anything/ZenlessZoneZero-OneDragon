# Zenless Zone Zero OneDragon

> Translation note: This English README was translated and adapted with ChatGPT.

Zenless Zone Zero OneDragon is a Windows automation tool for **Zenless Zone
Zero**. It provides configurable automation workflows, screen recognition,
auto-battle support, and utility tools through a PySide6 desktop interface.

## Features

- Configurable game accounts and launch settings
- Automatic battle and daily-task workflows
- Hollow Zero, Lost Void, and Withered Domain support
- Screen capture, OCR, and model-based recognition tools
- Keyboard/mouse and gamepad input options
- Notification channels and update support
- Chinese, English, and Vietnamese user-interface languages

## Requirements

- Windows 10 or later
- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- Zenless Zone Zero installed on the computer

Some workflows need downloaded recognition models or optional dependencies.
Use the application's **Resource Download** and **Script Environment** pages
to install them.

## Development setup

Clone the repository, then install the development dependencies:

```powershell
uv sync --group dev
```

Copy the environment template if the local setup needs one:

```powershell
Copy-Item env.sample.bat .env
```

Start the desktop application:

```powershell
uv run --env-file .env src/zzz_od/gui/app.py
```

The project uses a `src/` layout. Main packages are:

- `src/one_dragon/` — shared framework, configuration, and automation helpers
- `src/one_dragon_qt/` — shared Qt interface components
- `src/zzz_od/` — Zenless Zone Zero workflows and application interface

## Tests and checks

The test repository is maintained separately because some tests use game
screenshots. Clone it into this repository as `zzz-od-test/`, then run:

```powershell
uv run --env-file .env pytest zzz-od-test/
```

For linting a changed file:

```powershell
uv run --env-file .env ruff check src/path/to/changed_file.py
```

## Build

Packaging scripts are in [`deploy/`](deploy/). See the
[development documentation](docs/develop/README.md) for launcher and installer
build commands.

## License

See [LICENSE](LICENSE).
