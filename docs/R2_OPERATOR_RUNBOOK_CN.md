# R2 Operator Runbook

本阶段只上传 Worker 可分发任务对象到私有 `dtvs-pilot-assets` Bucket。

禁止上传完整原片、20分钟中心母版、音频、字幕、隐藏验证点、私钥或 Secret。

```powershell
./scripts/prepare_and_upload_r2_tasks.ps1 -RunId "<run_id>" -Bucket "dtvs-pilot-assets"
```

每个对象必须通过下载副本 SHA-256 复核后才写入 `upload_receipt.json` 的 `VERIFIED` 状态。

