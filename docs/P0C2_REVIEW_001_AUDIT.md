# DTVS-P0C2-REVIEW-001 revision audit

Review response recorded on 2026-11-05 (Asia/Jakarta).

- Review gate received: **REVISE**; this implementation does not self-approve it.
- Reviewed HEAD: `2b858ded34697120231b09806bdcde386eec0c71`.
- Main/base SHA: `8156da4ba113e7c6f4aa2a3eaf8afeb1be4758ca`.
- Branch: `codex/dtvs-p0c-network-aware-placement-v01`.
- Updated HEAD is recorded in the PR/prepared PR body and delivery message;
  a commit's own SHA cannot be embedded in this tracked report.
- `PRODUCTION_DISPATCH=DISABLED`, `MERGE=NO`, `DEPLOY=NO`,
  `HISTORICAL_PERFORMANCE_ACCEPTANCE=HOLD`.

## Preservation

All 15 files added at the reviewed HEAD were hashed before revision and compared
after the tests: **15/15 byte-identical**. The [preservation manifest](p0c2-review-001/preserved-reviewed-files.json)
records each SHA-256. Its own SHA-256 is
`2e7da0aa541692ce7c046ff988994a618688ee660c31854ef58256f774d3dcfc`.

This revision adds files only. It leaves every previously tracked file unchanged,
including all frozen v0.2.2 source/evidence, original tests, signed Bundles,
synthetic fixture data, prior reports, and expected release hashes. It does not
create the absent Windows recovery bundle, add skips, or mark the baseline
failure as an expected failure.

## Historical route semantics

The [mapping specification](P0C1_HISTORICAL_ROUTE_MAPPING_SPEC.md) and the new
`historical_routes.py` classifier define a separate `P0C1_LAN_V01` namespace:

| Historical label | Canonical semantic route |
| --- | --- |
| A | CENTRAL_RELAY |
| B | DIRECT_SOURCE |
| C | IN_SITU |
| D | STREAM_RANGE |

Execution site, input role path, and input access must independently match the
specification. A label is checked for consistency only after those facts match.
Letters alone, old synthetic modes, ambiguous declarations, and a C label with
stream-range facts HOLD. No reinterpretation of the preserved synthetic
`A_LOCAL/B_DIRECT/C_RANGE/D_REMOTE` labels is performed.

Classification is semantic inventory only. It grants no source execution,
remote execution, Range access, task/asset authorization, legal permission,
quality bypass, network capacity, or actual transport direction.

## Separate opt-in provenance inspection

`historical_import.py` introduces a separate API/CLI that requires explicit
opt-in before reading input files. It reads only the selected sanitized
`manifest.json`, `report.md`, `report.json`, and optionally `decisions.csv`.
The specification documents exact supported fields and refusal behavior.
No original export schema is guessed or silently normalized.

The importer verifies listed output hashes, structural metadata, optional CSV
identities/counts, and safe input file handling. It rejects unsafe manifest
paths, symlinks, invalid JSON, duplicate records, mismatched hashes, and unsupported
layouts. Input files are never rewritten. Outputs use a new exclusive directory
with a manifest and read-only files. Arbitrary identifiers and raw report/CSV
content are not echoed into the inspection report.

Even matching output hashes plus complete semantic records produce
`HOLD_PROVENANCE` and `HOLD_ELIGIBILITY_UNKNOWN`. Raw content, event-chain
authenticity, external anchors, and historical permission evidence remain
unverified. Claims of permissions, signatures, or acceptance inside an input
report cannot promote these gates. No cryptographic signature or historical
permission assertion is generated; the importer does not call the old signer,
replay engine, ranker, executor, verifier, or merger. It emits no replay dataset
or placements, and never computes or accepts historical latency/regret.

Integration tests use small invented artifact-contract examples in temporary
directories. Their `RAW_RUN_FILES` fields are deliberately untrusted input
claims, not assertions that historical raw files or permissions were supplied.
The original synthetic fixture and its tests are preserved separately.

## Actual validation and exit codes

Commands ran from the repository root with the existing `.venv` active
(Python 3.12.14, pytest 9.2.0). No dependencies were changed.

