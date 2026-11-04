# Uploaded P0-C1 output ZIP: actual validation

**Current result: all 48 exported selections and arithmetic checks match using
the operator-confirmed original B > D > C > A final priority. No output-policy
ties remain unresolved. Provenance, eligibility and historical performance
acceptance remain HOLD.**

This continues DTVS-P0C2-REVIEW-002 after the operator supplied
`DTVS_P0C1_Evidence_Review.zip` in the follow-up message. It supersedes the
earlier **unavailable ZIP** state; those earlier audits and snapshots remain
unchanged as records of the inputs then available.

Parent implementation: `e7e4ca9f319260606200a9fc135b180b66259614` on
`codex/dtvs-p0c-network-aware-placement-v01`, PR
[#6](https://github.com/roalstoney-alt/dtvs/pull/6). Main remains
`8156da4ba113e7c6f4aa2a3eaf8afeb1be4758ca`. The final commit SHA and remote
PR-head verification are reported in the delivery message/prepared PR body.

## Original bytes and preservation

The original uploaded ZIP is 4,394 bytes, SHA-256
`b53ce15cd64bc7860ddec1fb143bfba73273fc95b5e374332814c76cb7e5c959`.
It passed the fixed-member, resource, entry-type and CRC checks. All five member
digests exactly match the supplied independent review:

| Original member | Exact SHA-256 |
| --- | --- |
| manifest.json | `0a0154535fb4b707224d5a8f9514d73979b1f90e4821cc6e9ebe17793aec7f3e` |
| report.json | `e48efd58086f55c2371becb947c1fa6a02f52d7c7ecf812524d7f8566dd250b9` |
| report.md | `1ae6218a28df434f3ff5b4bd30fc41b24b869c006f37a04d853b46da866b1d08` |
| decisions.csv | `fdd787a15dc81f859f33fecf055f7130c9a34567e39c4a63828685119e0deff4` |
| observations.csv | `710b91904b744b8f534c5c8a3c3f9061c02cab1c7d4dfaa7c21c103c3ee94a6c` |

The manifest also independently matches all four listed data members. This is
`PASS_SELF_CONTAINED`, not external anchoring of historical LAN source files.
The ZIP and member bytes were not rewritten or extracted into the public repo;
the ZIP hash was checked again after both executions.

All 23 files reviewed through `991ce5b9a2737f3bcb890b45fa361b57bd63afc2`
remain byte-identical, including the first 15 additions and frozen v0.2.2
evidence. Prior reports, manifests and test snapshots are unchanged. Only the
two new inspector modules introduced in the last implementation are extended;
new tests and this derived evidence record are added.

## Real schema correction: version 0.2

The actual report's eight `statistics` records contain `profile`, `scenario`,
`n`, `mean_regret_pct`, `max_regret_pct`, and sparse `selected_paths` counts.
It publishes **no mean elapsed statistic**. Reference contract v0.2 validates
the available statistics without inventing a mean elapsed field. Omitted zero
selection counts are explicitly normalized to zero; unknown routes, wrong
counts and noninteger counts are rejected. All 33 available checks are made:
four per group and the overall maximum.

The old v0.1 reference retains its stricter schema/coverage requirements. The
versioned v0.2 contract accepts an explicitly unknown (`null`) final priority;
it does not silently derive an order from the exported selected routes.

The real CSV uses pipe-separated feasible sets, exported state
`OFFLINE_REPLAY_ONLY`, four-decimal time precision and three-decimal regret
precision. A private reference binds this observed layout and the exact policy
value. The confirmed source-reference hash binds a normalized transcription of
the operator-provided code excerpt attributed to original `p0c_replay.py`, lines 124-128, from
`DTVS_P0C_Offline_Placement_v0.1.zip`. The original program package itself was
not supplied to this machine. The excerpt hash is
`da8de7614109b8dae00471dd363e700c03c952c77b415e3f3d7f63c2cdbf4eeb`;
it is not an externally authenticated source-file/package hash. The private
reference/policy text is not committed.

## Actual arithmetic and the confirmed original final tie rule

There are exactly 48 `ACCEPTED` observation claims: two profiles × two queries ×
four routes × three repeats. There are 48 hypothetical decisions over **12
distinct exported folds reused in four scenarios**, not 48 new independent
physical executions. Duplicate/grid/finite-value checks passed.

| Check on the genuine export | Result |
| --- | --- |
| Internal exact hashes | PASS_SELF_CONTAINED |
| Full exported grid | PASS |
| Selected-path two-other-repeat median predictions | 48/48 match |
| Held-out actual values | 48/48 match |
| Feasible-route held-out oracles | 48/48 match |
| Regret and selected payload | 48/48 each match |
| Published group/overall statistics | 33/33 match |
| Profile isolation | PASS |
| Reproduced selections using the supplied original rule | 48/48 |
| Unresolved final ties | 0 |
| Structural route semantics | PROVISIONAL_REFERENCE_ONLY |

Recomputed maximum regret is **5.602871329879111%**, matching reported
**5.603%** at the report's precision. This is now an execution against the
genuine exported CSV values, not the earlier synthetic example or two-number
arithmetic test.

Payload comparisons use the exported counted-byte values after cross-repeat
and selected-row consistency checks. This does not independently authenticate
the original program's `EXPECTED` table or measure physical NIC traffic.

For all folds, forecasts use only the other two repeats from the same profile,
query and route. Feasible candidates enter the inclusive 3% forecast band and
are reduced by counted payload. Initially **39** choices had a unique
minimum-payload candidate and **nine** remained held because the ZIP did not
enumerate the final ordering. The operator then supplied the original reference
excerpt and explicitly confirmed this priority after equal payload:

1. B_DIRECT_SOURCE
2. D_STREAM_RANGE
3. C_IN_SITU
4. A_CENTRAL_RELAY

This priority does not use predicted latency again once routes are in the
inclusive 3% band with equal payload. It was supplied independently by the
operator, not inferred by fitting the exported selections. With that reference,
all nine formerly held cases match and `placement_policy=PASS`,
`validation_status=OUTPUT_VALIDATION_COMPLETE`. The earlier partial result is
retained below as a chronological record. The original source-code package and
historical runtime/rights remain unverified; this resolution discharges only
the exported selection-rule comparison.

## Actual runs, derived redaction, and results

The CLI ran twice against the same original archive with the confirmed explicit
reference, in two fresh private output directories. Both exited **2** (HOLD).
Both validation reports and manifests are byte-identical. The original ZIP hash
is unchanged after execution.

The committed [confirmed-rule validation report](p0c1-uploaded-evidence-confirmed-rule/validation.json)
and [confirmed-rule manifest](p0c1-uploaded-evidence-confirmed-rule/manifest.json) are exact
copies of those bounded inspector outputs. Their **new** hashes are:

- validation.json: `4b399a72ce178c8d7f4d1e9da176053080098f1e62d7fe1aa4438474740f86b6`
- manifest.json: `2f4005ddc668b7f18fcd4a0e42820bced45384e81125a30fef7abb9469662a9e`

The earlier [partial validation](p0c1-uploaded-evidence-validation/validation.json)
and [partial manifest](p0c1-uploaded-evidence-validation/manifest.json) remain
unchanged (hashes `86808cd9dce802c1f36fb24fbb39ac13b855a12074855633e3c3405a12de89d7`
and `5bafd70328373d7b11d3a517d38f4f01066e896e0be1cf219cbcc632542041d1`).
They document the 39/9 state before the reference reply, not the final result.

The separately documented [derived-redaction process](P0C1_FIVE_OUTPUT_INSPECTOR_V01.md#derived-redaction-for-auditpublic-review)
was applied: only controlled status/reason enums, fixed neutral route/profile
IDs, hashes, counts and aggregate statistics are emitted. Source JSON, CSV
rows, account paths, token strings, source-provenance objects and IP addresses
are not copied. The private policy reference remains outside tracked files.
Derived hashes are linked to unchanged original hashes; redacted bytes are never
labeled with an original member digest. These outputs were reviewed for their
bounded schema and sensitive-data patterns before committing.

Tests ran from the repository root in the existing virtualenv; dependencies
and lockfiles were not changed:

| Command/check | Actual result | Exit |
| --- | --- | ---: |
| Targeted pytest: new real-report contract, output inspector, prior importer, placement tests | 113 passed; 74 subtests passed | 0 |
| `python3 -m unittest discover -s tests -v` | 175 executed; 174 passed, 1 failed; no skips | 1 |
| `python3 -m pytest -q` | 174 passed, 1 failed; 74 subtests passed; no skips | 1 |
| Compile changed modules/new tests; staged whitespace/static checks | Passed | 0 |
| Genuine ZIP CLI twice; compare report/manifest bytes and original hash | Identical outputs; original unchanged | 2 each |

Thirteen new tests use **invented**, schema-accurate examples of this report layout,
not operator rows. They check sparse counts, absence of invented elapsed means,
unknown-priority holds, unique choices without an unused priority, invalid
claims within a tied fold, arithmetic checks despite unresolved selection,
integer counts, legacy-contract preservation, deterministic output and no input
overwrite. A regression test pins the supplied B > D > C > A order even when
the preferred route has a slower forecast inside the equal-payload time band.
The sole full-suite failure is still
`WindowsLauncherTests.test_recovery_directory_has_no_attestation_and_complete_hash_manifest`:
its gitignored recovery bundle is absent. No bundle, hash change, skip or
weakened assertion was introduced; the full suites are not green.

Final checks matched the original ZIP hash and all derived manifest hashes,
verified the 23 reviewed files against Git blobs, and passed the forbidden
network/process/signer/production-import AST check. A redacted scan of 192
tracked text files found zero credential, private-key, user-home, private-address
or MAC patterns. Existing binary release archives were not forensically audited.

## Boundaries and remaining evidence

The semantic namespace remains `P0C1_LAN_V01`. A is a simulated relay using a
Mac-local copy after the source fetch, not a third physical host; B is direct
source fetch; C is source-side compute; D is stream/range processing. These are
reference descriptions, not runtime attestation or current permissions.
Synthetic fixture letters are never mapped to these meanings by letter alone.

All six importer action counts are zero: production dispatch, external network
actions, cloud billable actions, generated historical signatures, permission
assertions and production placements. Git/GitHub review operations are outside
these counts. No original LAN data files, raw event-chain bytes, authenticated
external anchors, historical rights/quality evidence or fresh directional
network calibration were supplied. Reverse-direction anomalies remain open.

`HOLD_PROVENANCE`, `HOLD_ELIGIBILITY_UNKNOWN`, and
`HISTORICAL_PERFORMANCE_ACCEPTANCE=HOLD` remain mandatory.
`PRODUCTION_DISPATCH=DISABLED`, `MERGE=NO`, `DEPLOY=NO`.
The final tie gap is resolved by the operator's reference excerpt; no remaining
exported selection is held. Human review may approve offline integration,
request revision, or hold; none of those choices implies merge/production
permission or authenticates the missing original LAN source files.
