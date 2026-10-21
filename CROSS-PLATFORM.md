# Freedom GPT 1.5.0: платформы / platforms

Сборки Windows и Ubuntu проверены локально. macOS распространяется как
экспериментальный кандидат с явно указанными ограничениями. Модели
скачиваются отдельно; видеокомплект автора проверен, другие новые загрузки на паузе.

В 1.5.0 доступны цели, очередь и срочные поправки, ветки чатов и память проекта.
Обновления проверяются и скачиваются только по кнопке «Проверить обновления».
Для перехода с 1.4.x один раз используйте полный установщик после остановки
приложения, сохранив резервную копию. Старый автоматический канал намеренно
не устанавливает 1.5.0. [Проверки этой версии](docs/RELEASE-1.5.0-VERIFICATION.md).

| Система | Формат | Проверка |
| --- | --- | --- |
| Windows 10/11 x64 | EXE, ZIP | На Windows 11, отдельный runtime и PATH без сторонних программ |
| Ubuntu 24.04 x64 | `.run`, `.deb`, `.tar.gz` | Чистый контейнер без Python и сети; физический рабочий стол не проверен |
| macOS 26.2+, Apple Silicon M1+ | `.app` внутри ZIP | Проверены ARM64 и зависимости; реальный запуск на Mac ещё не проверен |

Intel Mac, Ubuntu ARM и более ранняя macOS не поддерживаются этими пакетами.
Mac-кандидат не подписан Developer ID и не notarized. Для статуса проверенного Mac-релиза нужны
установка и реальная генерация на Mac. Готовые движки ограничивают macOS:
SD требует 26.0, зависимость llama RDMA — 26.2. Поддержка старых macOS
потребует отдельной нативной компиляции и проверки.

## Внутри сборок

- Приватный Python, библиотеки агента, интерфейс RU/EN, Node.js и npm.
- Windows: прежний проверенный CUDA-движок, дополнительные Vulkan и CPU.
- Ubuntu: CUDA/Vulkan/CPU для текста; Vulkan/CPU для изображений и видео.
- Mac: Metal и CPU с общей памятью Apple Silicon.
- Wheelhouse для восстановления отсутствующих Python-библиотек без сети.
- Проверка CPU/RAM/GPU/диска и основных компонентов при первом запуске.
- Каталог, поиск моделей, возобновляемые загрузки и проверка SHA256.

Системный Python и Ollama не нужны. Веса моделей не включены: скачайте их
через приложение или импортируйте локальные файлы. После загрузки локальный
чат работает без интернета. При отсутствии ускорения доступен медленный CPU.

Драйверы GPU устанавливаются средствами ОС/производителя. Git, Docker,
Blender, SDK устройств, браузеры для автоматизации, специальные утилиты
и библиотеки отдельных проектов не входят целиком в этот runtime.
Личный набор инструментов автора не переносится автоматически между ОС.
Для Python-проектов используйте комплектный Python с `-m venv`/`-m pip`,
для JS — комплектные Node/npm. Сохраняйте зависимости внутри проекта.

## Установка

**Windows:** EXE в новую папку либо полный ZIP → `FreedomGPT.exe`.
Установщик не подписан Authenticode. Чаты, ключи и веса автора не включены.

**Ubuntu:**

```sh
sh FreedomGPT-Setup-1.5.0-Ubuntu-x64.run
```

Без запуска, в выбранную папку SSD:

```sh
FREEDOM_INSTALL_DIR=/mnt/ssd/FreedomGPT sh FreedomGPT-Setup-1.5.0-Ubuntu-x64.run --install-only
```

Root не требуется. По умолчанию: `~/.local/share/FreedomGPT`, ярлык в
`~/.local/share/applications`. DEB использует `/opt/freedom-gpt/App` и на
первом запуске создаёт личную копию runtime. TAR.GZ можно распаковать
и запустить `Start-FreedomGPT.sh`. Носитель должен разрешать исполнение
файлов; не используйте `noexec`. До отключения SSD вызовите Stop-FreedomGPT.

