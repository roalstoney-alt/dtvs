# Pilot v0.2.2 操作 Runbook

## 运行前 Gate

1. 人工确认素材、字幕、模型均具备合法使用边界。
2. 确认配置不含绝对路径、私钥或操作者隐私。
3. 确认 `configs/metropolis_20m_v022.json` 中帧范围为 20 分钟窗口。
4. 确认磁盘空间、睡眠策略和电源记录方式。

## 正式运行命令

```powershell
./scripts/run_v022_pilot.ps1 -Config configs/metropolis_20m_v022.json
```

## 输出检查

检查 `runs/<run_id>/`：

- `coordinator/asset_manifest.json`
- `coordinator/task_index.json`
- `coordinator/hidden_check_summary.json`
- `simulated_cloud/inbox/**/cloud_verdict.json`
- `merge/delivery.json`
- `fault_injection_report.json`
- `pilot_summary.json`
- `pilot_summary.md`

只有全部任务 `ACCEPTED` 且合并 Gate 通过时，才能进入完整交付判断。fixture 或 mock 结果不得标记为 RTX 4060 实测。

