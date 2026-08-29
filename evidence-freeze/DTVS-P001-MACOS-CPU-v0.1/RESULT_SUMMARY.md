# DTVS P001 macOS CPU Smoke v0.1

Status: PASS

The original macOS x86_64 PyTorch CPU Real-ESRGAN smoke evidence completed with exit code 0. The 720x480 input produced a 2880x1920 output using the official Real-ESRGAN source and `RealESRGAN_x4plus.pth`, on CPU with fp32.

- Source commit: `a58bbfd8734c7db0061f4feca9a8de6799ae2c53`
- Source tag: `dtvs-p001-macos-cpu-smoke-v0.1`
- Input SHA-256: `e8ce0d44bde341cc9fb64ee79bff09c7842b7057ecc90fb4ae041367b622f4e9`
- Model SHA-256: `4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1`
- Output SHA-256: `1ab652a12e937820006d12e614ec91ee54f0d1e87edc0c392925ec9ffb945d55`
- Duration: `467.790647` seconds
- Peak RSS: `693026816` bytes
- Fixture used: `false`
- Node usable: `true`

The earlier NCNN/Vulkan failure is preserved as backend-specific `BACKEND_UNAVAILABLE`; it does not reject the node.

This is a post-run evidence freeze and does not claim runtime-time signing.
