# P0C offline network-aware placement audit

## Baseline, scope, and review status

- `BASE_SHA`: `8156da4ba113e7c6f4aa2a3eaf8afeb1be4758ca`.
- Remote `main` was fetched and its full SHA checked before branching, and
  checked again after validation. Both checks matched the base above.
- Branch: `codex/dtvs-p0c-network-aware-placement-v01`; the working tree was
  clean and neither a local nor remote branch with this name existed.
- `HEAD_SHA`: resolve with `git rev-parse HEAD` on the review branch; the exact
  final commit is recorded in the PR body/prepared PR body and delivery message.
  Embedding a commit's own SHA in its tracked report would be self-referential.
- Review status: offline implementation tested; **historical performance
  acceptance remains HOLD**. The operator's original Mac artifacts are not
  available in this environment. No historical replay result is reproduced.

The new `dtvs.scheduling` package is standalone and offline. Existing
Coordinator, Worker, Verifier, Merger, signed Bundle schemas, frozen evidence,
dependency declarations, and legacy snapshots are unchanged. Nothing imports
this package into a dispatcher. No merge, deployment, production dispatch,
external release, remote benchmark, R2 upload, or billable cloud operation was
performed by the replay. Git/GitHub operations for code review are outside the
replay's external-action counters.

## Input provenance and reproducible artifacts

The fixture is **SYNTHETIC_FIXTURE**, generated for this change. It contains a
1,024-byte synthetic text record, two synthetic environment profiles, one task
per environment, three repeats, and four routes per repeat. Thus there are
24 route observations and six holdout decisions, not the operator's reported
48 historical observations/48 decisions. The public fixture key is not a
production trust root; its private counterpart was not saved.

Directional summaries (20/8 Mbps and 12/6 Mbps) and all end-to-end elapsed times
are invented test values. They are not measured LAN capacity. The conservative
values (80% of the summaries) are synthetic calibration fields, not empirically
justified confidence bounds. Variability, confidence, currency, and energy are
explicitly not measured. See the [fixture description](../tests/fixtures/p0c_placement/README.md).

| Exact file bytes | SHA-256 |
| --- | --- |
| `tests/fixtures/p0c_placement/dataset.json` | `baf8ce185f0a6b27686f2766cd50467eac0c886f733cb8b380f735382d3e14cd` |
| `tests/fixtures/p0c_placement/fixture.txt` | `079b0a5c3c39cea089f662283c838069ed029ea8c1f259537082e9e49c58c1c5` |
| `tests/fixtures/p0c_placement/manifest.json` | `cf0e8d725f063cf534031ae1d9cb46deb5598ccce017893bc2fc06c4dd8e158c` |
| `tests/fixtures/p0c_placement/public_key.hex` | `0321f645f96877d794ca97989e6b1d52da5165ce139695aa705b9c959ebc43ba` |
| [Replay report](p0c-network-aware-placement/replay/report.json) | `7423eb9d562d3420d8cd25493a7778837ae0f34ae390f1cb2b70f844fba47c0d` |
| [Output manifest](p0c-network-aware-placement/replay/manifest.json) | `aa615738324e8126491c0c519fdf04625430869029ed3571bf89180b6d895992` |

The output manifest binds exact input file bytes, the input manifest, public-key
fingerprint, and output report. Per-decision dataset hashes use canonical JSON;
the manifest separately records exact input-file hashes. Profile source hashes bind canonical
inline source summaries, and their content must agree with the profile. Fixture
content is recomputed against the Bundle and authorization hashes. Every event
link/hash is checked; duplicate event IDs and repeated route samples within a
repeat are rejected. These checks establish internal consistency, not independent
historical authenticity. The event chain and manifest are not externally anchored.
No `INDEPENDENT_RAW_CONTENT_AUTHENTICITY_VERIFIED` claim is made.

## Eligibility, calibration, and quality boundaries

The caller supplies a trusted Ed25519 public key. Both the unchanged v0.2.2
Task Bundle and a separate authorization must verify. The latter binds the
Bundle hash, fixture hash, task and environment, schedulable Bundle-state
snapshot, candidate endpoints, permissions, and verifier/merge requirements.
These are signed operator assertions, not live access checks, hardware probes,
or proof of rights. The package neither grants permissions nor writes verdicts.

