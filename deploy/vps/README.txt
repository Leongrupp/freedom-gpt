Freedom GPT website deployment

Static public website, served by the existing Nginx installation.
No model inference or agent API is published by this deployment.

Layout:
  /var/www/freedom-gpt/releases/<timestamp>/public
  /var/www/freedom-gpt/current -> releases/<timestamp>
  /var/www/freedom-gpt/shared/models/<catalog-id>/<filename>
  /var/www/freedom-gpt/shared/metadata

Nginx:
  /etc/nginx/sites-available/freedom-gpt.conf
  /etc/nginx/sites-enabled/freedom-gpt.conf
The server block listens on HTTP/80 for the configured bare IP. Existing
default/domain blocks are preserved. Do not bind HTTPS/443 without checking
existing SSTP/VPN use. No firewall changes are needed by these scripts.

Metadata refresh:
  systemctl status freedom-gpt-release-refresh.timer
  systemctl start freedom-gpt-release-refresh.service
  journalctl -u freedom-gpt-release-refresh.service -n 30 --no-pager
The service uses public unauthenticated GitHub release metadata. It requires
Python 3 from the existing OS. Model links appear only for exact expected
byte sizes; full SHA256 verification is still required after manual upload.

Deploy workflow:
  Read deploy.py before use. It is specific to this deployment and uses a
  staged archive plus site-manifest.json. Inspect existing services first.
  Back up Nginx and capture service/config state before any change.
  Run nginx -t before a graceful reload. Never restart VPN services.
  Run verify.py with the captured state-before.json and inspect its report.
  The temporary Range probe is removed by an exact-path cleanup.

Backups and reports are under /root/freedom-gpt-deploy (root-only), outside
the public web root. Nginx backups can contain private profile locations;
do not publish or copy them into the repository or website.

Rollback of this website:
  Point current at a preserved previous Freedom GPT release, if available.
  To remove only this site, unlink its exact sites-enabled/freedom-gpt.conf
  link after checking its resolved target. Validate nginx -t, then reload.
  Preserve shared models, all existing vhosts and VPN configuration.
  A root-only timestamped Nginx backup was created before first deployment.

Verification limitation:
  iptables-save exports live packet/byte counters. A changed raw export hash
  is not itself a rule change. verify.py retains that observation, compares
  preserved firewall configuration hashes, and checks normalized current
  rule stability. It does not reconstruct an earlier raw rule export.

Upload instructions: ../../FILEZILLA-MODELS.txt
