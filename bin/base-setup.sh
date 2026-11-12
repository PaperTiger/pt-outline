#!/usr/bin/env bash
# Base setup for pt-outline (Ubuntu 24.04). Safe to re-run.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

hostnamectl set-hostname pt-outline
timedatectl set-timezone UTC

apt-get -o DPkg::Lock::Timeout=900 update
apt-get -o DPkg::Lock::Timeout=900 -y -o Dpkg::Options::=--force-confold upgrade
apt-get -o DPkg::Lock::Timeout=900 install -y ca-certificates curl gnupg git jq unattended-upgrades debian-keyring debian-archive-keyring apt-transport-https postgresql-client-16 awscli || apt-get install -y ca-certificates curl gnupg git jq unattended-upgrades debian-keyring debian-archive-keyring apt-transport-https postgresql-client-16

# Docker (official apt repo)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list

# Caddy (official apt repo)
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list

apt-get -o DPkg::Lock::Timeout=900 update
apt-get -o DPkg::Lock::Timeout=900 install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin caddy
systemctl enable --now docker

# Automatic security updates
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'X'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
X

# Swap 2G, swappiness 10
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
sysctl -p /etc/sysctl.d/99-swappiness.conf

# SSH hardening
cat > /etc/ssh/sshd_config.d/99-pt-hardening.conf <<'X'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
X
sshd -t && systemctl reload ssh

mkdir -p /opt/outline/bin /opt/outline/logs
echo "BASE SETUP DONE"
