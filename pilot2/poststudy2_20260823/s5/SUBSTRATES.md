# S5 scaled substrates (`work/`) — excluded from this archive

The battery-2 S5 cost sweep was measured against scaled DuckDB substrates that
lived under `s5/work/` (row-scale copies of the `financial` warehouse at
12.5% / 25% / 50% / 100% / 200% / 400%, plus a byte-identical `world_1` copy
for the windows-span axis). Those warehouse files are **not** shipped here:
they are large, and they are **deterministically rebuildable** — the scaling
rule uses no RNG.

To rebuild them, run the sweep's substrate builder from this directory:

```
python3 s5_build_substrates.py
```

The exact deterministic scaling rule is documented in the header docstring of
`s5_build_substrates.py`: sub-1x points keep rows by systematic residue
sampling on the primary key (`trans_id % 8 < 8*f`); above-1x points duplicate
the original rows with the primary key remapped by `+ c * 4,000,000` per copy
(all other columns verbatim, join topology preserved); the 1x point is a
byte-identical copy of the source warehouse; the windows-span substrate is a
byte-identical copy of the frozen `world_1` domain. The source warehouses are
the frozen `pilot2/domains/` substrates rebuilt by `fetch_and_rebuild.sh`
(never opened read-write by the sweep).

Per-substrate reachability facts (row counts, date hulls, gold-anchor
survival) and identity checks are preserved in `s5_cost_sweep.json` and
`s5_identity_check.json`, so the shipped evidence remains verifiable without
the `work/` payload; `s5_check_identity.py` re-verifies a rebuilt substrate
set against those recorded facts.
