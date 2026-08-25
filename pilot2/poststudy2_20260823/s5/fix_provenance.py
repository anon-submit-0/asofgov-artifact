#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_provenance.py — one-shot S5 provenance correction (2026-08-23).

Defect (found by adversarial verification, VERIFICATION2.md, S5 section
and Defect list item 1): s5_measure.py's PREREG_SHA constant dropped two
hex characters from the governing prereg's sha256, citing a 62-character
value; the corrupted value propagated into s5_cost_sweep.json
(prereg.sha256 and substrates_manifest.prereg_sha256) and the
S5_REPORT.md header, and no S5 script re-asserted the hash from the
frozen prereg on disk, so the typo went uncaught.

Sanctioned scope — exactly three files, nothing re-measured:
  1. s5_cost_sweep.json : replace ONLY the two prereg-sha metadata
     fields with the correct value (recomputed from the frozen prereg on
     disk, asserted to differ from the old value only by the two dropped
     characters) and append a "provenance_correction" object.
  2. S5_REPORT.md       : re-render from the corrected JSON via the
     study's own s5_render_report.py (fidelity pre-checked byte-for-byte
     against the frozen report) and append a visible CORRECTION note.
  3. s5_measure.py      : correct the sha constant (docstring citation
     included) and ADD the missing runtime re-assert-from-disk so a
     future re-run refuses on mismatch.

Every other byte in pilot2/poststudy2_20260823/s5/ is proven unchanged
by a before/after sha256 snapshot of the whole tree; the full unified
diffs of the three changed files are persisted (append-only) in
fix_provenance_result.json.  The script aborts before writing anything
if any assertion fails, and is idempotent (second run: no-op).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import pathlib
import py_compile
import shutil
import subprocess
import sys
import tempfile

S5 = pathlib.Path(__file__).resolve().parent
POST = S5.parent
PREREG_P = POST / "PREREG_poststudy2_20260823.md"
JSON_P = S5 / "s5_cost_sweep.json"
REPORT_P = S5 / "S5_REPORT.md"
MEASURE_P = S5 / "s5_measure.py"
RENDER_P = S5 / "s5_render_report.py"
RESULT_P = S5 / "fix_provenance_result.json"

CORRECTION_DATE = "2026-08-23"
# Gate value only: the authoritative TRUE sha is recomputed from the
# frozen prereg on disk below and must equal this, or we abort.
EXPECTED_TRUE = ("838a214fc5a09902703d969c839872ff"
                 "843f190e9f2e1c9f6902f231e061c669")

TARGETS = {"s5_cost_sweep.json", "S5_REPORT.md", "s5_measure.py"}
SELF = {"fix_provenance.py", "fix_provenance_result.json"}


def die(msg):
    sys.stderr.write("ABORT (nothing written): %s\n" % msg)
    raise SystemExit(1)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot():
    return {str(p.relative_to(S5)): sha256_file(p)
            for p in sorted(S5.rglob("*")) if p.is_file()}


def render_report_from(json_text):
    """Run the study's own renderer against json_text in a staging dir."""
    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        shutil.copy2(RENDER_P, tdp / "s5_render_report.py")
        (tdp / "s5_cost_sweep.json").write_text(json_text, encoding="utf-8")
        r = subprocess.run([sys.executable, str(tdp / "s5_render_report.py")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            die("s5_render_report.py failed in staging: %s" % r.stderr)
        return (tdp / "S5_REPORT.md").read_text(encoding="utf-8")


def udiff(name, old, new):
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile="s5/%s (before)" % name, tofile="s5/%s (after)" % name))


