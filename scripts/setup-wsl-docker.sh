#!/usr/bin/env bash
# One-time dev setup on Ubuntu (incl. WSL2): Docker Engine + Compose + Buildx,
# and the NVIDIA Container Toolkit so containers can use the GPU.
# Follows docs.docker.com/engine/install/ubuntu and NVIDIA's container-toolkit
# install guide. Needs sudo. Safe to re-run.
set -euo pipefail

codename=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")

echo "== Docker Engine ($codename)"
sudo apt-get update
sudo apt-get install -y ca-certificates curl gpg
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"

if command -v nvidia-smi >/dev/null; then
  echo "== NVIDIA Container Toolkit"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
else
  echo "== nvidia-smi not found: skipping GPU support (use the cpu profile or an external LLM_BASE_URL)"
fi

sudo systemctl enable --now docker
sudo systemctl restart docker

echo
echo "== Checks (run via sudo because the docker group applies from your next login)"
sudo docker run --rm hello-world | grep -m1 "Hello from Docker"
sudo docker compose version
if command -v nvidia-smi >/dev/null; then
  sudo docker run --rm --gpus all ubuntu nvidia-smi --query-gpu=name,memory.total --format=csv
fi
echo "Done. Open a new terminal (or restart WSL) so 'docker' works without sudo."
