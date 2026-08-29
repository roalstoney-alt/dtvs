# Verification Commands

These commands are read-only and do not re-run inference.

```sh
git status --short
git rev-parse a58bbfd8734c7db0061f4feca9a8de6799ae2c53^{tree}
git cat-file -p dtvs-p001-macos-cpu-smoke-v0.1
shasum -a 256 runs/DTVS-P001-20260827T065301Z/local-real-render-proof/smoke/input.png
shasum -a 256 runs/DTVS-P001-20260827T065301Z/local-real-render-proof/cpu-runtime/cpu-smoke/output_x4.png
python3 -c "from PIL import Image; print(Image.open('runs/DTVS-P001-20260827T065301Z/local-real-render-proof/cpu-runtime/cpu-smoke/output_x4.png').size)"
```

Expected tag target: `a58bbfd8734c7db0061f4feca9a8de6799ae2c53`.
