# DTVS-P0C2-REVIEW-002 execution audit

Review response: 2026-11-05, Asia/Jakarta. Gate received: **REVISE**.

- Base/main: `8156da4ba113e7c6f4aa2a3eaf8afeb1be4758ca`.
- Reviewed branch HEAD: `991ce5b9a2737f3bcb890b45fa361b57bd63afc2`.
- Branch: `codex/dtvs-p0c-network-aware-placement-v01`.
- Existing PR: [#6](https://github.com/roalstoney-alt/dtvs/pull/6).
- The remote branch and `refs/pull/6/head` independently matched the reviewed
  HEAD before edits; the checkout was clean. Main was checked before editing.
- Updated commit SHA and final remote/PR-head checks are recorded in the delivery
  message and prepared PR body, avoiding a self-referential tracked commit SHA.

## Preservation and additive scope

All **23** files reviewed through the prior revision are byte-for-byte preserved,
including the original 15 additions and the following eight additions. The
[preservation manifest](p0c2-review-002/preserved-reviewed-files.json) records
their hashes, with SHA-256
`4c5a2d3fa997173c98862e9c38517adafce2405474929cbcab70679c092385d9`.
All frozen v0.2.2 implementation, evidence, legacy tests, expected hashes and
dependency declarations remain unchanged. This revision adds files only.

Final preservation checks matched all 23 files against their reviewed Git blobs.
The new modules passed a forbidden-network/process/signer/production-import AST
check. A redacted pattern scan of 186 tracked text files found zero credential,
private-key, user-home, private-address or MAC patterns. Existing binary release
archives were not forensically audited.

The new two-module inspector recognizes the specified five-output container and
CSV contracts separately from both old inspection examples and the synthetic
P0-C2 replay. It checks archive safety, exact member hashes, complete cardinality,
median/tolerance/payload selection, feasible-only oracle/regret and explicit
report statistics. See the [versioned contract and redaction process](P0C1_FIVE_OUTPUT_INSPECTOR_V01.md).

## Available evidence and a required distinction

This task exposes the two uploaded Markdown documents:
`DTVS_P0C2_REVIEW_002_CODEX_WORKFLOW.md` and
`DTVS_P0C1_EVIDENCE_REVIEW_002.md`. They describe a genuine output ZIP reviewed
elsewhere, and list its member hashes and reported arithmetic results. The ZIP
bytes, its original report/CSVs, and the reference test program are **not present
in the supplied attachments or readable project workspace**. Checking the
attachments again after the operator's reply did not reveal a ZIP/download
reference. No unrelated Windows release ZIP was substituted.

Consequently this revision does **not** claim to have revalidated the operator's
48 observations/decisions or the actual export's report layout. Hash strings in
a review cannot substitute for original bytes. The supplied review's 48/48
matches and 5.602871329879111% maximum remain attributed to that review, not
represented as results of an original-data execution in this cloud machine.

The final tie priority, precise eligible-path serialization, decision-state
string and report-statistic locations are not enumerated by those Markdown
documents. The inspector requires an explicit caller-selected reference for
them. It does not infer priorities from observed decisions or silently substitute
an invented report schema. Without that reference, hash/grid checks can run but
arithmetic remains `NOT_RUN`/`HOLD_POLICY_REFERENCE_REQUIRED`. The source
authenticity of a supplied reference is itself unverified.

## Executed validation

Commands ran at the repo root using the existing `.venv`, Python 3.12.14 and
pytest 9.2.0. No packages or dependency declarations were changed.

| Check | Actual outcome | Exit |
| --- | --- | ---: |
| Baseline `python3 -m unittest discover -s tests -v` | 122 executed: 121 passed, 1 failed; no skips | 1 |
| `python3 -m pytest tests/integration/test_p0c1_output_inspector.py tests/integration/test_p0c1_historical_import.py tests/unit/test_p0c_placement.py -q` | 100 passed; 67 subtests passed | 0 |
| Final `python3 -m unittest discover -s tests -v` | 162 executed: 161 passed, 1 failed; no skips | 1 |
| Final `python3 -m pytest -q` | 161 passed, 1 failed; 67 subtests passed; no skips | 1 |
| Compile new modules/tests; staged whitespace/static checks | Passed | 0 |
| Final-code CLI twice against the same **synthetic contract example** ZIP | Both wrote HOLD summaries; byte-identical validation and manifest | 2 each |

The unchanged baseline environment failure is
`WindowsLauncherTests.test_recovery_directory_has_no_attestation_and_complete_hash_manifest`,
which requires the absent gitignored Windows recovery bundle. It remains failed
in the baseline and both final full regressions. No recovery bundle was fabricated,
no expected hashes were changed, and no assertion/skip was added. Full suites
are **not green**. Existing setuptools packaging-discovery limitations also
remain unchanged; commands run source modules.

The **40 new integration tests** exercise schema-accurate invented observations
and decisions, not operator data or historical permission evidence. They cover
all requested negative cases: changed byte, absent observations, missing sample,
profile leakage, misranking, wrong actual/oracle/regret, payload mismatch,
duplicate rows, route-name conflict, forged permissions, schema drift and illegal
archive entries. They also check CRC/decompression errors, duplicate ZIP members,
resource/symlink limits, exact group counts, type-exact policy comparison, final
tie priority, 3% boundary, explicit encoding/state, opt-in, deterministic output,
input preservation, output refusal, no raw-value echoes and no socket actions.

One test checks the ratio `(19.5661 / 18.5280 - 1) * 100` quoted by the review.
It reproduces 5.602871329879111% numerically; it does **not** authenticate those
two measurements or reproduce the absent full historical export.

## Bounded exact-schema inspector example

The [machine-readable validation scope](p0c2-review-002/validation_scope.json),
SHA-256 `1b3dc60d0d7d710511558d84af88405fa1ed3b069a104d5f88829ad0511c3601`,
labels every positive execution here as
`SCHEMA_ACCURATE_SYNTHETIC_CONTRACT_EXAMPLE_ONLY`. Its recorded actual stages are:

| Stage | Invented contract example | Actual operator ZIP here |
| --- | --- | --- |
| Exact internal output hashes | PASS_SELF_CONTAINED | NOT_RUN: bytes unavailable |
| Full exported grid | PASS: 48 observations, 48 hypothetical decisions | NOT_RUN |
| Median/payload/tie arithmetic | PASS: 48 predictions/selections/actuals/oracles/regrets/payloads | NOT_RUN |
| Report statistics | PASS: 33 explicit checks | NOT_RUN |
| Profile isolation | PASS | NOT_RUN |
| Structural semantics | PROVISIONAL_REFERENCE_ONLY | No runtime attestation |
| External source authenticity | NOT_VERIFIED | NOT_VERIFIED |
| Historical permissions | HOLD_ELIGIBILITY_UNKNOWN | HOLD_ELIGIBILITY_UNKNOWN |

The example has 12 distinct exported folds reused across four scenarios. It is
not 48 independent new physical experiments. Its invented worst regret is
3.157894736842115%, **not** a reproduction of the reviewed historical maximum.
Both final-code CLI runs returned 2 because complete output-only validation
still HOLDs provenance/permissions. Their derived output SHA-256 values match:

- `validation.json`: `0179583eb7a472aa8ca5e71feb98dfd22fda35e0a42ee23a8b16ce541a77fd5a`
- `manifest.json`: `5578899086c6fa133fa9cee2e393ea113690822c625dd003407ffe566621f2f2`

The original/generated test containers, report JSON/CSV and reference remain
outside tracked files. Only this bounded scope summary and preservation hashes
are committed. The documented derived-redaction process uses new output hashes
linked to unchanged input hashes; it never overwrites originals or assigns
original hashes to redacted bytes.

## Evidence, safety boundaries and remaining actions

The historical namespace is `P0C1_LAN_V01`: A=CENTRAL_RELAY,
B=DIRECT_SOURCE, C=IN_SITU, D=STREAM_RANGE. The supplied reference describes A's
relay-to-worker stage as a **Mac-local copy**, not a third physical host. This
is provisional code-reference description, not deployed runtime attestation,
directional calibration, rights, or authorization. Synthetic `A_LOCAL` and
`C_RANGE` labels never supply historical semantics by letter.

All importer action counters are zero for the exercised offline engine:
`PRODUCTION_DISPATCH_COUNT=0`, `EXTERNAL_NETWORK_ACTIONS=0`,
`CLOUD_BILLABLE_ACTIONS=0`, generated historical signatures=0,
permission assertions=0 and production placements=0. Git/GitHub review actions
are outside those counters. No source files or previous evidence were overwritten.

The actual ZIP is still required for original-member hashes and all 48 original
reconstructions; the original policy/layout reference is required where not
explicit in its metadata. Historical LAN source-run files, event chains, external
anchors, legal/privacy/Range/source-execution permissions, quality evidence and
fresh directional calibration are not established by output validation. Reported
reverse-direction rate differences, pauses and unverified retransmissions remain
unresolved. No WAN, genuine 2 GiB Parquet, economic or energy claim is made.

The task identifies PR #6 as Draft. Its Git head was verified, but GitHub API
requests still return `Forbidden`, so live Draft/open status and metadata edits
cannot be independently confirmed through the API. Push/update outcomes are
reported separately after commit; no merge, deployment or readiness transition
is requested.

Human gate requested after review: **APPROVE_OFFLINE_INTEGRATION**, **REVISE**, or
**HOLD**. Approval would concern offline code only. Regardless of that choice,
`PRODUCTION_DISPATCH=DISABLED`, `MERGE=NO`, `DEPLOY=NO`, and
`HISTORICAL_PERFORMANCE_ACCEPTANCE=HOLD` remain in force.
