#!/usr/bin/env bash
set -euo pipefail
api="${API_URL:-http://localhost:8080}"
echo "[1/4] API health"
curl -fsS "$api/health"
echo
echo "[2/4] Create offline-compatible job"
body=$(curl -fsS -X POST "$api/jobs" -H 'Content-Type: application/json' -d '{"topic":"AI ในโรงพยาบาล","language":"th","target_seconds":20}')
job_id=$(printf '%s' "$body" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
test -n "$job_id"
echo "job=$job_id"
echo "[3/4] Wait for worker (max 8 minutes)"
for _ in $(seq 1 96); do
  state=$(curl -fsS "$api/jobs/$job_id")
  status=$(printf '%s' "$state" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
  echo "status=$status"
  if [ "$status" = completed ]; then break; fi
  if [ "$status" = failed ]; then printf '%s\n' "$state"; exit 1; fi
  sleep 5
done
test "$status" = completed
echo "[4/4] Pipeline passed"
printf '%s\n' "$state"

