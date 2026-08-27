# DTVS Phase 6A-R2：Cloudflare R2任务仓库与自动上传工作流

- **状态**：READY_FOR_CODEX_EXECUTION
- **范围**：只创建/复用R2 Bucket、生成对象清单、上传中心任务输入并逐项校验
- **不包含**：Worker渲染、结果上传、预签名URL服务、最终合成、公开发布
- **依赖**：DTVS Spec v0.2.2、Worker Pack Phase 0–5已完成
- **目标Bucket**：`dtvs-pilot-assets`

## 0. 直接交给Codex的任务指令

你现在负责为 `roalstoney-alt/dtvs` 项目实现 Cloudflare R2任务仓库和中心端自动上传链路。

严格执行本文件。先做只读检查，再创建或复用资源。不得删除Bucket、覆盖其他Run、公开Bucket、输出Secret、上传完整原片、上传完整字幕或上传隐藏验证点。所有远端写入必须来自本轮生成并通过本地Gate的 `upload_manifest.json`。

本任务授权：

- 检查已配置的Cloudflare身份；
- 创建或复用名为 `dtvs-pilot-assets` 的私有R2 Bucket；
- 修改DTVS仓库中的上传代码、配置、测试和文档；
- 将本轮Pilot的允许对象上传到该Bucket；
- 读取远端对象元数据并验证上传结果。

本任务不授权：

- 删除任何Cloudflare资源或远端对象；
- 启用 `r2.dev` 或自定义域名公开访问；
- 创建D1、KV、Queue、Durable Object或新的Worker；
- 将Cloudflare凭据写入代码、配置、日志或Git；
- 上传片源母版、音频、完整字幕、中心私钥或隐藏验证点；
- 生成长期公开下载地址；
- 修改冻结的Spec v0.2.2阈值。

## 1. 先理解R2“目录”

R2是对象存储，不存在必须预先创建的真实文件夹。以下路径：

```text
runs/DTVS-P001-20260827/task-inputs/T0001/input_with_context.mkv
```

是一个完整对象Key。上传该对象后，Cloudflare控制台会按 `/` 显示为类似目录的结构。因此Codex不应创建空目录占位对象。

