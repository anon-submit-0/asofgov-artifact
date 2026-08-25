#!/usr/bin/env bash
# fetch_and_rebuild.sh -- fetch the public source datasets from their OFFICIAL
# channels and rebuild the nine pilot2 warehouses + gov seeds + gold in-tree.
#
# This repository deliberately ships NO warehouse.duckdb and NO BIRD/Spider
# source data (licensing stays with the source distributors).  Everything
# derived is rebuilt deterministically from the official downloads:
#
#   step 1  BIRD dev set   -> data/bird/dev_20240627/dev_databases/<db>/<db>.sqlite
#           official page https://bird-bench.github.io/ ; the direct dev-set
#           link published there (verified 2026-08-04) is
#           https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip
#           sha256-checked against manifests/sha256_sources.txt.
#   step 2  Spider world_1 -> pilot/public/warehouse.duckdb  (legacy bridge)
#           Spider is distributed from https://yale-lily.github.io/spider
#           (Google Drive; no stable direct URL, so this step is manual:
#           download spider_data.zip, unzip, then pass
#           spider_data/database/world_1/world_1.sqlite).  The rebuilt bridge
#           is verified against a logical content hash of the frozen bridge.
#   step 3  python3 scripts/rebuild_portable.py
#           -> pilot2/domains/<db>/warehouse.duckdb  (9 DBs, ~1 GB)
#           -> gov_seed/*.jsonl + questions.json + provenance.json
#           and byte-checks every rebuilt frozen file against
#           pilot2/FREEZE_pilot2_arms.json.
#
# Usage:
#   ./fetch_and_rebuild.sh                     # all steps (step 2 needs
#                                              # SPIDER_WORLD1_SQLITE if the
#                                              # bridge is not built yet)
#   SPIDER_WORLD1_SQLITE=/path/world_1.sqlite ./fetch_and_rebuild.sh
#   BIRD_DEV_ZIP=/already/downloaded/dev.zip  ./fetch_and_rebuild.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
DATA="$REPO/data"
BIRD_URL="${BIRD_URL:-https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip}"
BIRD_ZIP_SHA="cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630"
BIRD_DIR="$DATA/bird/dev_20240627/dev_databases"

sha256() { if command -v shasum >/dev/null; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }

# ---------------------------------------------------------------- step 1 BIRD
if [ -d "$BIRD_DIR" ] && [ -e "$BIRD_DIR/financial/financial.sqlite" ]; then
  echo "[bird] $BIRD_DIR already present, skipping download"
else
  mkdir -p "$DATA/bird"
  ZIP="${BIRD_DEV_ZIP:-$DATA/bird/dev.zip}"
  if [ ! -f "$ZIP" ]; then
    echo "[bird] downloading dev.zip (330 MB) from $BIRD_URL"
    curl -L --fail -o "$ZIP" "$BIRD_URL"
  fi
  GOT="$(sha256 "$ZIP")"
  if [ "$GOT" != "$BIRD_ZIP_SHA" ]; then
    echo "[bird] sha256 MISMATCH for $ZIP"; echo "  got  $GOT"; echo "  want $BIRD_ZIP_SHA"
    echo "  (the upstream archive may have been re-released; compare the"
    echo "   per-database hashes in manifests/sha256_sources.txt instead)"
    exit 1
  fi
  echo "[bird] sha256 OK; unzipping"
  unzip -q -o "$ZIP" -d "$DATA/bird"
  # the official archive unzips to dev_20240627/ which may sit at either level
  if [ ! -d "$DATA/bird/dev_20240627" ]; then
    FOUND="$(find "$DATA/bird" -maxdepth 3 -type d -name dev_20240627 | head -1)"
    [ -n "$FOUND" ] && ln -s "$FOUND" "$DATA/bird/dev_20240627"
  fi
  # BIRD ships dev_databases.zip nested inside some releases
  if [ ! -d "$BIRD_DIR" ] && [ -f "$DATA/bird/dev_20240627/dev_databases.zip" ]; then
    unzip -q -o "$DATA/bird/dev_20240627/dev_databases.zip" -d "$DATA/bird/dev_20240627"
  fi
  [ -d "$BIRD_DIR" ] || { echo "[bird] dev_databases not found after unzip"; exit 1; }
fi
# verify the 8 consumed databases against the frozen per-file hashes
echo "[bird] verifying the 8 consumed .sqlite files"
FAIL=0
while read -r H P; do
  case "$P" in bird/*)
    if [ "$(sha256 "$DATA/$P")" != "$H" ]; then echo "  MISMATCH $P"; FAIL=1; fi ;;
  esac
done < "$REPO/manifests/sha256_sources.txt"
[ "$FAIL" = 0 ] && echo "[bird] all consumed sqlite hashes match" || exit 1

# ------------------------------------------------------------- step 2 Spider
BRIDGE="${ASOF_W1_BRIDGE:-$REPO/pilot/public/warehouse.duckdb}"
if [ -f "$BRIDGE" ]; then
  echo "[spider] bridge present; verifying logical hash"
  python3 "$REPO/scripts/rebuild_world1_bridge.py" --hash-only "$BRIDGE"
elif [ -n "${SPIDER_WORLD1_SQLITE:-}" ]; then
  python3 "$REPO/scripts/rebuild_world1_bridge.py" "$SPIDER_WORLD1_SQLITE" --out "$BRIDGE"
elif [ -f "$DATA/spider_data/database/world_1/world_1.sqlite" ]; then
  python3 "$REPO/scripts/rebuild_world1_bridge.py" \
    "$DATA/spider_data/database/world_1/world_1.sqlite" --out "$BRIDGE"
else
  cat <<EOF
[spider] world_1 bridge not built.  Spider has no stable direct download URL:
  1. open https://yale-lily.github.io/spider and download the dataset zip it
     links (Google Drive; the id changes across re-releases, so always take
     the link from the official page)
  2. unzip so that spider_data/database/world_1/world_1.sqlite exists
  3. re-run:  SPIDER_WORLD1_SQLITE=/path/to/world_1.sqlite ./fetch_and_rebuild.sh
EOF
  exit 1
fi

# ------------------------------------------------------------- step 3 rebuild
export ASOF_BIRD_DIR="$BIRD_DIR"
export ASOF_W1_BRIDGE="$BRIDGE"
python3 "$REPO/scripts/rebuild_portable.py" "$@"
echo "[fetch_and_rebuild] done"