| Command | Actual result | Exit |
| --- | --- | ---: |
| At reviewed HEAD: `python3 -m unittest discover -s tests -v` | 99 executed; 98 passed, 1 failed; no skips | 1 |
| `python3 -m pytest tests/integration/test_p0c1_historical_import.py tests/unit/test_p0c_placement.py -q` | 60 passed; 53 subtests passed | 0 |
| Final `python3 -m unittest discover -s tests -v` | 122 executed; 121 passed, 1 failed; no skips | 1 |
| Final `python3 -m pytest -q` | 121 passed, 1 failed; 53 subtests passed; no skips | 1 |
| Compile the two new modules; `git diff --cached --check` | Passed | 0 |
| Opt-in importer CLI against unavailable operator directory | Explicit artifact-validation/provenance HOLD report written | 2 |

There are **23 new integration tests** plus the preserved 37 targeted placement
tests. Integration checks cover all four semantic mappings, letter-only refusal,
C/range confusion, wrong namespace, opaque labels, matching-hash provenance HOLD,
untrusted permission/signature/acceptance claims, optional CSV absence, missing
artifacts, conflicting semantics, hash mismatch, unmanifested input, path/symlink
refusal, invalid JSON/numbers, unsupported layouts, duplicate CSV/route records,
profile separation, deterministic outputs, no network access, input preservation,
output-overwrite refusal, no signed-replay conversion, and CLI exit distinctions.

The unchanged baseline environment failure is:
`WindowsLauncherTests.test_recovery_directory_has_no_attestation_and_complete_hash_manifest`.
The assertion requires the absent, gitignored
`dist/DTVS-PILOT-VERIFIED-RECOVERY/` bundle. It fails at the reviewed HEAD and in
both final full runners. No new test failed; the full suites are **not green**.
The earlier packaging discovery problem also remains unchanged and outside this
revision; all validation uses source-module execution.

Preservation checks also matched all 15 files against their reviewed Git blobs,
verified the original and new artifact manifests, and confirmed this revision
contains eight additions only. A redacted pattern scan of 179 tracked text files
found zero credential/private-key, user-home, private-address, or MAC patterns.
The new files were also reviewed directly; existing binary release archives
were not forensically audited.

## Actual unavailable-artifact probe

The operator's sanitized P0-C1 artifacts were not supplied. After checking that
`inputs/p0c1-sanitized` did not exist, this command ran:

```bash
python3 -m dtvs.scheduling.historical_import \
  --allow-sanitized-p0c1-import \
  --input-dir inputs/p0c1-sanitized \
  --output-dir docs/p0c2-review-001/operator-artifacts-unavailable
```

It returned **2** and wrote the actual [validation report](p0c2-review-001/operator-artifacts-unavailable/validation.json)
and [output manifest](p0c2-review-001/operator-artifacts-unavailable/manifest.json).
Their SHA-256 values are respectively:

- `811328ad23b0bca25edca4a777d95ef0ddf63f6f6de9d5f0ffd6505f716a82ad`
- `de274f82301a5f4f114f650fad11599d16479c6f38dc684fada9e033804ff230`

This is a negative readiness probe, **not a successful historical import**.
Reported counts, selected route, and historical regret are null; route mappings
are empty. Production dispatch, external network actions, cloud billable actions,
signatures, permission assertions, and placements are all zero for the importer.
Absent inputs never trigger fallback to the earlier synthetic fixture.

## Unresolved evidence and review infrastructure

Actual sanitized report/manifest/optional decisions remain necessary to inspect
the real P0-C1 layout and its claims. The reported 48 observations/decisions,
seven tests, and 5.603% regret remain unverified. Missing raw content, an external
provenance anchor, historical permissions, and source-execution/quality evidence
are not resolved by adding this inspection code.

The previously reported directional rate differences, reverse-test pauses, and
unverified retransmissions remain unresolved. This revision sends no diagnostic
traffic and does not pool old/new network profiles or assume link symmetry.

GitHub API reads still fail with `Forbidden`; a fresh connectivity check fails
at proxy CONNECT with 403 (curl exit 56). Git repository reads work. The previous
`api.github.com` allowlist addition is saved in the environment draft, which does
not itself apply runtime access. Draft PR creation must be attempted and its
result reported separately; no PR URL is inferred from a branch or a failed API
request. No merge, deploy, or production action is authorized or performed.
