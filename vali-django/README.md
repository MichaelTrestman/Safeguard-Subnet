# vali-django

Ground-up rewrite of the Safeguard validator + customer portal as a single
Django ASGI app. Replaces the `validator.py` / `dashboard.py` split with one
process so the operator UI can give an honest answer to *"did I just set
weights?"* — same process, same memory, no stale jsonl files.

This project does **not** modify the existing `safeguard/validator.py` or
`safeguard/dashboard.py`. They keep running until this is proven, then they
get deleted.

---

## Why this exists

The Safeguard subnet on testnet 444 had a near-miss: `validator.py` crashed,
nobody noticed for hours, and a competing hotkey could have captured ~82% of
emissions if a friendly operator hadn't pointed it out. Yuma consensus does
not defend against an absent validator — it only defends against a
*disagreeing* one. The fixes split into two layers:

1. **Restart-the-process layer** (this app, plus k8s). One process owns the
   chain loop AND the operator UI, so the dashboard cannot lie about
   liveness. If the loop dies the pod dies and k8s restarts it.

2. **Don't-be-the-only-validator layer** (out of scope for this app, but
   unblocked by it). Run a second instance with a *different* hotkey. That
   is the actual Yuma defense; k8s uptime is just the prerequisite.

---

## Design

### Decentralized validator note

Safeguard is a decentralized subnet — every validator in the community runs
their own instance of this app. There is no shared global state. Each
validator has:

- their own DB (sqlite locally, Postgres in prod)
- their own copy of the registered-target list
- their own evaluation history and miner-score state

The fact that two validators may converge on similar miner weights is a
property of Yuma consensus, not of any cross-instance coordination in this
codebase. **Do not add features that assume a global view.**

Local resources currently scattered across yaml/json files in `safeguard/`
(target configs, canaries, target registry) will migrate into the
per-instance DB over time. For now, anything seeded from disk should be
loaded once at startup into the DB and then read from the DB.

### One process, two audiences

- **Operator UI** (you, the validator runner) — `/` and `/targets/<name>/`,
  HTML pages backed by a `ValidatorStatus` singleton row that the
  background loop updates every iteration. This is what tells you the chain
  loop is alive and setting weights.

- **Customer portal** (other subnets consuming the safety-eval service) —
  `/register`, `/evaluate`, `/status/<hk>`, `/registry`, all authed with
  Epistula signatures. The customer's hotkey *is* their identity; there is
  no separate Django user model.

### Background validator loop

Started by the ASGI **lifespan handler** in `valiproject/asgi.py`, not by
`AppConfig.ready()`. This is deliberate:

- `manage.py runserver` is WSGI → loop does **not** start. Dev server is
  for poking views, not for running the validator.
- `uvicorn valiproject.asgi:application --lifespan on` is ASGI → loop
  starts. This is the real entrypoint.

The loop is a single asyncio task. No threads. No `os.execv` self-restart
(the pattern in `safeguard/validator.py` is deliberately **not** ported).
Per-iteration errors are caught and recorded on `ValidatorStatus`; an
unrecoverable error (e.g. wallet load fails) re-raises, the lifespan task
dies, the process exits, and k8s restarts the pod. **One owner of restarts:
k8s.**

### Honest `/healthz`

Liveness probe returns 503 if any of:

- `wallet_loaded` is false
- `last_tick_at` is older than `HEALTH_MAX_TICK_AGE_S` (default 120s) —
  loop is wedged
- `last_set_weights_at` is older than `HEALTH_MAX_WEIGHT_AGE_S`
  (default 1800s = 30 min) — loop is alive but failing to submit weights

We deliberately do **not** fail when `last_set_weights_at` is None. That's
the warmup window before the first weight-set; tick staleness is the
early-warning indicator that catches a wedged loop in that window.

A red `/healthz` means k8s restarts the pod, which is the right move.

### Wallet loading

The user's mandate: *"just read the effing file bro."*

```
VALIDATOR_WALLET=<coldkey-name>
VALIDATOR_HOTKEY=<hotkey-name>
```

`validator/wallet.py` resolves `~/.bittensor/wallets/<VALIDATOR_WALLET>/hotkeys/<VALIDATOR_HOTKEY>`
directly, verifies the file exists, then hands the names to
`bittensor_wallet.Wallet(name=..., hotkey=...)`. No env-var indirection
inside the bittensor library. No surprises about which wallet got loaded.

In k8s, `~/.bittensor` is a mounted Secret. Same code path locally and in
production.

### State: DB, not files

All the file-based state in `safeguard/` becomes Django models:

