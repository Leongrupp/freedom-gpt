FREEDOM GPT 1.4
===============

RU
Windows 10/11 x64: запустите установщик EXE или FreedomGPT.exe из полного ZIP.
Ubuntu 24.04 x64: sh FreedomGPT-Setup-1.4.1-Ubuntu-x64.run
Для установки без запуска добавьте --install-only. Есть также DEB и TAR.GZ.
macOS: распакуйте ZIP, перенесите Freedom GPT.app в Applications и откройте.
Текущая сборка Mac требует Apple Silicon M1+ и macOS 26.2+.
Mac Intel и более ранние macOS этой сборкой не поддерживаются.

Python, библиотеки агента, Node.js и локальные движки включены в сборку.
Системный Python, Ollama и платный API для чата не нужны.
На первом запуске откройте «Модели»: проверка ПК подберёт доступный движок.
Скачайте совместимую модель и дождитесь проверки. Веса моделей не включены.
Изображения и видео требуют отдельных весов и больше памяти; доступность
определяется проверкой ПК. GPU требует подходящего драйвера производителя.
При недоступном ускорении используется CPU, который существенно медленнее.
Инструменты для специальных задач, Git, Docker, SDK, Blender и драйверы
устройств не устанавливаются автоматически. Панель компонентов показывает
наличие основных средств. Чат не содержит весь набор инструментов автора.

В RU/EN переключается язык интерфейса. Все API слушают только 127.0.0.1.
После скачивания моделей чат работает без интернета. Интернет нужен для
поиска, сайтов, скачивания новых пакетов и проверки обновлений.
Останавливайте приложение через Stop-FreedomGPT перед отключением SSD.
Храните всю папку приложения вместе. Данные, чаты и модели находятся рядом
с установленным runtime. POSIX-установщик сохраняет их при обновлении.

Эта локальная сборка ещё не опубликована. Mac ZIP не подписан Developer ID
и не notarized; проверка запуска на реальном Mac пока не выполнена.
Автообновления требуют опубликованного подписанного канала вашей платформы.
Используйте доверенный источник, не отключайте защиту ОС глобально.

EN
Windows: run the EXE installer, or FreedomGPT.exe from the complete ZIP.
Ubuntu 24.04 x64: sh FreedomGPT-Setup-1.4.1-Ubuntu-x64.run
Add --install-only to install without launching. DEB and TAR.GZ are provided.
macOS Apple Silicon M1+, macOS 26.2+: unzip, move Freedom GPT.app to
Applications, then open. This build does not support Intel or older macOS.
The Mac candidate is unsigned, not notarized, and has not run on a real Mac.

Bundled: private Python, agent libraries, Node.js, native inference engines.
No preinstalled Python, Ollama or paid API is required for local chat.
Model weights are downloaded separately after the hardware compatibility
check. GPU acceleration needs a compatible manufacturer driver. CPU fallback
is slower. Image/video model requirements vary. Specialized tools, Git,
Docker, SDKs, Blender and device drivers are not silently installed.
The author's entire personal tool collection is not part of these builds.
Local inference works offline after downloading weights. New downloads,
websites and update checks need internet. APIs bind to loopback only.
Keep the complete app folder together and stop the app before unplugging SSD.
Signed updates require a published update feed for the specific platform.

Project: https://github.com/Leongrupp/freedom-gpt
Optional Bitcoin support:
bc1qkkzx7rzx9qace3xvyphcdfy4d5up5k9gzyhdc6

Application source: MIT. Third-party notices are in licenses/.
