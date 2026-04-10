#!/bin/bash
set -euo pipefail

# Deploy the Safeguard validator stack to GKE.
# This deploys vali-django + demo-client ONLY.
# The miner is a separate project with its own deployment.

REGISTRY="us-central1-docker.pkg.dev/safeguard-testnet/safeguard"
REGION="us-central1"
PROJECT="safeguard-testnet"

echo "=== Authenticating Docker to Artifact Registry ==="
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

echo "=== Building and pushing images ==="
docker buildx build --platform linux/amd64 -t ${REGISTRY}/vali-django:latest --push ./vali-django
docker buildx build --platform linux/amd64 -t ${REGISTRY}/demo-client:latest --push ../safeguard-demo-client

echo "=== Getting cluster credentials ==="
gcloud container clusters get-credentials safeguard-cluster \
  --region=${REGION} --project=${PROJECT}

echo "=== Creating namespace ==="
kubectl apply -f k8s/namespace.yaml

echo "=== Checking secrets ==="
kubectl get secret safeguard-secrets -n safeguard 2>/dev/null || {
  echo "ERROR: secrets not found. Run: bash k8s/create-secrets.sh"
  exit 1
}

echo "=== Deploying ==="
kubectl apply -f vali-django/k8s/deployment.yaml
kubectl apply -f ../safeguard-demo-client/k8s/deployment.yaml

echo "=== Waiting for rollout ==="
kubectl rollout status deployment/vali-django -n safeguard --timeout=120s
kubectl rollout status deployment/demo-client -n safeguard --timeout=120s

echo "=== Status ==="
kubectl get pods -n safeguard
echo ""
echo "Dashboard: kubectl port-forward svc/vali-django 9080:9090 -n safeguard"
