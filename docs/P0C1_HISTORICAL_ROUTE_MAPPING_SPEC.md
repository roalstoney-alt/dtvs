# P0-C1 historical LAN route semantics, version 0.1

This specification implements `DTVS-P0C2-REVIEW-001`. It defines a separate
inspection namespace, `P0C1_LAN_V01`. Historical performance acceptance remains
**HOLD**. Classification is not a placement, eligibility decision, permission
grant, proof of rights, or confirmation that the declared topology was observed.

## Canonical mapping and required facts

| Historical label | Canonical semantic route | Execution site | Input role path | Input access |
| --- | --- | --- | --- | --- |
| A | CENTRAL_RELAY | WORKER | SOURCE → CENTRAL → WORKER | FULL_OBJECT |
| B | DIRECT_SOURCE | WORKER | SOURCE → WORKER | FULL_OBJECT |
| C | IN_SITU | SOURCE | SOURCE | IN_PLACE |
| D | STREAM_RANGE | WORKER | SOURCE → WORKER | BYTE_RANGE_STREAM |

Roles describe the input's logical path, not machine addresses or distinct host
counts. A relay's staging/forwarding distinguishes A from B; executing where the
input resides distinguishes C from D. D streams byte ranges to a worker; it is
not source-side execution. Result transfer paths, host identities, actual Range
support, access fraction, rights, quality, and directional network calibration
remain separate evidence requirements. None is inferred from this table.

`classify_route` matches **all three structural facts first**, using exact enum
values and an explicit namespace. Only then does it check a historical letter
for consistency. Letter-only records and canonical names without structural
facts produce `HOLD_SEMANTIC_MAPPING`. A record labeled C with stream-range
facts produces a conflict HOLD; it is not silently renamed to D. An opaque
nonletter identifier can classify only through its explicit structural facts.
Conflicting canonical declarations, missing namespace, and unsupported role
paths also HOLD. There is no fuzzy matching or inferred endpoint direction.

## Separation from the reviewed synthetic fixture

The original 15 files and their synthetic replay remain byte-for-byte unchanged.
Its `A_LOCAL`, `B_DIRECT`, `C_RANGE`, `D_REMOTE` labels do not define historical
A/B/C/D. In particular, synthetic `C_RANGE` does not mean historical C=IN_SITU,
and synthetic A_LOCAL does not mean A=CENTRAL_RELAY. Its `LOCAL`, `DIRECT`,
`RANGE`, `REMOTE` modes are not accepted as historical semantic evidence.

No automatic conversion into the signed replay is provided. The earlier replay
does not encode the historical central-relay path or establish the operator's
historical source-execution permissions. Reusing its fixture signatures or
inventing signed authorization to bridge that gap is prohibited. The new
inspection code does not import signing, ranking, or replay modules.

## Separate opt-in artifact inspection

The importer reads only a caller-selected directory and requires
`--allow-sanitized-p0c1-import` (or API `opt_in=True`). No opt-in means no source
reads and no output creation. It does not search an operator's machine, fetch
files, run network measurements, or discover credentials.

Recognized inspection contract:

1. `manifest.json` contains the operator's `input_mode: RAW_RUN_FILES` **claim**
   and `files_sha256`. Required listed files are `report.md` and `report.json`;
   `decisions.csv` is optional. Digests must be lowercase SHA-256. Other listed
   basenames/layouts HOLD without opening those files. Do not rewrite an
   original manifest or invent missing files to satisfy this contract.
2. The importer recomputes the exact bytes of every listed allowed output.
   Symlinks, nonregular files, missing files, unsafe paths, oversized artifacts
   (over 8 MiB each), duplicate JSON keys, invalid Unicode, and non-finite JSON
   are refused. Unmanifested optional files are not imported.
3. `report.json` must contain `status: OFFLINE_REPLAY_ONLY` and positive integer
   `observations` and `holdout_decisions`. They are copied as **reported counts**,
   never treated as verified raw observations. Markdown is hashed, not rendered
   or interpreted as instructions.
4. Optional `report.json.route_semantics` contains records with these fields:

   ```json
   {
     "route_namespace": "P0C1_LAN_V01",
     "environment_profile_id": "sanitized-profile-id",
     "source_route_id": "C",
     "execution_site": "SOURCE",
     "input_path": ["SOURCE"],
     "input_access": "IN_PLACE",
     "declared_canonical_route": "IN_SITU"
   }
   ```

   `declared_canonical_route` is optional; the structural facts are required.
   Metadata must come from actual operator evidence, not an invented assertion
   added to pass this validator. If the original report lacks these facts,
   retain it unchanged and report `ROUTE_SEMANTICS_NOT_SUPPLIED`. Independently
   reviewed metadata needs a separately specified evidence link in future work.
   A mapping result means only that the supplied facts match this specification.
5. Optional `decisions.csv` must have explicit columns
   `environment_profile_id,task_id,repeat_id,source_route_id`. It is checked for
   known per-profile route records, duplicate decision identities, and agreement
   with the reported decision count. Extra columns are not interpreted. Other
   layouts HOLD; route labels or timing values are never guessed into columns.
   Environment profiles remain separate. No latency or regret is recomputed.

This is a bounded validation contract based on the supplied workflow's known
fields, not a claim of compatibility with an uninspected P0-C1 export. The actual
operator files have not been supplied. An unsupported layout remains HOLD until
the real schema is inspected and an explicit adapter is reviewed. Tests use
invented contract examples, not historical raw data or permission evidence.

## Provenance HOLD and output contract

Even when all listed output hashes match, semantic mappings succeed, and CSV
counts agree, the result is **HOLD_PROVENANCE**:

- Original fixture content and raw observations are not available or independently
  authenticated by these output artifacts.
- The manifest and event chain are not externally anchored. The importer does
  not claim to validate raw events it has not received.
- Historical permissions and legal/quality evidence remain
  `HOLD_ELIGIBILITY_UNKNOWN`; source execution is not authorized by C=IN_SITU.
- `historical_performance_acceptance` is always `HOLD`. There is no flag or
  report field that promotes acceptance, permission, or production dispatch.
- Signature, permission-assertion, placement, network, billable-action, and
  production-dispatch creation counts remain zero. No signed Bundle, replay
  dataset, candidate set, placement decision, or synthetic signature is emitted.

Malformed or inconsistent artifacts give `HOLD_ARTIFACT_VALIDATION`. Missing or
contradictory semantic facts add semantic HOLD reasons. The output preserves
controlled status/reason enums, hashes, counts, and canonical semantic names;
arbitrary profile/route identifiers are hashed rather than echoed. Only the
known A/B/C/D labels may be echoed. Raw reports, CSV rows, permission claims,
and unrecognized fields are not copied into output.

Outputs `validation.json` and `manifest.json` are created exclusively in a new
directory and marked read-only. Existing outputs (including symlinks) are
refused. Inputs are never rewritten. The output manifest binds the captured
source manifest, validated source hashes, and validation output; this is
consistency evidence, not an external authenticity anchor.

Example after the actual sanitized operator files are supplied, from the repo
root with the existing project virtualenv active:

```bash
python3 -m dtvs.scheduling.historical_import \
  --allow-sanitized-p0c1-import \
  --input-dir inputs/p0c1-sanitized \
  --output-dir runs/p0c1-inspection-001
```

Use a fresh output directory each time. Exit **2** means an inspection report
was written and remains HOLD, including validation failures. Exit **3** means
opt-in was absent and no input was read. Exit **4** means output was refused or
unavailable. There is deliberately no acceptance/dispatch exit 0. Keep operator
inputs in the ignored input directory; do not commit private material.