**Mac:** распаковать ZIP → переместить `Freedom GPT.app` в Applications →
открыть. Неподписанный кандидат может потребовать разрешения владельца
в системных настройках безопасности. Не отключайте защиту macOS глобально.
Данные создаются в `~/Library/Application Support/FreedomGPT`. Для другой
папки есть комплектный `Install-FreedomGPT.sh --target /Volumes/SSD/FreedomGPT`.
Установка на реальном Mac пока не проверена.

## Доказательства проверок

- `logs/windows-clean-pc-verification-1.5.0.json`: проверки ядра, запуска,
  повторного запуска, истории и восстановления отсутствующей библиотеки.
- `logs/ubuntu-clean-pc-verification-1.5.0.json`: проверки без системного Python
  и сети, включая Node, pip, повторную установку и сохранение данных.
- `logs/ubuntu-cuda-model-verification.json`: Linux CUDA в Docker/WSL2
  загрузил существующий Huihui GGUF, ответил `OK` и написал Python-функцию.
  Контекст теста 1024, без MTP: это проверка работоспособности, не обещание
  скорости на физической Ubuntu или при 65K-контексте.
- `logs/macos-all-native-audit-1.5.0.json`: ARM64 и зависимости 104 нативных файлов.
  Статическая проверка не заменяет запуск на Mac.
- Конечные архивы и установщики имеют отдельные отчёты в `logs/`.

API слушают только loopback. Существующие веса для теста подключены только
для чтения. Комплект Wan скачан и проверен SHA-256. Реальная генерация видео
на Windows/RTX 4080 проверена; на macOS и физической Ubuntu она ещё не проверена.

## Повторная сборка локально

Папка: `A:\CodexProjects\freedom-gpt-release`. Используйте установленный
Python на A:, не создавайте кэши/сборки в профиле Windows.

```powershell
python packaging/platform_bundle.py --target ubuntu-x64 --runtime-from build/FreedomGPT-1.3.0 --stage-only
python packaging/platform_bundle.py --target macos-arm64 --runtime-from build/FreedomGPT-1.3.0 --stage-only
python packaging/release_platform.py --target ubuntu-x64
python packaging/release_platform.py --target macos-arm64
```

Переупаковка `release_platform.py` не скачивает и не публикует ничего.
Для Windows задайте `FREEDOM_BUILD_NODE` путём официального Node.js,
затем используйте `packaging/bundle.py --runtime-from build/FreedomGPT-1.3.0`
и `packaging/release.py`. Версии/SHA256 закреплены в `native-lock.json`,
Python-пакеты — в `requirements-portable.lock` и wheel manifests.
На новой машине сборщика заранее подготовьте Windows wheelhouse командой
`python packaging/fetch_wheels.py --target windows-x64`; на машине автора
он уже скачан и проверен. Этот шаг не загружает веса моделей.

Раздельные подписанные каналы: `update.json` (Windows),
`update-macos-arm64.json`, `update-ubuntu-x64.json`. Ed25519 и SHA256
проверяются до установки; пакет другой ОС отклоняется. POSIX-пакеты сохраняют
права исполнения. Чаты, модели и настройки исключены из allowlist обновлений.
Каналы публикуются вместе с проверенным релизом; закрытый ключ остаётся в `.private`.

## English summary

Private Python, agent libraries, Node.js/npm and native engines are included.
No preinstalled Python, Ollama or paid API is required for local chat.
Models download separately. GPU drivers and optional project tools are managed
separately; the author's personal tool collection is not bundled.
Windows and clean offline Ubuntu core tests passed. Linux CUDA also generated
Python code from existing weights in a 1024-context smoke test.
The Mac candidate requires Apple Silicon/macOS 26.2+, is unsigned, not notarized
and has not run on a Mac. Intel Mac is not included. Everything stays local.

## Обновление проверки видео — 1.4.2
Веса Wan на ПК автора полностью скачаны и проверены SHA-256. Исправлен конфликт записи состояния Windows. Реальная генерация 512×288 / 33 кадра / 20 шагов проверена на RTX 4080: 50,24 с с возвратом к модели кода. Декодирование WebM, HTTP Range и ответ модели кода после видео проверены. На macOS и физической Ubuntu генерация видео ещё не проверена.
