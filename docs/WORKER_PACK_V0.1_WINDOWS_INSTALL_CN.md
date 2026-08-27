# Worker Pack v0.1 Windows 安装说明

## 必需环境

- Windows 10/11
- Python 3.11+
- FFmpeg/ffprobe 6+，PATH 可调用
- NVIDIA Driver 与 `nvidia-smi`
- RTX 4060 或操作者明确记录的等价测试环境
- 官方 `realesrgan-ncnn-vulkan` executable 与模型文件

## 本地文件

- `inputs/source_master.mkv`
- `inputs/subtitles_zh.srt`
- `tools/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe`
- `tools/realesrgan-ncnn-vulkan/models/*`

不得提交片源、字幕、模型、私钥或 `runs/**` 运行结果。

## 预检

```powershell
python -m dtvs.cli --version
./scripts/run_v022_pilot.ps1 -Config configs/metropolis_20m_v022.json
```

没有真实媒体、模型和 RTX 4060 时，只能运行 fixture 路径，报告中必须保留 `SKIPPED_WITH_REASON`。

