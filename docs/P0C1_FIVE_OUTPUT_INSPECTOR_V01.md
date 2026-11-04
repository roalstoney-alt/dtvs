# P0-C1 five-output inspector and derived-summary contract

This additive adapter addresses `DTVS-P0C2-REVIEW-002`. The earlier 23 reviewed
files, synthetic replay, example-only importer, and frozen v0.2.2 implementation
remain unchanged. The new entry point is
`python3 -m dtvs.scheduling.p0c1_output_inspector`; it does not silently relax
the earlier example schema or convert output-only evidence into trusted replay
inputs, permissions, or live placement.

## Exact export contract

Select either the original ZIP or a directory containing these five basenames:

- `manifest.json`
- `report.json`
- `report.md`
- `observations.csv`
- `decisions.csv`

The manifest must claim `input_mode=RAW_RUN_FILES` and list exact SHA-256 values
for the four data members. The original manifest and every member are hashed
without alteration. Matching digests are `PASS_SELF_CONTAINED`, not an external
authenticity anchor. Markdown is hashed, never rendered or executed as instructions.

The CSV headers must be exactly these ordered fields:

```text
profile,query,path,repeat,status,elapsed_s,payload_bytes
profile,scenario,query,heldout_repeat,eligible_paths,selected_path,predicted_s,actual_s,oracle_s,regret_pct,payload_bytes,decision_state
```

The declared inspection domain is `OLD_WIFI`/`NEW_WIFI`, `Q1`/`Q2`, repeats
1/2/3, and the four exact route IDs below. Unknown names and renamed/reordered
columns HOLD rather than being guessed or aliased. A BOM is accepted for CSV
decoding; hashes still cover the original exact bytes.

All 48 observation keys `(profile,query,path,repeat)` must occur exactly once,
with exported status `ACCEPTED`, positive finite elapsed seconds, and nonnegative
integer payload bytes. Counted payload must agree across a route's repeats;
variation is held, not imputed. All 48 decision keys
`(profile,scenario,query,heldout_repeat)` must occur exactly once.
These are **12 distinct exported folds reused in four hypothetical scenarios**,
not 48 independent new task executions. Neither exported status nor manifest
claims authenticate the underlying LAN runs.

| Scenario | Hypothetically feasible routes |
| --- | --- |
| LOCAL_ALLOWED | A, B, C, D |
| LOCAL_FORBIDDEN | A, B, D |
| LOCAL_AND_RANGE_FORBIDDEN | A, B |
| RELAY_ONLY | A |

Scenario sets describe the original offline thought experiment. They are not
signed historical rights, current permissions, or authorization to execute C.
The inspector checks feasible-set equality; it never grants those permissions.

## Reference semantics, not runtime attestation

The distinct namespace is `P0C1_LAN_V01`:

| Exact route ID | Canonical meaning | Supplied v0.1.1 reference description |
| --- | --- | --- |
| A_CENTRAL_RELAY | CENTRAL_RELAY | Full source fetch, then a Mac-local relay-to-worker copy |
| B_DIRECT_SOURCE | DIRECT_SOURCE | Full source fetch directly into the Mac worker file |
| C_IN_SITU | IN_SITU | Source-side compute with a result returned to the Mac |
| D_STREAM_RANGE | STREAM_RANGE | Byte-range fetch and Mac-local aggregation |

A does **not** imply a third physical network host. Its copy stage is simulated
locally on the Mac. Counted payload values do not establish measured NIC traffic
or two distinct network links. These descriptions come from the supplied review,
not independently inspected deployed code or runtime attestation, so the status
is `PROVISIONAL_REFERENCE_ONLY`. Unrecognized or conflicting names HOLD. The
synthetic `A_LOCAL/B_DIRECT/C_RANGE/D_REMOTE` IDs are never mapped by letter.

## Original arithmetic rule and explicit reference requirements

For each candidate in a fold, use only the other two repeats of the same
profile, query and route. Predict their **median** end-to-end elapsed time.
Include feasible routes within 3% of the minimum prediction, inclusively. Among
them choose the lowest recorded counted-LAN payload, then the explicitly
declared final route priority. Held-out elapsed and the feasible hindsight oracle
are accessed only after selection. Predictions never pool profiles or queries.
The synthetic P0-C2 ranker is not called.

The selected path, four-decimal predicted/actual/oracle values, declared CSV
regret precision, selected payload, and hypothetical feasible sets must match.
Regret is `(held-out actual / feasible held-out oracle - 1) * 100`. A forced
RELAY_ONLY zero regret describes a singleton oracle, not good performance.
Independent network-stage timing, monetary/energy costs, fresh directional
calibration, and physical execution claims are not produced.

The two supplied Markdown reviews do not enumerate the final tie ordering,
`eligible_paths` serialization, exact decision-state string, or original report
statistic locations. Those are not inferred from exported selections or guessed
from example schemas. For arithmetic validation, supply an explicit JSON
reference with **exactly** these fields:

