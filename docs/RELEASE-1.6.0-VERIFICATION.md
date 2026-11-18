# Freedom GPT 1.6.0 — verification / проверки

Final packages rebuilt and verified on 2026-10-23 after reply notifications were added.
Screenshots show the actual Windows interface. No author chat history, credentials,
phone pairing profiles, models or private voice/camera/upscale/converter additions are included.

| Platform / проверка | Scope / результат |
|---|---|
| Windows 11 x64 | 15 clean-copy checks; private runtime, restricted PATH, startup, chat, persistence and recovery |
| Ubuntu 24.04 x64 | 16 offline checks, no system Python/network; 8 real .run/DEB installer checks |
| Cross-platform artifacts | 14 checks: archives, update signatures, hashes, executable modes and requirements |
| Source alignment | 85 reviewed source/assets entries matched in each Windows, Ubuntu and macOS package; zero mismatches |
| Native macOS ARM64 | 14 checks: exact archive, bundled dependencies, Node, engine load, core/gateway, fixture reply and restart |

Native macOS CI: [https://github.com/Leongrupp/freedom-gpt/actions/runs/39877825964](https://github.com/Leongrupp/freedom-gpt/actions/runs/39877825964)  
Archive: `FreedomGPT-1.6.0-macOS-AppleSilicon.zip`  
SHA256: `68f60acb7d3ea1e0af9a8e4f8463d5300ad8edb70c1b161b46c3c96346ad87d2`

## Practical limits / ограничения

- macOS requires Apple Silicon and 26.2+. No Developer ID signature or notarization.
  Native core checks use a loopback model fixture: real GPU/model/media generation,
  Finder approval and the terminal download examples were not validated by this CI.
- Ubuntu checks run in an offline container; a physical desktop, drivers and GPU rendering are not covered.
- Windows clean-copy tests reuse the author's OS; they are not a separate physical PC.
- Paid providers require the user's credentials and balance; unavailable upstream models can fail.
- Phone access requires an awake, online computer and the project relay. No background iOS push.
  The owner's earlier physical cellular test is not a new device test for every installer.
- Model speed depends on hardware, model placement and context. No universal 100 tokens/s promise.
- Local video remains experimental. Earlier RTX4080 rendering evidence is historical, not a fresh cross-platform benchmark.
- Freedom rewards are local game points, not cryptocurrency or promised income.
- For 1.4.x use a deliberate full-installer upgrade with a backup; the legacy automatic channel remains blocked.

Подтверждены точные финальные пакеты и запуск ядра на трёх платформах в указанном объёме.
Проверка Mac использует тестовый ответ модели и не подтверждает генерацию на GPU.
Сохранены прежние релизы; новые файлы публикуются только после сверки SHA256 и размеров.
Обновления запускаются пользователем. Личные экспериментальные дополнения владельца
не входят в публичную1.6.0.

[Installation](../INSTALL.md) · [Установка](../INSTALL.ru.md) · [Features](FEATURES.md) · [Возможности](FEATURES.ru.md)