| Old (file)                  | New (model)         |
|-----------------------------|---------------------|
| `target_registry.json`      | `RegisteredTarget`  |
| `evaluation_log.jsonl`      | `Evaluation`        |
| (extracted findings)        | `Finding`           |
| `hitl_escalations.jsonl`    | `HitlCase`          |
| `miner_scores.json`         | `MinerScore`        |
| *(no equivalent)*           | `ValidatorStatus`   |

`ValidatorStatus` is the new piece: a singleton row (pk=1) that the
background loop updates each iteration with `last_tick_at`,
`loop_iteration`, `last_set_weights_at`, `last_chain_error`, etc. The
operator UI and `/healthz` both read this. Same DB, same transaction
semantics, no jsonl-staleness.

### Epistula auth

`validator/epistula.py` is a `sys.path` shim that re-exports
`verify_epistula` and `create_epistula_headers` from the existing
`safeguard/epistula.py` so we don't fork the implementation. When this
project graduates and the old tree goes away, copy the module in and delete
the shim.

### k8s deployment shape

- **`replicas: 1`** with **`strategy: Recreate`**. Two pods sharing one
  wallet would double-submit `set_weights`. If you want a hot standby, run
  a *second* Deployment with a *different* hotkey, not a second replica.
  This is the actual silence-capture defense.
- Wallets mounted as a Secret at `/root/.bittensor`. See
  `k8s/secret.example.yaml` for the create command.
- DB on a PVC at `/data`.
- `livenessProbe` and `readinessProbe` both on `/healthz`.
- No log files. Stdout only. k8s captures it, GCP logging picks it up.

---

## Run it locally

Verified to boot clean on macOS / Python 3.11+ with the steps below. The
background loop reaches the wallet, the operator dashboard renders, and
`/healthz` returns 200.

```bash
cd safeguard/vali-django

# 1. venv + install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. config
cp .env.example .env
# edit .env if your wallet/hotkey aren't SuperPractice/default

# 3. migrate
python manage.py makemigrations validator
python manage.py migrate

# 4. run (ASGI — background loop runs)
uvicorn valiproject.asgi:application --host 0.0.0.0 --port 9090 --lifespan on
```

Then:

- `http://localhost:9090/` — operator dashboard
- `http://localhost:9090/healthz` — liveness probe
- `http://localhost:9090/registry` — public list of registered targets

### Smoke-test it boots

```bash
curl -s http://localhost:9090/healthz
# {"status": "ok", "iteration": 1}
```

Look for these lines in stdout:

```
vali.asgi | INFO | Starting background validator loop
vali.loop | INFO | Validator loop starting (interval=12.0s)
vali.wallet | INFO | Loaded wallet SuperPractice/default → <ss58>...
```

If wallet loading fails the loop will refuse to start and `/healthz` will
go red. Check the error in the operator dashboard or in stdout.

---

## Run it in Docker

```bash
docker build -t vali-django:dev .
docker run --rm -p 9090:9090 \
  -e VALIDATOR_WALLET=SuperPractice \
  -e VALIDATOR_HOTKEY=default \
  -e SUBTENSOR_NETWORK=test \
  -e NETUID=444 \
  -v $HOME/.bittensor:/root/.bittensor:ro \
  -v $(pwd)/data:/data \
  vali-django:dev
```

Migrations run automatically at container start.

---

## Deploy to k8s

```bash
# 1. push the image
docker build -t <your-registry>/vali-django:0.1.0 .
docker push <your-registry>/vali-django:0.1.0
# update k8s/deployment.yaml `image:` line

# 2. create secrets (wallets are key material — do not put them in YAML)
kubectl create secret generic vali-django-secret \
  --from-literal=django-secret-key=$(openssl rand -hex 32)

kubectl create secret generic vali-django-wallets \
  --from-file=wallets/SuperPractice/coldkeypub.txt=$HOME/.bittensor/wallets/SuperPractice/coldkeypub.txt \
  --from-file=wallets/SuperPractice/hotkeys/default=$HOME/.bittensor/wallets/SuperPractice/hotkeys/default

# 3. apply
kubectl apply -f k8s/deployment.yaml
```

For "the little guy" deployment story, k3s on a single `e2-small` GCE VM is
~$13/month and uses an identical k8s API. Autopilot is ~$75/month minimum
and is overkill for one CPU pod.

---

## Layout