| Field | Required value or meaning |
| --- | --- |
| `schema_version` | `p0c1-output-reference-v0.1` |
| `route_namespace` | `P0C1_LAN_V01` |
| `source_reference_sha256` | Declared SHA-256 of the reviewed reference; not an externally verified anchor |
| `tie_priority` | All four exact route IDs, once each, in the original program's final order |
| `eligible_paths_encoding` | Explicit `JSON_ARRAY` or `PIPE_SEPARATED`; other encodings HOLD |
| `decision_state` | Exact original exported state string |
| `expected_report_policy` | Exact original `report.json.policy` value, compared as canonical JSON including types |
| `csv_regret_decimals` | Original exported regret precision, 0 through 9 |
| `report_checks` | Explicit report JSON pointers and the statistics described next |

Each report check has exactly `pointer`, `profile`, `scenario`, `statistic`,
and `decimals`. The profile/scenario identify one of eight groups, or are both
null for the overall statistic. No recursive search or field-name guessing is
used. At minimum, independently check each group's `decision_count`,
`mean_actual_s`, `mean_regret_pct`, and `max_regret_pct`, plus the overall maximum
(33 checks). Group counts must be exact integers. Optional checks can cover
mean prediction/oracle/payload and per-route selection counts. Missing report
locations or inconsistent statistics HOLD.

Construct this reference only from the actual original policy/layout and retain
its attribution. Do not reverse-engineer tie priorities to fit the decisions.
The reference is a caller-selected comparison contract; its source authenticity
is still `NOT_VERIFIED`. Tests supply clearly invented reference contracts, not
the unavailable original policy. Without a reference, hashes and grid can be
checked but arithmetic stays `NOT_RUN` with `HOLD_POLICY_REFERENCE_REQUIRED`.

## Read safety, opt-in, and persistent HOLDs

Explicit `--allow-p0c1-output-inspection` or API `opt_in=True` is required before
operator input or reference reads. No source discovery or network access occurs.
ZIPs are read in memory, never extracted. They must have exactly five unique
root members; traversal/nested/extra names, directories, symlinks, nonregular
entries, encryption and unsupported compression are refused. CRC/decompression
errors HOLD. Limits are 8 MiB/member, 32 MiB total/archive and compression ratio
200. Directory reads use fixed basenames and no-follow regular-file opens.
Invalid JSON/Unicode, duplicate keys/rows, nonfinite numbers and malformed records
are refused with controlled codes, without echoing source values.

Every result maintains:

- `status=HOLD_PROVENANCE`
- `permissions_status=HOLD_ELIGIBILITY_UNKNOWN`; historical permissions HOLD
- `historical_performance_acceptance=HOLD`
- external source/code authenticity and runtime attestation `NOT_VERIFIED`
- `production_dispatch=DISABLED`, `merge=NO`, `deploy=NO`

No signing keys, signed Bundles, external anchors, permissions, current network
profiles or production placements are generated. Original source-run event
chains are not present in output-only exports and are not claimed verified.

Example once the actual ZIP and an explicit reference are available, from the
repository root with the existing virtualenv active:

```bash
python3 -m dtvs.scheduling.p0c1_output_inspector \
  --allow-p0c1-output-inspection \
  --source inputs/p0c1/DTVS_P0C1_Evidence_Review.zip \
  --policy-reference inputs/p0c1/original-policy-reference.json \
  --output-dir runs/p0c1-review-002
```

Omit `--policy-reference` for hash/grid inspection only. Exit 2 means a HOLD
summary (including otherwise successful output validation), exit 3 means missing
opt-in/no input reads, and exit 4 means output refusal. Use a new output directory
each time. Existing files/directories/symlinks are never overwritten. Invalid or
unavailable reference input returns controlled HOLD exit 2.

## Derived redaction for audit/public review

Keep originals and explicit policy references outside tracked files, preferably
in ignored `inputs/`. Do not commit or rewrite the operator ZIP/JSON/CSV, its
account paths, tokens, network addresses, or original provenance claims.

`write_summary` creates **new derived files** `validation.json` and `manifest.json`:

1. Recompute exact original ZIP/member hashes without altering those bytes.
2. Emit only this version's controlled status/reason enums, neutral fixed profile
   and route IDs, counts, arithmetic checks and aggregate statistics. Never copy
   raw report fields, CSV rows, arbitrary identifiers, paths or token text.
3. Mark reference semantics provisional and source authenticity unverified.
4. Hash the newly serialized derived validation file. The derived manifest links
   its **new** hash to unchanged source hashes and the canonical-reference hash;
   it never labels redacted data with an original member hash.
5. Create exclusively in a fresh directory and mark outputs read-only. Review
   this bounded derived summary's privacy before publication. Publishing derived
   audit summaries does not authorize publishing original operator files.

The revision's committed validation scope explicitly labels its CLI example as
synthetic. It contains no original operator output. Self-contained hashes and
arithmetic PASS on that example do not claim historical 48/48 revalidation.
