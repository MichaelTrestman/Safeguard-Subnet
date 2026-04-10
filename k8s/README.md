# Safeguard Validator — GKE Deployment

Validator stack on GKE Autopilot: `safeguard-testnet` project, `us-central1`.

This deploys the **validator** and **demo-client** only. The miner is a
separate project (`safeguard-miner/`) with its own deployment — validators
and miners are independent parties.

## Services

| Service | Image | Port | Probes |
|---|---|---|---|
| vali-django | vali-django:latest | 9090 | /healthz |
| demo-client | demo-client:latest | 9180 | /healthz, /readyz |

## Setup

```bash
gcloud config set project safeguard-testnet
gcloud container clusters get-credentials safeguard-cluster --region=us-central1

cd safeguard/
bash k8s/create-secrets.sh   # first time only
bash k8s/deploy.sh           # build, push, deploy
```

## Dashboard

```bash
kubectl port-forward svc/vali-django 9080:9090 -n safeguard
# http://localhost:9080
```

## Logs

```bash
kubectl logs -f deploy/vali-django -n safeguard
kubectl logs -f deploy/demo-client -n safeguard
```

## Redeploy

```bash
REGISTRY="us-central1-docker.pkg.dev/safeguard-testnet/safeguard"
docker buildx build --platform linux/amd64 -t ${REGISTRY}/vali-django:latest --push ./vali-django
kubectl rollout restart deployment/vali-django -n safeguard
```

## Networking

Within the cluster, services find each other by DNS:
- Demo-client registers with validator at `http://vali-django:9090`
- Validator forwards relay calls to `http://demo-client:9180/relay`
- Miners connect from outside the cluster via public endpoints

## Secrets

| Secret | Contents |
|---|---|
| safeguard-secrets | chutes-api-key, django-secret-key |
| wallet-superpractice | Validator hotkey + coldkeypub |
| wallet-safeguardowner | Demo-client hotkey + coldkeypub |
