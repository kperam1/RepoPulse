#!/usr/bin/env bash
set -euo pipefail

: "${INFLUX_URL:?Set INFLUX_URL (e.g. http://localhost:8086)}"
: "${INFLUX_INIT_TOKEN:?Set INFLUX_INIT_TOKEN}"
: "${INFLUX_ORG:?Set INFLUX_ORG}"
: "${INFLUX_BUCKET:?Set INFLUX_BUCKET}"
: "${INFLUX_RETENTION_DAYS:=120}"

RETENTION_SECONDS=$(( INFLUX_RETENTION_DAYS * 86400 ))

echo "=== InfluxDB Retention Manager ==="
echo "URL:       $INFLUX_URL"
echo "Org:       $INFLUX_ORG"
echo "Bucket:    $INFLUX_BUCKET"
echo "Retention: ${INFLUX_RETENTION_DAYS}d (${RETENTION_SECONDS}s)"
echo ""

BUCKET_JSON=$(curl -s \
  --header "Authorization: Token ${INFLUX_INIT_TOKEN}" \
  "${INFLUX_URL}/api/v2/buckets?org=${INFLUX_ORG}&name=${INFLUX_BUCKET}")

BUCKET_ID=$(echo "$BUCKET_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
buckets = data.get('buckets', [])
if buckets:
    print(buckets[0]['id'])
else:
    sys.exit(1)
" 2>/dev/null) || {
  echo "ERROR: Bucket '${INFLUX_BUCKET}' not found in org '${INFLUX_ORG}'."
  echo "Response: $BUCKET_JSON"
  exit 1
}

echo "Bucket ID: $BUCKET_ID"

CURRENT_RETENTION=$(echo "$BUCKET_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
rules = data['buckets'][0].get('retentionRules', [])
if rules:
    secs = rules[0].get('everySeconds', 0)
    if secs == 0:
        print('infinite')
    else:
        print(f'{secs}s ({secs // 86400}d)')
else:
    print('none')
")

echo "Current retention: $CURRENT_RETENTION"
echo ""
echo "Updating retention to ${INFLUX_RETENTION_DAYS}d ..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  --request PATCH \
  --header "Authorization: Token ${INFLUX_INIT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "{
    \"retentionRules\": [{
      \"type\": \"expire\",
      \"everySeconds\": ${RETENTION_SECONDS}
    }]
  }" \
  "${INFLUX_URL}/api/v2/buckets/${BUCKET_ID}")

if [ "$HTTP_CODE" = "200" ]; then
  echo "SUCCESS: Retention updated to ${INFLUX_RETENTION_DAYS}d."
else
  echo "FAILED: HTTP $HTTP_CODE. Check credentials and bucket config."
  exit 1
fi

echo ""
echo "Verifying ..."

VERIFY_JSON=$(curl -s \
  --header "Authorization: Token ${INFLUX_INIT_TOKEN}" \
  "${INFLUX_URL}/api/v2/buckets/${BUCKET_ID}")

VERIFY_RETENTION=$(echo "$VERIFY_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
rules = data.get('retentionRules', [])
if rules:
    secs = rules[0].get('everySeconds', 0)
    print(f'{secs}s ({secs // 86400}d)')
else:
    print('none')
")

echo "Verified retention: $VERIFY_RETENTION"
echo "Done."
