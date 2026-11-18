# Freedom GPT Connect

An optional, self-hostable relay for Freedom GPT 1.5.1+ phone access.
The desktop initiates an outbound connection; no inbound PC port is opened.
Pairing requires explicit approval on the PC. Each installation has its own key.

## Build and run

From the repository root, build the trusted interface first:

```sh
cd app
npm ci --ignore-scripts
npm run build
cd ..
docker build -t freedom-gpt-connect -f connect/Dockerfile .
docker run -d --name freedom-gpt-connect \
  -p 127.0.0.1:18869:18869 \
  -v freedom-gpt-connect:/state \
  -e FREEDOM_CONNECT_ORIGIN=https://your-domain.example \
  --memory=256m --cpus=0.5 --restart=unless-stopped freedom-gpt-connect
```

Terminate HTTPS at your own reverse proxy using a valid certificate. Preserve
WebSocket Upgrade/Connection headers, disable proxy request/response buffering,
and keep the relay bound to loopback. Use an unoccupied HTTPS port or your own
separate virtual host; preserve existing websites and VPN services.

In the desktop, while phone access is disabled, set the HTTPS `relay` origin in
`data/remote-access.json`. Enable the feature and pair a phone normally.

For a Python environment, install `connect/requirements.txt`, copy the trusted
`app/dist/` to `ui/` beside `relay.py` and add `app/public/freedom.svg` as
`ui/freedom.svg`. Run `relay.py` with the environment variables below. Use a
dedicated unprivileged account and a private writable state directory.

| Variable | Default | Purpose |
| --- | --- | --- |
| `FREEDOM_CONNECT_ROOT` | directory of relay.py | Read-only source, web pages and trusted `ui/` |
| `FREEDOM_CONNECT_STATE` | root directory | Private writable authorization database |
| `FREEDOM_CONNECT_ORIGIN` | `https://aionpc.ru:8445` | Exact public HTTPS origin |
| `FREEDOM_CONNECT_PORT` | `18869` | Loopback HTTP listener |
| `FREEDOM_CONNECT_CAPACITY` | `25` | Maximum simultaneous authenticated PCs |

Do not enable HTTP in production. Keep the database private, do not log query
strings or pairing links, and do not expose the loopback listener directly.
Back up device authorization metadata securely if persistence is desired.

## Security scope

The relay stores PC public keys, display names and hashed phone sessions. It
streams API messages/files and does not persist their content. **TLS terminates
at the relay: this is not end-to-end encryption.** The operator is trusted to
handle remote requests. Users must opt in; local mode has no relay dependency.

Only trusted release UI assets are served. Arbitrary customer HTML/JavaScript
is blocked, local approval endpoints are excluded from forwarding, browser
storage is scoped per PC, and request queues and file sizes are bounded.
The service has no analytics, advertising SDK, paid tunnel dependency or user
password collection. The normal MIT project license applies.
