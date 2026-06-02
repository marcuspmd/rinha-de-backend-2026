# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is the **official repository for Rinha de Backend 2026**, a friendly competition where participants build a fraud detection backend under strict resource constraints (1 CPU, 350 MB RAM total). The repo contains:
- The challenge specification (`docs/`)
- Reference data files (`resources/`)
- A k6-based test suite (`test/`)
- Participant registration files (`participants/`)

Participants submit their own backends in separate repositories — this repo is the contest infrastructure, not a participant's solution.

## Running the test suite locally

The test suite uses [k6](https://k6.io/) and requires the participant's backend to be running at `http://localhost:9999` beforehand.

```bash
# Full test (generates test/results.json)
./run.sh

# Using docker compose (from the test/ directory)
docker compose --profile test up      # full test
docker compose --profile smoke up     # quick smoke test
```

The `run.sh` script invokes k6 and pipes results through `jq`. Results are written to `test/results.json`.

## Regenerating test data

```bash
./generate-data.sh
```

This regenerates `test/test-data.json` using the pre-built `data-generator/generate` binary, reusing the existing `resources/references.json.gz`.

## Building the data generator

The data generator is written in C and lives in `data-generator/`:

```bash
cd data-generator && make
```

## Publishing test results (CI/engine use)

```bash
./post-run.sh <participant> <repo-url> <submission-id> <commit> [issue-number]
# submission-id can be "default" to resolve from participants/<participant>.json
```

## Architecture of a valid participant submission

Each participant's `submission` branch must contain a `docker-compose.yml` with:
- At least **one load balancer** and **two API instances** (simple round-robin)
- Total resource limits: **≤ 1 CPU, ≤ 350 MB** across all services
- Load balancer on port **9999**
- Network mode: `bridge` (no `host` or `privileged`)
- All images publicly available and `linux/amd64`-compatible

## The fraud detection algorithm (what participants must implement)

**Endpoint:** `POST /fraud-score`, `GET /ready` on port 9999.

**Flow for each request:**
1. Vectorize the transaction payload into **14 float dimensions** (see `docs/en/DETECTION_RULES.md`)
2. Find the **5 nearest neighbors** in `resources/references.json.gz` (3M pre-labeled vectors)
3. Return `fraud_score = fraud_count / 5`, `approved = fraud_score < 0.6`

**Vector dimensions (in order):**

| idx | field | formula |
|-----|-------|---------|
| 0 | `amount` | `clamp(amount / 10000)` |
| 1 | `installments` | `clamp(installments / 12)` |
| 2 | `amount_vs_avg` | `clamp((amount / avg_amount) / 10)` |
| 3 | `hour_of_day` | `hour(requested_at_UTC) / 23` |
| 4 | `day_of_week` | `day_of_week(requested_at_UTC) / 6` (mon=0) |
| 5 | `minutes_since_last_tx` | `clamp(minutes / 1440)` or **`-1`** if no last transaction |
| 6 | `km_from_last_tx` | `clamp(km / 1000)` or **`-1`** if no last transaction |
| 7 | `km_from_home` | `clamp(km_from_home / 1000)` |
| 8 | `tx_count_24h` | `clamp(tx_count_24h / 20)` |
| 9 | `is_online` | 1 or 0 |
| 10 | `card_present` | 1 or 0 |
| 11 | `unknown_merchant` | 1 if merchant.id not in known_merchants, else 0 |
| 12 | `mcc_risk` | lookup in `mcc_risk.json`, default 0.5 |
| 13 | `merchant_avg_amount` | `clamp(merchant.avg_amount / 10000)` |

The `-1` sentinel at indices 5 and 6 is the only value allowed outside `[0.0, 1.0]`. Do not filter or replace it — the reference dataset uses the same convention.

## Reference files

- `resources/references.json.gz` — 3M labeled vectors, format: `[{"vector": [...14 floats...], "label": "fraud"|"legit"}, ...]`
- `resources/mcc_risk.json` — MCC → risk score (0.0–1.0) map
- `resources/normalization.json` — normalization constants
- `resources/example-payloads.json` — sample request payloads
- `resources/example-references.json` — small uncompressed excerpt of the references dataset

These files **do not change during the test** — participants should pre-process/index them at build or startup time.

## Scoring

`final_score = score_p99 + score_det` (each ranges −3000 to +3000, max total +6000)

- **Latency (`score_p99`):** logarithmic, every 10× faster = +1000 pts. Cutoff: p99 > 2000ms → −3000.
- **Detection (`score_det`):** weighted errors `E = 1·FP + 3·FN + 5·Err`. Cutoff: failure rate > 15% → −3000.

HTTP errors have the worst weight (5×). If the backend is failing, returning `{"approved": true, "fraud_score": 0.0}` (FP, weight 1) is better than returning HTTP 500 (Err, weight 5).

## Participant registration

To add or update a participant, add/modify a JSON file in `participants/<github-username>.json`:

```json
[{
    "id": "my-submission-id",
    "repo": "https://github.com/username/repo"
}]
```

## Submission deadline

**2026-06-05T23:59:59.999-03:00** — final deadline for the `submission` branch.
