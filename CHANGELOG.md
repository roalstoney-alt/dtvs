# Changelog

## Local WebM Phase 6A→6B workflow — 2026-08-27

- added a local-Codex source discovery and immutable-copy gate for WebM files in Downloads;
- defined full decode, CFR/timebase, 20-minute master, audio/subtitle, task compilation, and signing gates;
- connected verified task generation to the private R2 upload workflow;
- blocked cloud-only execution, ambiguous source selection, invented subtitles, and publication of source media.

## Phase 6A-R2 upload workflow — 2026-08-27

- defined safe create-or-reuse provisioning for the private `dtvs-pilot-assets` bucket;
- specified immutable run prefixes, upload manifests, receipts, SHA-256 download verification, and resume behavior;
- prohibited source masters, audio, subtitles, hidden checks, keys, and secrets from task distribution;
- added a 315 MiB Wrangler object gate with an explicit multipart escalation path.

## Worker Pack v0.1 implementation plan — 2026-08-27

- added the Codex-executable architecture and phased development workflow;
- separated Coordinator, Worker, Cloud Verifier, and Merger modules;
- defined schemas, CLI, test matrix, fault injection, reporting, and final acceptance gates;
- preserved the v0.2.1 monolithic runner as a characterization baseline.

## v0.2.2-spec-freeze — 2026-08-27

- froze the coordinator → Worker Pack → cloud verifier → central merge responsibility chain;
- made local `LAS >= 90` an upload gate rather than final acceptance;
- separated per-output LAS from historical Node Reputation Score (NRS);
- specified signed Task Bundles, scene-aware core/context frames, public and hidden verification points;
- added hard gates, weighted soft checks, cloud verification, state transitions, retry and reassignment rules;
- defined a 20-task single-RTX-4060 simulation with fault injection and full traceability;
- required median and percentile economics per accepted 4K minute, including failures and verification costs.

## v0.2.1-pilot-start — 2026-08-27

- froze the first 20-minute single-node RTX 4060 evidence unit;
- defined source, subtitle, configuration, output, checkpoint, energy, QC, and evidence manifests;
- introduced 60-second resumable chunks;
- separated soft-subtitle master from burned-in review output;
- prohibited distributed-network and cost-advantage claims from single-node evidence;
- added median-oriented fields for later node and task economics.

## v0.2

- defined the Task Bundle, lease, checkpoint, evidence, verification, failure, and accepted-result concepts.