参考：[Cloudflare R2 Objects](https://developers.cloudflare.com/r2/objects/)

## 2. 冻结的远端对象结构

每个Pilot必须使用独立且不可变的 `run_id`：

```text
runs/<run_id>/
├── public/
│   ├── run_manifest.json
│   └── task_index.json
├── task-inputs/
│   ├── T0001/
│   │   ├── input_with_context.mkv
│   │   ├── task_bundle.json
│   │   ├── task_bundle.sig
│   │   └── public_anchors.json
│   ├── T0002/
│   └── ...
└── upload-control/
    ├── upload_manifest.json
    └── upload_receipt.json
```

本阶段禁止上传：

```text
center/master/source_20m_video.mkv
center/master/source_20m_audio.flac
center/master/subtitles_20m_zh.srt
coordinator/hidden_checks.json
coordinator/private_key.*
inputs/source_master.*
```

## 3. 身份与环境Gate

### 3.1 必需环境

必须检查但不得打印值：

```text
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_API_TOKEN
```

输出只能是：

```text
CLOUDFLARE_ACCOUNT_ID=present|missing
CLOUDFLARE_API_TOKEN=present|missing
```

任何一个缺失时立即停止，状态为 `BLOCKED_CREDENTIALS_MISSING`。

不得执行交互式 `wrangler login` 来绕过缺失Secret。

### 3.2 Wrangler检查

在仓库根目录运行：

```bash
node --version
npm --version
npx wrangler --version
npx wrangler whoami
```

要求：

- Node.js满足当前Wrangler要求；
- Wrangler为4.x或更高；
- `whoami`返回预期Cloudflare账户；
- 不打印Token；
- 若仓库尚未固定Wrangler，加入开发依赖而不是依赖未知全局版本。

Cloudflare建议在项目中本地安装并通过 `npx wrangler` 运行。[Wrangler命令文档](https://developers.cloudflare.com/workers/wrangler/commands/)

## 4. Bucket创建或复用

### 4.1 只读检查

先执行：

```bash
npx wrangler r2 bucket list
```

只允许以下两种分支：

```text
已存在 dtvs-pilot-assets
→ 复用

不存在 dtvs-pilot-assets
→ 创建一次
```

### 4.2 创建

仅在确认不存在时执行：

```bash
npx wrangler r2 bucket create dtvs-pilot-assets
```

随后执行：

```bash
npx wrangler r2 bucket info dtvs-pilot-assets
npx wrangler r2 bucket list
```

验收：

- Bucket名称完全一致；
- Bucket默认保持私有；
- 未启用 `r2.dev`；
- 未连接公开自定义域名；
- 未创建第二个近似名称Bucket。

Cloudflare的Bucket默认不是公开的。[创建R2 Bucket](https://developers.cloudflare.com/r2/buckets/create-buckets/)

## 5. 本地实现文件

Codex应新增：

```text
dtvs/
├── dtvs/storage/
│   ├── __init__.py
│   ├── r2_manifest.py
│   ├── r2_wrangler.py
│   └── upload_policy.py
├── scripts/
│   ├── prepare_r2_upload.py
│   ├── upload_tasks_to_r2.py
│   └── verify_r2_upload.py
├── schemas/
│   ├── r2_upload_manifest.schema.json
│   └── r2_upload_receipt.schema.json
├── configs/
│   └── r2_pilot_upload.json
├── tests/
│   ├── unit/test_r2_manifest.py
│   ├── unit/test_upload_policy.py
│   └── integration/test_r2_uploader_fake.py
└── docs/
    └── R2_OPERATOR_RUNBOOK_CN.md
```

不得把Secret写入 `r2_pilot_upload.json`。

## 6. 上传配置

建议配置：

```json
{
  "schema_version": "0.2.2",
  "bucket": "dtvs-pilot-assets",
  "run_id": "DTVS-P001-YYYYMMDDTHHMMSSZ",
  "local_run_root": "runs/<run_id>",
  "remote_prefix": "runs/<run_id>",
  "wrangler_single_object_limit_bytes": 330301440,
  "overwrite_existing": false,
  "allowed_suffixes": [
    ".mkv",
    ".json",
    ".sig"
  ],
  "forbidden_name_patterns": [
    "source_master",
    "source_20m_video",
    "source_20m_audio",
    "subtitles_20m",
    "hidden_check",
    "private_key",
    ".pem",
    ".key"
  ]
}
```

`330301440`字节即315 MiB。本数值作为本工作流的Wrangler上传Gate，若官方工具在实际运行中报告更低限制，以实际错误为准并停止。

Cloudflare当前说明Wrangler一次上传一个对象，支持的文件最大为315 MB；大文件或批量迁移应使用rclone或其他S3兼容工具。[R2上传对象](https://developers.cloudflare.com/r2/objects/upload-objects/)

## 7. 生成上传清单

`prepare_r2_upload.py` 必须只读取Coordinator已生成的：

```text
run_manifest.json
task_index.json
task-inputs/Txxxx/*
```

并生成：

```text
runs/<run_id>/upload-control/upload_manifest.json
```

最低结构：

```json
{
  "schema_version": "0.2.2",
  "run_id": "DTVS-P001-...",
  "bucket": "dtvs-pilot-assets",
  "remote_prefix": "runs/DTVS-P001-...",
  "created_at": "...Z",
  "objects": [
    {
      "local_path": "runs/.../task-inputs/T0001/input_with_context.mkv",
      "object_key": "runs/.../task-inputs/T0001/input_with_context.mkv",
      "bytes": 0,
      "sha256": "...",
      "content_type": "video/x-matroska",
      "task_id": "DTVS-P001-T0001",
      "classification": "WORKER_DISTRIBUTABLE"
    }
  ],
  "totals": {
    "objects": 0,
    "bytes": 0,
    "tasks": 20
  }
}
```

### 7.1 清单Gate

生成清单前必须确认：

- `run_id`符合安全字符规则，只允许字母、数字、`-`和`_`；
- 本地路径解析后仍位于当前Run目录内，防止路径穿越；
- 恰好包含Task Index登记的全部任务；
- 每个任务都有MKV、Bundle、签名和公开锚点；
- 不包含软链接指向Run目录外；
- 不包含完整片源、音频、字幕、隐藏验证点或密钥；
- 每个文件在读取后立即计算SHA-256和字节数；
- 每个对象Key唯一；
- 任一对象不超过315 MiB；
- 本地Task Bundle和Task Index中的哈希一致。

任一失败时不得开始远端上传。

## 8. 上传策略

### 8.1 Wrangler调用

每个对象使用参数列表调用，不拼接不受信任的shell命令：

```bash
npx wrangler r2 object put "dtvs-pilot-assets/<object_key>" --file "<local_path>" --content-type "<content_type>"
```

官方基本语法参见：[Wrangler R2命令](https://developers.cloudflare.com/r2/reference/wrangler-commands/)

### 8.2 上传顺序

必须按以下顺序：

```text
1. 各任务 input_with_context.mkv
2. 各任务 public_anchors.json
3. 各任务 task_bundle.json
4. 各任务 task_bundle.sig
5. public/task_index.json
6. public/run_manifest.json
7. upload-control/upload_manifest.json
8. upload-control/upload_receipt.json
```

最后才上传索引和Receipt，避免终端看到尚未完整上传的Run。

### 8.3 不覆盖原则

默认：

```text
overwrite_existing=false
```

上传每个对象前必须检查远端是否已有同Key对象：

- 不存在：上传；
- 存在且已由本工具验证为相同字节数和SHA-256：记录 `SKIPPED_IDENTICAL`；
- 存在但无法证明一致：停止，状态 `REMOTE_KEY_CONFLICT`；
- 禁止用 `--force` 或删除远端对象解决冲突；
- 修正任务必须使用新的 `bundle_version`、对象Key或新的 `run_id`。

## 9. 上传校验

不能把Wrangler返回退出码0直接视为最终验收。

每个对象上传后必须：

1. 使用 `wrangler r2 object get`下载到本Run专用临时验证目录；
2. 计算下载副本SHA-256；
3. 与 `upload_manifest.json`比较；
4. 比较字节数；
5. 删除本地临时验证副本，而不是删除R2对象；
6. 写入Receipt。

示例：

```bash
npx wrangler r2 object get "dtvs-pilot-assets/<object_key>" --file "<verify_temp_file>"
```

`upload_receipt.json`最低包含：

```json
{
  "schema_version": "0.2.2",
  "run_id": "...",
  "bucket": "dtvs-pilot-assets",
  "started_at": "...Z",
  "completed_at": "...Z",
  "state": "VERIFIED",
  "objects": [
    {
      "object_key": "...",
      "action": "UPLOADED",
      "bytes": 0,
      "local_sha256": "...",
      "downloaded_sha256": "...",
      "verified": true,
      "attempts": 1
    }
  ],
  "summary": {
    "expected": 0,
    "uploaded": 0,
    "skipped_identical": 0,
    "failed": 0,
    "verified": 0
  }
}
```

只有所有对象 `verified=true` 时，Run上传状态才允许为 `VERIFIED`。

注意：不得把R2 ETag当作DTVS SHA-256。multipart或迁移方式可能改变ETag语义；DTVS必须保持自己的SHA-256证据。

## 10. 重试与恢复

上传工具必须支持：

```bash
python scripts/upload_tasks_to_r2.py \
  --manifest runs/<run_id>/upload-control/upload_manifest.json \
  --resume
```

规则：

- 单对象最多3次尝试；
- 使用有上限的指数退避；
- 已验证对象不重新上传；
- 网络失败后重新下载验证，不凭本地状态猜测成功；
- 同一对象Key不得并发写入；
- 每次尝试追加记录到 `r2_upload_events.jsonl`；
- Ctrl+C后Receipt保持 `PARTIAL`，再次运行可恢复；
- 不得因为单一文件失败而把Run错误标记为 `VERIFIED`。

## 11. 超过315 MiB的处理

如果任一任务MKV超过315 MiB：

```text
state = BLOCKED_OBJECT_TOO_LARGE_FOR_WRANGLER
```

Codex必须停止上传并报告：

- 文件名；
- 字节数；
- 对应任务；
- 建议选择：重新设计任务中间编码，或另立S3 multipart/rclone实施任务。

不得为了满足限制而：

- 降低4K输出要求；
- 静默重编码并改变已签名Bundle；
- 把一个任务随意拆开却不更新全局帧映射；
- 将R2访问密钥直接写进脚本。

R2本身支持更大的对象和multipart；315 MB是Wrangler单对象上传工具限制，不是R2存储上限。[R2平台限制](https://developers.cloudflare.com/r2/platform/limits/)

## 12. 自动化入口

最终应提供：

### PowerShell

```powershell
./scripts/prepare_and_upload_r2_tasks.ps1 `
  -RunId "DTVS-P001-YYYYMMDDTHHMMSSZ" `
  -Bucket "dtvs-pilot-assets"
```

### Python分步命令

```bash
python scripts/prepare_r2_upload.py --run-id <run_id>
python scripts/upload_tasks_to_r2.py --manifest <manifest> --resume
python scripts/verify_r2_upload.py --manifest <manifest>
```

PowerShell包装器只负责顺序调用，核心策略和校验必须位于可测试的Python模块中。

## 13. 测试要求

### 13.1 无Cloudflare环境的测试

必须使用fake command runner测试：

- Bucket存在时不重复创建；
- Bucket不存在时只创建一次；
- 路径穿越被拒绝；
- 禁止文件被拒绝；
- 315 MiB边界；
- 相同Key冲突；
- 上传失败重试；
- 下载哈希不一致；
- PARTIAL恢复；
- Receipt只有全量校验后才为VERIFIED。

### 13.2 真实Cloudflare smoke test

先使用本Run下的小型探针对象：

```text
runs/<run_id>/upload-control/smoke-test.json
```

执行上传、下载、SHA-256比较。成功后才上传任务文件。不得使用独立测试Bucket制造额外资源。

### 13.3 媒体清单检查

测试必须证明：

- `source_master`未进入清单；
- `source_20m_video`未进入清单；
- 音频未进入清单；
- 字幕未进入清单；
- 隐藏验证点和密钥未进入清单；
- 20个任务输入完整进入清单。

## 14. Git与Secret规则

确认 `.gitignore` 至少包含：

```gitignore
.dev.vars
.env
.env.*
secrets/
keys/
*.pem
*.key
runs/**
inputs/**
```

允许提交：

- Python实现；
- PowerShell包装器；
- JSON Schema；
- 无Secret示例配置；
- fake fixtures；
- 测试和操作文档。

不得提交：

- 真实Cloudflare Account ID；
- API Token；
- R2 Access Key ID或Secret；
- 真实预签名URL；
- 电影、字幕、任务MKV、输出视频；
- 私钥和隐藏验证点。

## 15. 执行阶段

### R2-0：基线与身份检查

- 读取Git状态、Spec v0.2.2和Phase 0–5实现；
- 运行现有测试；
- 验证Wrangler版本、Cloudflare身份和Secrets存在性；
- 只读列出Bucket。

Gate：账户正确，现有测试通过，无未处理的用户冲突修改。

### R2-1：存储契约

- 实现上传配置、Schema、Manifest、Receipt和上传策略；
- 完成fake测试。

Gate：未连接Cloudflare也能通过全部策略测试。

### R2-2：Bucket创建或复用

- 复用或创建 `dtvs-pilot-assets`；
- 确认私有；
- 完成smoke test。

Gate：smoke对象上传、下载和SHA-256一致。

### R2-3：真实任务清单

- 对已生成的20个任务建立Manifest；
- 运行所有本地内容和尺寸Gate；
- 人工输出清单摘要供检查。

Gate：20任务齐全，无禁止文件，无超限对象。

### R2-4：上传与逐项验证

- 按冻结顺序上传；
- 下载复核所有对象；
- 生成Receipt；
- 上传最终Manifest和Receipt。

Gate：Receipt为VERIFIED，失败数为0。

### R2-5：交付终端领取准备

本阶段只输出：

- 已验证的Bucket；
- `run_id`；
- task index对象Key；
-总对象数和总字节数；
- Manifest和Receipt SHA-256；
- 下一阶段生成预签名URL所需的对象清单。

不得在本阶段创建公开URL。

## 16. Codex强制回报格式

```markdown
# DTVS R2任务上传结果

- 状态：PASS / PARTIAL / BLOCKED / FAIL
- Cloudflare账户：已验证 / 未验证（不显示ID）
- Bucket：dtvs-pilot-assets
- Bucket动作：REUSED / CREATED / NONE
- Bucket公开状态：PRIVATE / UNKNOWN
- Run ID：...
- Manifest对象数：...
- 任务数：...
- 总字节数：...
- 最大对象：... bytes
- 上传：...
- 跳过相同对象：...
- 失败：...
- 下载复核通过：...
- Manifest SHA-256：...
- Receipt SHA-256：...
- 测试：通过X / 失败Y / 跳过Z
- Git Commit：...
- 未完成项：...
- 下一步：生成短期GET/PUT预签名URL
```

不得输出Cloudflare Secret、完整Account ID、私钥或完整远端授权URL。

## 17. 最终验收

全部满足才算本工作流完成：

| 项目 | Gate |
| --- | --- |
| Bucket | 精确复用或创建一个 `dtvs-pilot-assets` |
| 私有性 | 未启用公开访问 |
| 对象结构 | 全部位于唯一 `runs/<run_id>/` 前缀 |
| 内容边界 | 未上传完整片源、音频、字幕、密钥和隐藏验证点 |
| 完整性 | 20个Task均有MKV、Bundle、签名和公开锚点 |
| 尺寸 | 每个Wrangler上传对象不超过315 MiB |
| 防覆盖 | 远端冲突会停止，不覆盖 |
| 校验 | 所有对象下载副本SHA-256与本地一致 |
| 恢复 | 中断后可从Receipt恢复 |
| 证据 | Manifest、Receipt和事件日志齐全 |
| Git安全 | 无Secret和媒体进入仓库 |

任一项失败时，状态不得标记为PASS，也不得进入终端分发阶段。
