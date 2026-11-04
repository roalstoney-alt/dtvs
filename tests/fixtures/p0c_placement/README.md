# Synthetic offline placement fixture

This is newly generated test data, not either historical LAN pilot or the
operator's P0-C1 raw replay. The 1,024-byte `fixture.txt` is a synthetic record,
not 64 MiB media or 2 GiB Parquet. No private key, pairing token, host address,
SSID, account name, or operator home path is included.

`dataset.json` contains two independent synthetic environments, one task per
environment, three repeats, and four routes per repeat: 24 route observations
and six leave-one-repeat-out decisions. All elapsed values are invented
end-to-end seconds. Directional throughput summaries are invented separately:
20/8 Mbps and 12/6 Mbps, with conservative values at 80% of each summary.
They do not measure either Wi-Fi pilot and are not used to compute elapsed
latency. Variability and confidence are not measured.

Each profile references a canonical SHA-256 of its inline `profile_sources`
record; the record's summary fields must agree with the profile. These are
self-contained synthetic summaries, not independent throughput logs. The input
manifest hashes exact dataset and fixture bytes. Events form an unanchored
SHA-256 chain, with duplicate sample identities rejected.

The two v0.2.2 Task Bundles and their separate authorizations are signed by a
fixture-only Ed25519 key. `public_key.hex` is public and appropriate only for
this fixture. Its private counterpart was not saved. For real evidence, the
caller must establish public-key trust and rights/permission assertions outside
this package. Hashes and fixture signatures do not establish real authorization
or externally anchored historical authenticity.

The deliberately fastest `D_REMOTE` route is legally ineligible. `C_RANGE`
requires explicit Range support and a 0.25 access fraction. Unit tests also
deny the C path and verify its exclusion from predictions, baselines, and the
oracle. Permission/quality snapshots are signed offline assertions; no remote
permission checks, hardware discovery, task dispatch, verdict, or merge runs.

Run from the repository root with the project environment active:

```bash
python3 -m dtvs.scheduling.replay \
  --input-dir tests/fixtures/p0c_placement \
  --trusted-key tests/fixtures/p0c_placement/public_key.hex \
  --as-of 2026-11-04T12:10:00Z \
  --output-dir runs/p0c-review-001
```

Choose a new output directory for each replay; existing directories and
symlinks are refused. Output files are created exclusively and marked read-only.
This prevents accidental overwrite through this API, not owner/admin tampering.
