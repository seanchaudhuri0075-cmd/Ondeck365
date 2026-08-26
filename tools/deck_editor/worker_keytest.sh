#!/bin/bash
# ---------------------------------------------------------------------------
# worker_keytest.sh — does the deck-media Worker accept a TWO-SEGMENT key?
#
# The editor now uploads to  <slug>/<build-id>/<file>  instead of  <slug>/<file>
# (commit e47ed5a). Everything about that was verified against a local mock
# Worker, which accepts any path. The real Worker is unverified.
#
# This writes exactly ONE 26-byte text file under a junk prefix and reads it
# back. It touches no deck, no real slug, and nothing that any published HTML
# points at.
#
# Nothing is stored: the Worker URL and token are read into shell variables
# with `read -s`, never written to disk, never echoed, and never placed in an
# argument (so they do not appear in `ps` or in shell history).
# ---------------------------------------------------------------------------
set -u

JUNK_SLUG="zz-throwaway-keytest"
BUILD_ID="$(date -u +%Y%m%d-%H%M%S)-test"
KEY="$JUNK_SLUG/$BUILD_ID/keytest.txt"

echo "=============================================================="
echo " Worker two-segment key test"
echo "=============================================================="
echo " Will upload ONE file to the key:"
echo "   $KEY"
echo
echo " Nothing else is touched. This prefix is junk and collides with"
echo " nothing: olay, olay-v2, oldspicepackaging, hh-creativestrategy,"
echo " pgdigital, venus-hestia."
echo

# --- credentials, never persisted -----------------------------------------
printf "Worker URL (no trailing slash, no /upload): "
read -r WORKER_URL
printf "Auth Token (hidden, press Enter if none): "
read -rs AUTH_TOKEN
echo; echo

if [ -z "$WORKER_URL" ]; then echo "No Worker URL given. Stopping."; exit 1; fi
WORKER_URL="${WORKER_URL%/}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PAYLOAD="$TMP/keytest.txt"
printf 'ondeck two-segment key ok\n' > "$PAYLOAD"
SENT_BYTES=$(wc -c < "$PAYLOAD" | tr -d ' ')

# --- 1. upload -------------------------------------------------------------
echo "STEP 1 — uploading..."
if [ -n "$AUTH_TOKEN" ]; then
  RESP=$(curl -sS -w '\n__HTTP__%{http_code}' -X POST "$WORKER_URL/upload" \
    -H "X-Auth-Token: $AUTH_TOKEN" \
    -F "file=@$PAYLOAD;filename=keytest.txt" \
    -F "path=$KEY" 2>&1)
else
  RESP=$(curl -sS -w '\n__HTTP__%{http_code}' -X POST "$WORKER_URL/upload" \
    -F "file=@$PAYLOAD;filename=keytest.txt" \
    -F "path=$KEY" 2>&1)
fi
CODE="${RESP##*__HTTP__}"
BODY="${RESP%$'\n'__HTTP__*}"
echo "  HTTP $CODE"
echo "  body: $BODY"
echo

if [ "$CODE" != "200" ]; then
  echo "RESULT: ✗ FAIL — upload rejected (HTTP $CODE)."
  echo "  A two-segment key is NOT accepted, or auth/URL is wrong."
  echo "  Re-run with a single-segment path to tell those apart."
  exit 2
fi

# --- 2. did it return a URL, and does that URL keep BOTH segments? ---------
# -E: BSD sed (macOS) has no \| alternation in basic regex; extended does.
URL=$(printf '%s' "$BODY" | sed -E -n 's/.*"(url|publicUrl)"[[:space:]]*:[[:space:]]*"([^"]*)".*/\2/p')
if [ -z "$URL" ]; then
  echo "RESULT: ✗ FAIL — 200 but no url/publicUrl in the response."
  exit 2
fi
echo "STEP 2 — returned URL:"
echo "  $URL"
KEEPS_BOTH=no
case "$URL" in *"$JUNK_SLUG/$BUILD_ID/keytest.txt"*) KEEPS_BOTH=yes ;; esac
echo "  keeps both segments: $KEEPS_BOTH"
echo

# --- 3. read it back -------------------------------------------------------
echo "STEP 3 — fetching it back..."
GET=$(curl -sS -o "$TMP/back.txt" -w '%{http_code}' "$URL")
echo "  HTTP $GET"
GOT_BYTES=0
[ -f "$TMP/back.txt" ] && GOT_BYTES=$(wc -c < "$TMP/back.txt" | tr -d ' ')
MATCH=no
if [ "$GET" = "200" ] && cmp -s "$PAYLOAD" "$TMP/back.txt"; then MATCH=yes; fi
echo "  bytes sent $SENT_BYTES / received $GOT_BYTES / identical: $MATCH"
echo

# --- verdict ---------------------------------------------------------------
echo "=============================================================="
if [ "$KEEPS_BOTH" = "yes" ] && [ "$MATCH" = "yes" ]; then
  echo " RESULT: ✓ PASS — two-segment keys work."
  echo " The <slug>/<build-id>/ layout is safe. Proceed with deck 9."
elif [ "$KEEPS_BOTH" = "no" ] && [ "$MATCH" = "yes" ]; then
  echo " RESULT: ✗ FAIL — the Worker FLATTENED the path."
  echo " It stored the file but dropped a segment, so every build would"
  echo " land on the same key and overwrite. Do NOT use <slug>/<build-id>/;"
  echo " the namespacing has to move into the FILENAME instead."
else
  echo " RESULT: ✗ FAIL — stored but not readable back at the returned URL."
  echo " HTTP $GET, bytes identical: $MATCH"
fi
echo "=============================================================="
echo
echo " Leftover: one $SENT_BYTES-byte object at"
echo "   $KEY"
echo " Harmless. Delete it from the Cloudflare R2 dashboard when convenient —"
echo " the editor has no delete function. Paste the block above to Claude."
