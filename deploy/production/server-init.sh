#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  if curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc; then
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
    if apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
      :
    else
      rm -f /etc/apt/sources.list.d/docker.list
      apt-get update
      apt-get install -y docker.io docker-compose-v2
    fi
  else
    apt-get install -y docker.io docker-compose-v2
  fi
fi

systemctl enable --now docker

mkdir -p /opt/world-cup-prediction

echo "Docker version:"
docker --version
docker compose version
