#!/bin/bash
set -euo pipefail

# Create k8s secrets from local wallet files.
# Wallet files are mounted into containers at /root/.bittensor/wallets/<name>/hotkeys/<hotkey>

WALLETS_DIR="${HOME}/.bittensor/wallets"

echo "=== Creating namespace ==="
kubectl apply -f k8s/namespace.yaml

echo "=== Creating shared secrets ==="
kubectl create secret generic safeguard-secrets \
  --namespace=safeguard \
  --from-literal=chutes-api-key="$(grep CHUTES_API_KEY vali-django/.env | cut -d= -f2 | tr -d '\"')" \
  --from-literal=django-secret-key="$(openssl rand -hex 32)" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== Creating wallet secrets ==="
# Each wallet secret holds the hotkey file and coldkeypub.
# The Deployment volumeMount + subPath reconstructs the directory structure.

# SuperPractice (validator)
kubectl create secret generic wallet-superpractice \
  --namespace=safeguard \
  --from-file=hotkey="${WALLETS_DIR}/SuperPractice/hotkeys/default" \
  --from-file=coldkeypub.txt="${WALLETS_DIR}/SuperPractice/coldkeypub.txt" \
  --dry-run=client -o yaml | kubectl apply -f -

# miner2 (safeguard-miner)
kubectl create secret generic wallet-miner2 \
  --namespace=safeguard \
  --from-file=hotkey="${WALLETS_DIR}/miner2/hotkeys/default" \
  --from-file=coldkeypub.txt="${WALLETS_DIR}/miner2/coldkeypub.txt" \
  --dry-run=client -o yaml | kubectl apply -f -

# SafeGuardOwner (demo-client)
kubectl create secret generic wallet-safeguardowner \
  --namespace=safeguard \
  --from-file=hotkey="${WALLETS_DIR}/SafeGuardOwner/hotkeys/default" \
  --from-file=coldkeypub.txt="${WALLETS_DIR}/SafeGuardOwner/coldkeypub.txt" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== Done ==="
kubectl get secrets -n safeguard
