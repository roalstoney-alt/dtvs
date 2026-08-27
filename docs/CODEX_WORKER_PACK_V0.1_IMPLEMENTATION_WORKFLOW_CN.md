# DTVS Worker Pack v0.1 与 20 分钟单机 Pilot：Codex 实施工作流

文档状态：READY_FOR_IMPLEMENTATION

本地实现必须保留 v0.2.1 Runner，新增 Coordinator、Worker Pack、Cloud Verifier、Merger。Worker 最高只能写到 `UPLOADED`。Phase 0 从基线保护开始，逐阶段测试和提交；没有 RTX 4060、合法片源、模型环境时，Phase 6 停止并输出人工实测命令，不得伪造结果。