```
vali-django/
├── README.md                    # this file
├── pyproject.toml
├── Dockerfile
├── .env.example
├── manage.py
├── valiproject/                 # Django project
│   ├── settings.py              # sqlite default, DATABASE_URL → postgres
│   ├── urls.py
│   ├── wsgi.py                  # dev server only — does NOT run bg loop
│   └── asgi.py                  # lifespan handler owns the bg loop
├── validator/                   # Django app
│   ├── models.py                # all per-instance state lives here
│   ├── wallet.py                # ~/.bittensor wallet file resolution
│   ├── epistula.py              # sys.path shim → safeguard/epistula.py
│   ├── loop.py                  # background validator loop (STUB)
│   ├── views.py                 # customer portal + operator UI + /healthz
│   ├── urls.py
│   └── templates/validator/
│       ├── base.html
│       ├── operator_dashboard.html
│       └── target_detail.html
└── k8s/
    ├── deployment.yaml          # Deployment + Service + PVC
    └── secret.example.yaml      # how to mount wallets as a Secret
```

---

## Experiments (consistency-check mining)

Second mining task alongside adversarial probing. Operator creates an
`Experiment` row with a challenge claim, an optional consistency-check
claim, and a runs-per-trial count, then dispatches it to eligible probe
miners. Each miner's execution is a trial — an `Evaluation` row with an
`experiment` FK. The miner runs N independent relay sessions and returns
a structured report of factual contradictions; the validator verifies
provenance and confirms the cited text spans.

**New model.** `Experiment` in `validator/models.py`, with a `status`
field (`draft` / `running` / `completed` / `failed`), an `experiment_report`
JSON column on each trial, and a reverse FK from `Evaluation`.

**Operator UI.** `/operator/experiments/` — list, create form, per-miner trial
results with expandable consistency reports and session transcripts. An
**Inconsistencies** column on the list page is aggregated in Python from
each trial's `experiment_report` JSON (not SQL-annotatable) and highlights
any experiment with a nonzero count. A **Stuck** badge flags running
experiments with no trial activity for >10 min, and a **Reset to Draft**
button (also on the detail page) flips stuck/failed rows back to draft so
the operator can re-dispatch. A per-experiment `/operator/experiments/<slug>/timeline/`
page renders a read-only event log derived from DB state (creation,
dispatch start, per-trial landings, completion). The bare `/experiments/`,
`/experiments/<slug>/`, and `/targets/` paths are public anon-visible
showcase pages under `public/` — operator routes live under `/operator/*`
to avoid collision.

**Dispatch path.** `dispatch_experiment()` is called from the
`/operator/experiments/<id>/run/` view, **not** from the background validator loop.
The view is async — it awaits each miner's `/experiment` endpoint — and
blocks for the full duration of the dispatch. The main loop
(`validator/loop.py`) is untouched by this path. Async view gotchas (sync
auth decorators, FK traversal, fire-and-forget) are documented in the
safeguard-ops README's "Django async views" section.

**Database connection handling.** The experiment dispatch view makes
multiple `sync_to_async` ORM calls per request. Under concurrent
dispatches this bursts past Cloud SQL's connection ceiling on small
instance tiers. `settings.py` enables connection reuse via
`CONN_MAX_AGE=60` and `CONN_HEALTH_CHECKS=True`, tunable through the
`DB_CONN_MAX_AGE` env var. Don't set this back to 0 — Django's default
churns a connection per request, which will exhaust a db-f1-micro instance
at moderate concurrency. See dev-blog-012 for the stress-test details.

**Known gaps.** The consistency-audit branch in `_audit_one_evaluation`
doesn't yet persist its result — experiment trials currently show
`audit_score=None` and `contribution=0.0`, so they're not yet contributing
to mechid 0 weights. This is the top open follow-up. Zombie experiments
(pod restart during an in-flight dispatch) need a reaper; the manual
workaround is documented in the safeguard-ops README.

## Status: what's done, what's stubbed

### Done

- Project scaffold, settings, models, migrations
- ASGI lifespan handler that starts the background loop
- Wallet loading from `~/.bittensor/wallets/<w>/hotkeys/<h>`
- Customer portal endpoints: `/register`, `/evaluate`, `/status`, `/registry`
- Epistula auth on portal endpoints
- Operator dashboard + per-target detail page
- Honest `/healthz` (wallet + tick age + weight age)
- Dockerfile (single container, migrate + uvicorn)
- k8s manifest (Deployment + Service + PVC + Secret example)
- **Verified end-to-end**: venv install, migrate, uvicorn boot, wallet load,
  loop tick, healthz green, dashboard renders

### Stubbed — the next real piece of work

**`validator/loop.py`** is a stub. It loads the wallet, ticks the iteration
counter, records errors on `ValidatorStatus`, and sleeps. It does NOT yet
discover miners, dispatch probes, audit transcripts, update `MinerScore`,
or call `set_weights`.

The full completion + perfection plan — schema migrations, loop port
phases, dashboard upgrades, audit pipeline wiring, tests, layer-2 wallet
defense, legacy retirement — lives in [`PLAN.md`](./PLAN.md). Read that
top to bottom before starting any work on the loop body.
