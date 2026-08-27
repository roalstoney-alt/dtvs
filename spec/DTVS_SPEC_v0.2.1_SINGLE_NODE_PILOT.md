# DTVS Spec v0.2.1 - Single-node Pilot profile

Status: Pilot freeze

The v0.2.1 runner is a single-node 20-minute RTX 4060 evidence unit. Its state machine is:

`CREATED -> PREFLIGHT_PASSED -> SEGMENT_FROZEN -> CHUNK_EXTRACTED -> CHUNK_UPSCALED -> CHUNK_ENCODED -> CHUNK_ACCEPTED -> ASSEMBLED -> QC_COMPLETE -> VERIFIED | FAILED`

This profile must not be silently deleted or rewritten by the v0.2.2 Worker Pack implementation.

