# Failure Codes

| Code | Meaning | Default Action |
| --- | --- | --- |
| `BUNDLE_SIGNATURE_INVALID` | Bundle signature invalid | Reject execution |
| `INPUT_HASH_MISMATCH` | Input hash mismatch | Re-download or stop |
| `ENVIRONMENT_UNSUPPORTED` | Environment unsupported | Do not lease task |
| `OUTPUT_STRUCTURE_INVALID` | Frame, format, or timeline invalid | Local reject |
| `LOCAL_SCORE_BELOW_THRESHOLD` | LAS or component score below threshold | Local reject or retry |
| `EVIDENCE_INCOMPLETE` | Evidence missing or unverifiable | Reject upload or cloud reject |
| `CLOUD_HIDDEN_CHECK_FAILED` | Hidden check failed | Reject or human review |
| `LEASE_EXPIRED` | Lease expired | Conflict check or reassign |
| `DUPLICATE_ACCEPTED_RESULT` | Accepted result already exists | Quarantine duplicate |
| `WORKER_STATE_FORBIDDEN` | Worker attempted forbidden state write | Reject transition |

