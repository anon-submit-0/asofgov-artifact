# pilot/ — the frozen scorer and the world_1 bridge slot

This directory carries exactly two things; everything else from the project's
earlier pilot phase (an enterprise-track study that only *motivates* the
paper) is deliberately **not** distributed.

1. **`run_pilot.py` — the frozen judging chain.**
   `pilot2/make_pilot2_summary.py` and `pilot2/run_pilot2_arms.py` import this
   file for SQL extraction, refusal detection, execution and scoring, and
   assert its sha256 (`fecda681ccce203f...`, recorded both in
   `pilot2/make_pilot2_summary.py` and in `pilot2/FREEZE_pilot2_arms.json`)
   before importing. Do not edit it: every scored number in the paper flows
   through this exact byte sequence. Its own `__main__` mode drove the earlier
   pilot and is not runnable here (those domain dirs are not shipped).

2. **`public/` — the world_1 legacy bridge slot** (`warehouse.duckdb`,
   gitignored). The pilot2 build imports the Spider `world_1.country` original
   values through this small duckdb (table `country_v2026_01`), a lineage
   stop-over from the earlier public track. It is rebuilt from the official
   Spider download by `scripts/rebuild_world1_bridge.py` and verified against
   a logical content hash (`manifests/sha256_sources.txt`).