Task/asset authorization, source access, source or remote execution permission,
compute capability, privacy, and legal permission precede ranking. Range also
requires explicit support and an access fraction in `(0, 1]`; full-access routes
require fraction 1. Known denial excludes a route. Unknown permission on an
otherwise possible route holds the task, even when a local route is available.

Bundle signature or actual input-content/hash failure yields `HOLD_INTEGRITY`.
An expired lease, terminal Bundle state, disabled verifier, disabled quality gate,
disabled accepted-only merge requirement, or weakened/invalid quality threshold
holds the task. Non-finite values cannot bypass threshold comparisons. Existing
Worker/Verifier/Merger quality gates are not modified or executed by selection.

Every nonlocal route needs both explicit input and result directions. Missing,
stale, future-dated, malformed, reversed, wrong-topology, source-mismatched, or
anomaly-flagged calibration yields `HOLD_NOT_CALIBRATED`; there is no reverse-link
substitution or forced local fallback. TTL ages the observation window's end,
not a refreshable recording timestamp. All times require explicit UTC. The
synthetic replay evaluation time is pinned at `2026-11-04T12:10:00Z`; it is not
a claim that these profiles are calibrated for use now.

## Estimator and holdout methodology

Each `(environment, task, repeat)` is one fold. All routes from the held-out
repeat are excluded before training. Training is restricted to the same task
and environment; independent profiles are never pooled. Each feasible route's
prediction is the arithmetic mean of its training **end-to-end elapsed seconds**.
Missing training samples or held-out coverage holds the fold rather than silently
dropping a route. One-repeat inputs cannot train on themselves.

No elapsed value is interpreted as isolated network time. Independent stage
timings are absent, so no bytes/bandwidth time decomposition is used. Stage,
network, compute, verify, merge, and retry terms are `UNKNOWN`. This is time
ranking, not an economic optimizer. Currency, energy, and confidence contain
`NOT_MEASURED` with null values.

Ranking sees only predictions, with route ID as the deterministic tie-breaker.
The oracle is computed afterwards over eligible, calibrated, observed candidates
only. Relative regret is `selected held-out seconds / feasible oracle seconds - 1`.
Always-local, always-direct, and always-range baselines are evaluated on exactly
the same feasible folds. Ineligible baselines are `NOT_APPLICABLE`, not fallback
selections. The deliberately fastest D route is legally denied and excluded
from predictions, baselines, and oracle. Tests also deny the C path.

| Synthetic profile | Held repeat | Selection | Prediction (s) | Held actual (s) | Feasible oracle (s) | Regret |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| new | 1 | C_RANGE | 12 | 12 | 12 | 0% |
| new | 2 | C_RANGE | 11.5 | 13 | 13 | 0% |
| new | 3 | C_RANGE | 12.5 | 11 | 11 | 0% |
| old | 1 | B_DIRECT | 10.5 | 9 | 9 | 0% |
| old | 2 | B_DIRECT | 9.5 | 11 | 9 | 22.222222% |
| old | 3 | C_RANGE | 9.5 | 12 | 10 | 20% |

| Synthetic profile | Policy mean actual (s) | Always-local (s) | Always-direct (s) | Always-range (s) |
| --- | ---: | ---: | ---: | ---: |
| new | 12 | 15 | 20 | 12 |
| old | 10.666667 | 14 | 10 | 10.333333 |

These adverse old-profile results show the policy can lose to a simple baseline.
The maximum fixture regret is 22.222222%, not the unverified operator-reported
5.603%. No acceptance threshold is inferred from this small synthetic example.
There is no extrapolation to unseen WAN, 5 GHz, production Parquet, genuine
2 GiB inputs, network payments, or energy economics.

## Executed validation

Python 3.12.14; pytest 9.2.0 from the existing project's test extra. Commands ran
from the repository root with `.venv` active. No new dependency was added.