def main():
    # ---- 0. ground truth: re-assert the prereg hash FROM DISK ----------
    TRUE = sha256_file(PREREG_P)
    if TRUE != EXPECTED_TRUE:
        die("frozen prereg %s hashes to %s on disk, not the expected %s"
            % (PREREG_P, TRUE, EXPECTED_TRUE))
    if len(TRUE) != 64:
        die("disk sha has length %d, expected 64" % len(TRUE))

    orig_json = JSON_P.read_text(encoding="utf-8")
    orig_report = REPORT_P.read_text(encoding="utf-8")
    orig_measure = MEASURE_P.read_text(encoding="utf-8")
    J = json.loads(orig_json)

    if "provenance_correction" in J:
        print("already corrected (provenance_correction present) — no-op")
        return 0

    # ---- 1. characterise the defect (abort unless EXACTLY as diagnosed)
    BAD = J["prereg"]["sha256"]
    if len(BAD) != 62:
        die("prereg.sha256 in JSON is %d chars; expected the 62-char "
            "corrupted citation" % len(BAD))
    drops = [i for i in range(len(TRUE) - 1)
             if TRUE[:i] + TRUE[i + 2:] == BAD]
    if not drops:
        die("cited sha is NOT the true sha with exactly two adjacent "
            "characters dropped — defect differs from diagnosis, refusing")
    drop_at = drops[0]
    dropped = TRUE[drop_at:drop_at + 2]
    if J["substrates_manifest"]["prereg_sha256"] != BAD:
        die("substrates_manifest.prereg_sha256 is %r, expected the same "
            "corrupted value" % J["substrates_manifest"]["prereg_sha256"])

    # occurrence discipline: the corrupted string appears exactly where
    # diagnosed and the true string appears nowhere in the targets
    for name, text, n in (("s5_cost_sweep.json", orig_json, 2),
                          ("S5_REPORT.md", orig_report, 1),
                          ("s5_measure.py", orig_measure, 2)):
        if text.count(BAD) != n:
            die("%s: %d occurrences of the corrupted sha, expected %d"
                % (name, text.count(BAD), n))
        if TRUE in text:
            die("%s already contains the true sha — unexpected state" % name)

    # ---- 2. pre-flight: whole-tree snapshot + renderer fidelity --------
    before = snapshot()
    if render_report_from(orig_json) != orig_report:
        die("s5_render_report.py does not reproduce the existing "
            "S5_REPORT.md byte-for-byte from the existing JSON — "
            "refusing to re-render")

    # residual corrupted citations OUTSIDE the sanctioned three files
    residual_files = []
    for p in sorted(S5.rglob("*")):
        if not p.is_file() or p.name.startswith("._"):
            continue
        rel = str(p.relative_to(S5))
        if rel in TARGETS or rel in SELF:
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        n = t.count(BAD)
        if n:
            residual_files.append({"file": "s5/" + rel, "occurrences": n})

    # ---- 3. build the corrected JSON (sha fields only + appended note) -
    if json.dumps(J, ensure_ascii=False, indent=1) != orig_json:
        die("s5_cost_sweep.json does not round-trip through its "
            "generator's dump settings — cannot guarantee a byte-minimal "
            "edit, refusing")
    corrected_json_text = orig_json.replace(BAD, TRUE)
    JC = json.loads(corrected_json_text)
    JX = json.loads(orig_json)
    JX["prereg"]["sha256"] = TRUE
    JX["substrates_manifest"]["prereg_sha256"] = TRUE
    if JC != JX:
        die("string replacement would change something besides the two "
            "prereg-sha metadata fields — refusing")

    corr = {
        "schema": "asofgov/provenance_correction.v1",
        "corrected_at": CORRECTION_DATE,
        "corrected_by": "pilot2/poststudy2_20260823/s5/fix_provenance.py",
        "defect": {
            "kind": "corrupted_prereg_sha_citation",
            "description": (
                "s5_measure.py's PREREG_SHA constant dropped two hex "
                "characters ('%s' at offset %d) from the prereg sha256, "
                "citing a %d-character value; it propagated into this "
                "JSON (prereg.sha256, substrates_manifest.prereg_sha256) "
                "and the S5_REPORT.md header, and no S5 script "
                "re-asserted the hash from the frozen prereg on disk, so "
                "the typo went uncaught" % (dropped, drop_at, len(BAD))),
            "corrupted_value": BAD,
            "correct_value": TRUE,
            "correct_value_recomputed_from": str(PREREG_P),
            "dropped_chars": dropped,
            "drop_offset": drop_at,
            "fields_corrected": ["prereg.sha256",
                                 "substrates_manifest.prereg_sha256"],
        },
        "discovery": {
            "method": "adversarial verification",
            "record": ("poststudy2_20260823/VERIFICATION2.md "
                       "(S5 section; Defect list item 1)"),
            "date": CORRECTION_DATE,
        },
        "impact": ("metadata-only: no measured number, verdict, or "
                   "certificate is affected; no timing was re-run"),
        "companion_fixes": [
            "S5_REPORT.md re-rendered from this corrected JSON via "
            "s5_render_report.py (fidelity pre-checked byte-for-byte), "
            "with a visible CORRECTION note appended",
            "s5_measure.py: PREREG_SHA constant corrected (docstring "
            "citation included) and a runtime re-assert-from-disk added, "
            "so a future re-run refuses on mismatch",
        ],
        "residual_corrupted_citations_out_of_scope": {
            "note": ("left untouched — outside the sanctioned correction "
                     "scope under the append-only regime; NOTE a future "
                     "rebuild via s5_build_substrates.py would regenerate "
                     "work/substrates_manifest.json with the corrupted "
                     "value — flagged for follow-up"),
            "files": residual_files,
        },
    }
    JC["provenance_correction"] = corr
    final_json_text = json.dumps(JC, ensure_ascii=False, indent=1)
    if not final_json_text.startswith(corrected_json_text[:-2]):
        die("appending provenance_correction altered earlier bytes")

    # ---- 4. re-render the report from the corrected JSON ---------------
    rendered = render_report_from(final_json_text)
    if rendered != orig_report.replace(BAD, TRUE):
        die("re-render from corrected JSON differs from the frozen report "
            "beyond the sha string — refusing")
    note = (
        "---\n"
        "\n"
        "## CORRECTION (%s) — prereg sha256 provenance\n"
        "\n"
        "The prereg sha256 quoted in the header above was corrected on %s.\n"
        "The original run's sweep-script constant dropped two hex characters\n"
        "(`%s` at offset %d) and cited the %d-character value\n"
        "`%s` in place of the true\n"
        "%d-character sha (recomputed from the frozen prereg on disk)\n"
        "`%s`;\n"
        "no S5 script re-asserted the hash from disk. The defect was found\n"
        "by adversarial verification (`VERIFICATION2.md`, S5 section and\n"
        "Defect list item 1). Measured numbers are unaffected and nothing\n"
        "was re-run: this report was re-rendered (byte-identically, sha\n"
        "string aside) from the corrected `s5_cost_sweep.json` by the\n"
        "study's own `s5_render_report.py`; see that JSON's\n"
        "`provenance_correction` object. `s5_measure.py`'s constant was\n"
        "corrected and a runtime re-assert-from-disk added, so a future\n"
        "re-run refuses on mismatch. Correction applied by\n"
        "`fix_provenance.py`; byte-level before/after proof in\n"
        "`fix_provenance_result.json`.\n"
        % (CORRECTION_DATE, CORRECTION_DATE, dropped, drop_at, len(BAD),
           BAD, len(TRUE), TRUE))
    final_report_text = rendered + note

    # ---- 5. patch the sweep script: sha strings + re-assert-from-disk --
    m = orig_measure.replace(BAD, TRUE)
    imp_anchor = "import datetime as dt\nimport json\n"
    if m.count(imp_anchor) != 1:
        die("s5_measure.py import anchor not found exactly once")
    m = m.replace(imp_anchor,
                  "import datetime as dt\nimport hashlib\nimport json\n")
    guard = (
        "# Provenance re-assert added %s (fix_provenance.py; see\n"
        '# s5_cost_sweep.json "provenance_correction"): the original run\n'
        "# cited a corrupted 62-char sha because nothing checked the\n"
        "# constant against the frozen prereg on disk.  A future re-run\n"
        "# now refuses on mismatch.\n"
        'PREREG_PATH = S5.parent / "PREREG_poststudy2_20260823.md"\n'
        "_PREREG_DISK_SHA = hashlib.sha256("
        "PREREG_PATH.read_bytes()).hexdigest()\n"
        "if _PREREG_DISK_SHA != PREREG_SHA:\n"
        "    raise SystemExit(\n"
        '        "PREREG sha mismatch: disk %%s != constant %%s '
        '-- refusing to run"\n'
        "        %% (_PREREG_DISK_SHA, PREREG_SHA))\n" % CORRECTION_DATE)
    sha_anchor = 'PREREG_SHA = "%s"\n' % TRUE
    if m.count(sha_anchor) != 1:
        die("s5_measure.py PREREG_SHA anchor not found exactly once")
    m = m.replace(sha_anchor, sha_anchor + "\n" + guard)
    final_measure_text = m

    # verify: the exact inserted guard passes with the true sha and
    # refuses with the corrupted one
    ns_ok = {"S5": S5, "hashlib": hashlib, "PREREG_SHA": TRUE}
    exec(compile(guard, "<guard>", "exec"), ns_ok)  # must not raise
    ns_bad = {"S5": S5, "hashlib": hashlib, "PREREG_SHA": BAD}
    try:
        exec(compile(guard, "<guard>", "exec"), ns_bad)
        die("guard failed to refuse on a mismatched sha")
    except SystemExit as e:
        if "PREREG sha mismatch" not in str(e):
            raise
    # verify the patched script still compiles
    with tempfile.TemporaryDirectory() as td:
        tp = pathlib.Path(td) / "s5_measure_patched.py"
        tp.write_text(final_measure_text, encoding="utf-8")
        py_compile.compile(str(tp), doraise=True)

    # ---- 6. write the three sanctioned files ---------------------------
    finals = {"s5_cost_sweep.json": (orig_json, final_json_text),
              "S5_REPORT.md": (orig_report, final_report_text),
              "s5_measure.py": (orig_measure, final_measure_text)}
    for name, (_, text) in finals.items():
        (S5 / name).write_text(text, encoding="utf-8")

    # ---- 7. byte-level before/after proof over the whole tree ----------
    after = snapshot()
    changed = sorted(k for k in before
                     if k in after and before[k] != after[k])
    added = sorted(k for k in after if k not in before)
    removed = sorted(k for k in before if k not in after)
    problems = []
    if set(changed) != TARGETS:
        problems.append("changed set %s != sanctioned %s"
                        % (changed, sorted(TARGETS)))
    if removed:
        problems.append("files removed: %s" % removed)
    if [a for a in added if a not in SELF]:
        problems.append("unexpected files added: %s" % added)

    result = {
        "schema": "asofgov/fix_provenance_result.v1",
        "ran_at": CORRECTION_DATE,
        "script": "pilot2/poststudy2_20260823/s5/fix_provenance.py",
        "true_sha_recomputed_from_disk": TRUE,
        "corrupted_sha": BAD,
        "dropped_chars": dropped,
        "drop_offset": drop_at,
        "renderer_fidelity_precheck":
            "PASS: render(original JSON) == frozen S5_REPORT.md, "
            "byte-for-byte",
        "rerender_check":
            "PASS: render(corrected JSON) == frozen S5_REPORT.md with "
            "only the sha string replaced",
        "guard_check":
            "PASS: inserted guard accepts the true sha and raises "
            "SystemExit on the corrupted one; patched script py_compiles",
        "files_scanned": len(before),
        "files_changed": {
            name: {
                "sha256_before": before[name],
                "sha256_after": after[name],
                "bytes_before": len(finals[name][0].encode("utf-8")),
                "bytes_after": len(finals[name][1].encode("utf-8")),
                "unified_diff": udiff(name, finals[name][0],
                                      finals[name][1]),
            } for name in sorted(TARGETS)},
        "files_added_append_only": added,
        "files_removed": removed,
        "files_unchanged": len(before) - len(changed),
        "unchanged_verified_by": "sha256 of every file under s5/ "
                                 "(work/ included), before vs after",
        "residual_corrupted_citations_out_of_scope": residual_files,
        "clean": not problems,
        "problems": problems,
    }
    RESULT_P.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    print("true sha (from disk): %s" % TRUE)
    print("corrupted citation  : %s  (dropped '%s' at offset %d)"
          % (BAD, dropped, drop_at))
    print("files scanned: %d | changed: %s | added (append-only): %s | "
          "unchanged: %d" % (len(before), changed, added,
                             len(before) - len(changed)))
    for name in sorted(TARGETS):
        print("\n===== %s =====" % name)
        print(result["files_changed"][name]["unified_diff"])
    if residual_files:
        print("residual corrupted citations left untouched (out of "
              "sanctioned scope): %s" % residual_files)
    if problems:
        for p in problems:
            sys.stderr.write("PROBLEM: %s\n" % p)
        return 2
    print("\nCLEAN: only the two sha metadata fields, the sha strings in "
          "the report header and sweep script, the appended correction "
          "records, and the added runtime re-assert changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
