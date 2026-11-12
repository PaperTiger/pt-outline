# pt-outline server

Dedicated DigitalOcean droplet for Paper Tiger's Outline workspace at https://papertiger.agency. Kept apart from `pt-utility` on purpose (see the Decisions log in `outline-setup-spec.md`).

Created Nov 12, 2026 by Claude Code.

## Basics

| Item | Value |
|---|---|
| Name | `pt-outline` |
| Droplet ID | `618508842` |
| Public IP | `64.225.7.247` |
| Private IP (VPC) | `10.132.0.5` |
| Region | `nyc3`, VPC `957278cb-dc84-11e8-80bc-3cfdfea9fba1` |
| Size | `s-1vcpu-2gb`: 1 vCPU, 2 GB RAM, 50 GB disk (about $12/month) |
| OS | Ubuntu 24.04.5 LTS |
| Hostname | `pt-outline` |
| Time zone | UTC |
| Swap | 2 GB at `/swapfile`, swappiness 10 |
| Tag | `INTERNAL` |
| Monitoring | On |
| Droplet backups | On (about $2.40/month). This droplet holds live data |
| DNS | `papertiger.agency` A record → `64.225.7.247`, TTL 300, in DigitalOcean DNS |

## Access

- SSH key: `mac-mini-marc` (DigitalOcean key ID `59935487`), `~/.ssh/id_ed25519` on Marc's Mac. It has a passphrase, so load it first:
  ```bash
  ssh-add --apple-use-keychain ~/.ssh/id_ed25519
  ```
- Connect: `ssh root@64.225.7.247`
- Key-only SSH: password login off, root by key only (`/etc/ssh/sshd_config.d/99-pt-hardening.conf`)
- Security updates install automatically (`unattended-upgrades`)

## Firewall

DigitalOcean cloud firewall `pt-outline-fw` (ID `cb702907-be45-485d-b81d-42cec0afafed`):
- Inbound: TCP 22, 80, 443
- Outbound: everything

## How it runs

| Piece | Where |
|---|---|
| Outline `1.12.0` | Docker, `/opt/outline/docker-compose.yml`, bound to `127.0.0.1:3000` only |
| Postgres 16, Redis 7 | Docker, same compose file, named volumes `outline_pgdata` and `outline_redisdata` |
| Caddy (TLS, reverse proxy) | On the host, `/etc/caddy/Caddyfile` (copy of `Caddyfile` in this repo). Let's Encrypt certificate renews itself |
| Uploads | Spaces bucket `pt-outline` (nyc3, standard, private, CDN off). CORS allows `https://papertiger.agency` only |
| Email | Google Workspace SMTP relay (`smtp-relay.gmail.com:587`, IP-authenticated), from `noreply@papertiger.com` |
| Sign-in | Google only |

Upgrade Outline: change the image tag in `docker-compose.yml`, copy it to `/opt/outline`, then `cd /opt/outline && docker compose pull && docker compose up -d`. Run a backup first.

## Secrets

All in `/opt/outline/.env` (mode 600, never committed). Internal secrets (`SECRET_KEY`, `UTILS_SECRET`, `POSTGRES_PASSWORD`) were generated on the server by `bin/init-env.sh` and have never left it. Google OAuth and Spaces keys were copied from Marc's Mac `.env` (also mode 600, git-ignored).

To change one, run `set-secret` from a real terminal (not the Claude Code `!` prompt, which has no TTY):
```bash
ssh -t root@64.225.7.247 /opt/outline/bin/set-secret NAME
```
Then `cd /opt/outline && docker compose up -d`.

## Scripts (`/opt/outline/bin`)

| Script | Does |
|---|---|
| `init-env.sh` | Writes fixed settings into `.env`, generates internal secrets once. Safe to re-run |
| `set-secret NAME` | Prompts for a value without echoing it and replaces that line in `.env` |
| `s3 …` | AWS CLI against the `pt-outline` bucket with the key from `.env` |
| `backup.sh` | Dumps Postgres, uploads to `s3://pt-outline/backups/` |
| `restore-test.sh` | Restores the newest backup into a scratch database, compares row counts, drops it |

## Jobs

| Job | Schedule | Log |
|---|---|---|
| `outline-backup.timer` → `backup.sh` | Daily 07:00 UTC (2am Eastern), up to 10 min jitter | `/opt/outline/logs/backup.log` |

Backups expire after 30 days via the bucket lifecycle rule `expire-backups-30d` (prefix `backups/`).

## Setup log

- 2026-11-12: Droplet and firewall created. Base setup (Docker, Caddy, git, jq, Postgres client, AWS CLI via snap, swap, SSH hardening). Rebooted; SSH confirmed
- 2026-11-12: First run of base setup hit the apt lock held by Ubuntu's first-boot updater. Script now waits for the lock
- 2026-11-12: Outline 1.12.0, Postgres and Redis deployed. Caddy issued the Let's Encrypt certificate once the A record resolved
- 2026-11-12: Marc signed in as the first user (workspace admin)
- 2026-11-12: Spaces bucket, CORS and lifecycle set. First backup taken and restore proven (counts matched)
- 2026-11-12: The first Spaces key had full access to every bucket. Marc regenerated `outline-11122026` as `bucket=pt-outline;permission=readwrite`. Confirmed it can't read other buckets
- 2026-11-12: Backup script now deletes its local dump even when the upload fails
- 2026-11-12: Workspace renamed "Paper Tiger", allowed domain set to `papertiger.com`, email (magic link) sign-in turned off. Google is the only sign-in method