| Command | Actual result | Exit |
| --- | --- | ---: |
| Baseline `python3 -m unittest discover -s tests -v` | 62 executed; 61 passed, 1 failed; no skips | 1 |
| `python3 -m pytest tests/unit/test_p0c_placement.py -q` | 37 passed; 34 subtests passed | 0 |
| Final `python3 -m unittest discover -s tests -v` | 99 executed; 98 passed, 1 failed; no skips | 1 |
| Final `python3 -m pytest -q` | 98 passed, 1 failed; 34 subtests passed; no skips | 1 |
| CLI replay twice to different new directories; `cmp` of both outputs | Byte-identical reports and manifests | 0 |
| `python3 -m compileall -q dtvs/scheduling`; `git diff --check` | Passed | 0 |

Both full runners fail the same pre-existing test:
`WindowsLauncherTests.test_recovery_directory_has_no_attestation_and_complete_hash_manifest`.
It requires the absent, gitignored `dist/DTVS-PILOT-VERIFIED-RECOVERY/` bundle.
No replacement evidence, expected hash changes, test skips, or assertion changes
were used to hide it. The standard editable install also has the previously
diagnosed setuptools multiple-top-level-package discovery error; source-module
execution works and packaging configuration was not changed.

The new suite verifies missing/stale/reversed profiles; unknown topology,
permissions, and source execution; absent return calibration; signed authorization
tampering; wrong public key; expired/terminal state; quality enforcement; Range
support/fraction/rights; actual fixture mismatch; duplicate events/samples;
event mutation/reordering; non-finite data; profile source hashes/content;
repeat leakage; cross-environment isolation; single-repeat HOLD; schema nulls;
and overwrite prevention. Changing held-out times changes regret but neither
predictions nor the chosen route for that fold.

Actual replay audit counters are all zero: unauthorized selections, holdout
leakage, `PRODUCTION_DISPATCH_COUNT`, `EXTERNAL_NETWORK_ACTIONS`, and
`CLOUD_BILLABLE_ACTIONS`. Socket calls are forbidden during a replay test; an
AST check also rejects network/process/executor imports in the package. Counters
describe this engine, not arbitrary extensions or external Git review tooling.

Input bytes are compared before/after replay, and input/output-directory reuse
is refused. Output files use exclusive creation and read-only permissions.
This is an accidental-overwrite guard, not immutable storage against an owner
or administrator. Existing source and frozen evidence remain unchanged. A
redacted pattern scan and manual review of new text found no embedded
credentials, private keys, user-specific home paths, private host addresses,
or MAC addresses; public fixture keys/signatures are intentionally included.
Pattern scans are not a forensic audit of existing binary release archives.

Reproduce using the fixture README's CLI command and a fresh output directory.
The committed report/manifest are the actual successful final CLI outputs,
not hand-authored summaries or historical operator artifacts.

## Outstanding evidence and infrastructure anomalies

The workflow reports two real two-host LAN pilots of synthetic 64 MiB fixed
records, each 24/24 accepted. It reports directional receiver observations of
31.5 Mbps in one direction, 13.5 Mbps with `iperf3 -R`, and 18.9 Mbps when the
other host explicitly sent. Those numbers, reverse-direction pauses, and high
retransmission statistics have not been independently verified here. Direction
cannot be inferred from task names or reverse-mode labels alone; the old and
new Wi-Fi environments must remain separate. No diagnostic traffic was sent.

The Mac P0-C1 output manifest, sanitized report, and decisions were not supplied.
Its reported seven passing tests, completion marker, 48 observations/decisions,
and regret therefore remain operator-reported evidence. Review of those artifacts
and their checksums remains a prerequisite to historical performance acceptance.
The supplied workflow also notes no external event-chain anchor and no independent
original-content verification in that earlier tool. This implementation does not
retroactively strengthen those claims.

GitHub API reads returned `Forbidden`; an unauthenticated connectivity check
failed at the proxy CONNECT step with 403, including after sandbox escalation.
Git repository reads work. The exact `api.github.com` addition was saved to the
environment configuration draft while preserving existing presets; that save
does not apply runtime access. Draft PR creation must be confirmed separately;
no PR existence or remote push success follows from a saved allowlist entry.

Human review can approve offline code only, request revision, or hold pending
provenance review. Live adaptive scheduling, production activation, merge,
deployment, commercial claims, payments, and cross-network economics remain
outside this change.
