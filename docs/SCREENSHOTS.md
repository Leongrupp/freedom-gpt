# Real Freedom GPT interface / Настоящий интерфейс

Captured on 21 October 2026 from Freedom GPT 1.5.0 on Windows 11, using the local `huihui-coder-local` model. These are actual application renders, with no replacement of chat text or invented controls. ExpenseLab is a neutral demonstration project; private chats and credentials were not used.

Снимки сделаны 21 октября 2026 в работающей Freedom GPT 1.5.0 на Windows 11 с локальной моделью. ExpenseLab — демонстрационный проект. Содержимое переписки и элементы интерфейса не подменялись; личные чаты и ключи в снимки не включены.

| View / Экран | Русский | English UI |
|---|---|---|
| Workspace overview / Рабочее пространство | [Open](../assets/screenshots/overview-ru.png) | [Open](../assets/screenshots/overview-en.png) |
| Chat and code editor / Чат и редактор | [Open](../assets/screenshots/chat-ru.png) | [Open](../assets/screenshots/chat-en.png) |
| Goal and history / Цель и история | [Open](../assets/screenshots/goal-ru.png) | [Open](../assets/screenshots/goal-en.png) |
| Hardware advisor / Подбор моделей | [Open](../assets/screenshots/models-ru.png) | [Open](../assets/screenshots/models-en.png) |
| Queue and correction / Очередь и поправка | [Open](../assets/screenshots/agent-working-ru.png) | Russian conversation |

The agent wrote a Decimal-based expense summary, incorporated negative values and uncategorized rows from an urgent correction, ran six passing tests and wrote the queued README. Its goal then completed in two steps and appeared in history. Separate checks covered file editing, stale-edit protection, recoverable removal, restoration and a branch retaining its history and files with an empty queue.

Агент написал модуль подсчёта расходов через Decimal, учёл отрицательные суммы и записи без категории из срочной поправки, выполнил шесть тестов и создал README из очереди. Затем цель завершилась за два шага и перешла в историю. Дополнительно проверены правка файлов, защита от устаревшей версии, корзина, восстановление и ветка с прежними файлами и перепиской, без старой очереди.

The screenshots show Windows, not a native Mac or Ubuntu desktop test. The English interface retains the same Russian example conversation. Hardware and timings are examples, not minimum requirements or speed guarantees. See [release verification](RELEASE-1.5.0-VERIFICATION.md) for the platform boundaries.

Снимки показывают Windows и не подтверждают запуск на настоящем Mac. В английском интерфейсе сохранена та же демонстрационная переписка на русском. Железо и время работы — примеры, а не гарантии скорости.


## Release 1.6.0 panels / Панели 1.6.0

Captured on Windows on 22 October 2026 in a separate clean installation with version 1.6.0. These are real UI captures, not mockups. The installation had no private chats, connected accounts or phone-pairing key. The settings and phone panel show their actual state; the achievement profile is a fresh level-one profile with zero rewards. These panels do not claim a completed model task. The older ExpenseLab captures above remain the record of a real agent task.

- [Compact settings and RU / EN / 中文](../assets/screenshots/settings-160.png)
- [Actual achievement profile](../assets/screenshots/rewards-160.png)
- [Optional phone connection, switched off](../assets/screenshots/phone-160.png)

Новые снимки сделаны в отдельной чистой Windows-установке 1.6.0. Переписки, аккаунты и ключи доступа автора не переносились. Профиль наград действительно новый, с нулевым прогрессом. Скриншоты панелей не подменяют доказательство выполнения задания агентом; для него сохранены исходные снимки ExpenseLab.


## 22 October: fresh 1.6.0 showcase

- [Russian workspace](../assets/screenshots/workspace-160-ru.png) and [English workspace](../assets/screenshots/workspace-160-en.png): actual app on loopback in an isolated Windows installation. Fixture chats were archived through the normal recoverable archive. No chat text, controls or metrics were painted into the images.
- [Notifications](../assets/screenshots/notifications-160.png): the actual Settings → Notifications → Try it preview, labelled Preview in the app. It is not presented as a completed task.
- Rewards and phone images show actual 1.6.0 Windows panels, not a physical phone or native Mac.
- No pairing QR, credentials or author chat history. Images are not AI-generated.
