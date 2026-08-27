DTVS Windows 离线 Pilot 一键启动器

把本目录四个文件复制到 K:\dtvs，并确保同目录存在：

- DTVS-Worker-Pack-v0.1.0-Windows-x64.zip
- DTVS-Worker-Pack-v0.1.0-Windows-x64.zip.sha256
- DTVS-P001-OFFLINE-HANDOFF.zip
- DTVS-P001-OFFLINE-HANDOFF.zip.sha256

运行：

K:\dtvs\START_DTVS_PILOT.cmd

启动器会要求输入两个已知 SHA-256，完成三方 Hash 校验后才解压、Doctor、执行或恢复、导出离线回传包。

可先执行无媒体、无 Doctor、无 Worker 的启动器自检：

K:\dtvs\run_dtvs_offline_pilot.ps1 -SelfTest

可执行完整验证（包含 Doctor，但不会开始渲染）：

K:\dtvs\run_dtvs_offline_pilot.ps1 -VerifyOnly

PowerShell 源码使用 UTF-8 BOM，以兼容 Windows PowerShell 5.1。启动器不会用 SHA-256 摘要冒充 Return Manifest 签名；必须保留并验证 Worker export 产生的真实签名。

终端 Worker 最高状态为 READY_FOR_RETURN，不能生成 ACCEPTED。
