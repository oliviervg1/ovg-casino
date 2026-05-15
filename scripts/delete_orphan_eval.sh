#!/usr/bin/env bash
# One-shot cleanup of the placeholder Welcome & Recommend Slots eval
# left on prod after Phase B (cxas push doesn't propagate eval
# deletions — push-eval is upsert-only). Phase C ships proper Goldens
# in evals/goldens/, but the orphan from before still sits on prod
# until something deletes it.
#
# Run once and never again. Kept in scripts/ for discoverability so
# future readers see "we had to delete an orphan eval once" and find
# the script and the API recipe.
#
# Hostname: ces.googleapis.com (verified by reading
# cxas_scrapi/core/common.py:_get_client_options — cxas uses the same
# endpoint regardless of the app's location).
set -euo pipefail

PROJECT="bigquery-demo-396708"
LOCATION="us"
APP_ID="c4242f9c-3b93-4c92-a69c-a035daabc0c8"
DISPLAY_NAME="Welcome & Recommend Slots"

API_HOST="ces.googleapis.com"
APP_PATH="projects/${PROJECT}/locations/${LOCATION}/apps/${APP_ID}"
TOKEN="$(gcloud auth print-access-token)"

# Find the eval resource by display name.
echo "Listing evaluations on $APP_PATH..."
LIST_URL="https://${API_HOST}/v1beta/${APP_PATH}/evaluations"
EVAL_NAME=$(curl -s -H "Authorization: Bearer $TOKEN" "$LIST_URL" \
  | jq -r --arg name "$DISPLAY_NAME" \
      '.evaluations[]? | select(.displayName==$name) | .name')

if [ -z "$EVAL_NAME" ] || [ "$EVAL_NAME" = "null" ]; then
  echo "Eval '$DISPLAY_NAME' not found — already deleted or never existed. Nothing to do."
  exit 0
fi

echo "Deleting: $EVAL_NAME"
DELETE_URL="https://${API_HOST}/v1beta/$EVAL_NAME"
curl -fsS -X DELETE -H "Authorization: Bearer $TOKEN" "$DELETE_URL"

echo ""
echo "Verifying deletion..."
sleep 2
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$DELETE_URL")

if [ "$RESPONSE" = "404" ]; then
  echo "Confirmed deleted (404)."
  exit 0
fi

echo "Unexpected response code: $RESPONSE — check manually."
exit 1
