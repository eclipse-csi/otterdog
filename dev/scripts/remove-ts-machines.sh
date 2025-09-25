#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

if [ -z "$TS_CLIENT_ID" ] || [ -z "$TS_CLIENT_SECRET" ] || [ -z "$TS_DNS" ]; then
  echo "Error: Required environment variables not set"
  echo "Please set: TS_CLIENT_ID, TS_CLIENT_SECRET, TS_DNS"
  exit 1
fi

echo "Getting access token..."
TOKEN_RESPONSE=$(curl -s -X POST https://api.tailscale.com/api/v2/oauth/token \
  -d "client_id=${TS_CLIENT_ID}" \
  -d "client_secret=${TS_CLIENT_SECRET}" \
  -d "grant_type=client_credentials")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')

if [ "$ACCESS_TOKEN" == "null" ] || [ -z "$ACCESS_TOKEN" ]; then
  echo "Error: Failed to get access token"
  echo "Response: $TOKEN_RESPONSE"
  exit 1
fi

MACHINES=("otterdog.${TS_DNS}" "sbom.${TS_DNS}" "tailscale-operator.${TS_DNS}")


echo "Fetching device list..."
DEVICES=$(curl -s "https://api.tailscale.com/api/v2/tailnet/${TS_DNS}/devices" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")


for MACHINE in "${MACHINES[@]}"; do
  echo "Looking for machine: ${MACHINE}"


  DEVICE_ID=$(echo "$DEVICES" | jq -r ".devices[] | select(.hostname == \"${MACHINE}\" or .name == \"${MACHINE}\") | .id")

  if [ -z "$DEVICE_ID" ] || [ "$DEVICE_ID" == "null" ]; then
    echo "  Machine ${MACHINE} not found"
    continue
  fi

  echo "  Found device ID: ${DEVICE_ID}"
  echo "  Removing ${MACHINE}..."

  curl -s -X DELETE \
    "https://api.tailscale.com/api/v2/device/${DEVICE_ID}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}"

  echo "  ✓ Removed ${MACHINE}"
done

echo "Done!"
