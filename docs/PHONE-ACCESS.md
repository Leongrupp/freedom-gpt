# Доступ с телефона / Phone access

Available in Freedom GPT **1.6.0+**. Optional, disabled by default.

## Подключение

1. На ПК: **Настройки → Доступ с телефона**, включите функцию.
2. Нажмите **Показать QR-код** и отсканируйте его камерой iPhone.
3. В Safari нажмите **Подключить этот телефон**.
4. Сравните шестизначные коды и нажмите **Разрешить на компьютере**.
5. Откройте чат. Для быстрого входа: Safari → Поделиться → На экран «Домой».

Работает через [сервер связи проекта](https://aionpc.ru:8445/). Отдельный аккаунт,
SSH-пароль, настройка роутера, профиль VPN и приложение из App Store не нужны.
ПК должен быть включён, без сна и с запущенным Freedom GPT. Интернет нужен обоим
устройствам. Закрытие страницы на телефоне не останавливает работу агента.

Мобильная страница использует те же чаты, очередь и разрешения агента на ПК.
Не выдавайте агенту больше прав, чем требуется задаче. Если выбрана платная
API-модель, сохраняются условия и тарифы её провайдера.

На одном ПК действует один сеанс телефона. Новый телефон заменяет прежний
только после подтверждения на ПК. В любой момент можно отозвать доступ или
выключить соединение. При удалении cookie/в инкогнито может потребоваться новое
подключение. QR-код одноразовый и действует пять минут, разрешение телефона —
до 90 дней. Ключи компьютера не входят в установщики.

## Privacy and trust

The PC makes an outbound authenticated WebSocket connection over HTTPS. Each
installation has an independent Ed25519 key. The key is protected with Windows
DPAPI on Windows and file permissions (0600) on POSIX systems. It is never sent
to the relay. The phone receives a Secure, HttpOnly, SameSite=Strict browser
session only after approval on the PC. Device/session metadata is stored by the
relay; chat content, uploads and downloads are streamed, not persisted there.

**The relay handles the transferred data. This is not end-to-end encryption.**
Enable remote access only when you trust its operator. Local/offline use does
not need the relay. The phone's API requests have the same powers as the local
interface, within the permissions configured for the agent.

The shared phone origin serves only trusted Freedom GPT interface assets.
Customer PCs cannot serve arbitrary HTML/JavaScript through it. HTML files are
download-only, proxy cookies are never forwarded to the PC, and browser storage
is scoped to each PC. PC approval endpoints cannot be reached through the tunnel.

## Limits and availability

The free project relay initially supports up to **25 connected PCs**, with
registration/connection limits. It can temporarily reject new connections when
full. Uploads are limited to **20 MB per request** and streamed downloads to
**512 MB**. Keep large model downloads on the PC. No availability or universal
mobile-carrier compatibility is guaranteed; restrictive networks can block the
relay's HTTPS port. Local operation continues if remote access is unavailable.

## Self-hosting

Relay source and a deployment example are in [connect/](../connect/README.md).
The desktop's `data/remote-access.json` can specify your own HTTPS relay origin
in its `relay` field while the feature is disabled. Use a trusted TLS certificate.
Never publish `data/`, device keys, cookies, pairing links or customer databases.

## Verification

The implementation was tested with two independent PC identities, mandatory
approval, one-time/expired QR codes, streamed uploads/downloads, protected browser
storage, WebSocket compression boundaries, reconnection and revocation. The live
browser flow was tested through the project HTTPS relay. The unsigned macOS core passed native ARM64 CI with a model fixture;
real GPU generation remains untested; see [CROSS-PLATFORM.md](../CROSS-PLATFORM.md).

The earlier owner-only iPhone certificate installation is separate from this
public feature. No owner key or phone profile is included in public packages.
