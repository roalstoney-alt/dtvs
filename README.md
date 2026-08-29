# DTVS - Distributed Task Fulfilment Standard

DTVS is an open specification and reference implementation for converting unreliable idle compute into verifiable task fulfilment.

This repository preserves the v0.2.1 single-node runner and adds the v0.2.2 asymmetric Coordinator / Worker / Cloud Verifier / Merger implementation surface.

The v0.2.2 implementation uses fixtures and deterministic mocks unless a legal source, FFmpeg, models, and an RTX 4060 environment are supplied by the operator. Fixture results must not be reported as real GPU measurements.

## Verified execution lines

The repository's primary verified evidence line is the macOS x86_64 PyTorch CPU
real-render smoke test. It is frozen at commit
`a58bbfd8734c7db0061f4feca9a8de6799ae2c53` by the annotated tag
`dtvs-p001-macos-cpu-smoke-v0.1`. The evidence proves a real
`RealESRGAN_x4plus` fp32 CPU inference from 720x480 to 2880x1920; it does not
claim RTX, CUDA, Vulkan, performance, or a completed 20-minute pilot. The
post-run freeze records are under
`evidence-freeze/DTVS-P001-MACOS-CPU-v0.1/`.

GPU hardware is optional. A node is usable when it has at least one supported
execution backend; PyTorch CPU is the general fallback. The earlier macOS
NCNN/Vulkan failure is recorded as backend-specific `BACKEND_UNAVAILABLE` and
does not reject the node.

The prior single-node and Windows-oriented implementation history is retained
on the `windows-legacy` branch. That branch is a separate Windows development
line and must not be interpreted as macOS CPU execution evidence. Windows
hardware validation, if performed, requires its own terminal evidence and must
not replace or rewrite the frozen macOS records.
