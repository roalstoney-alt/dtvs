# DTVS Spec v0.2.2 - 非对称可验证媒体计算流程（冻结稿）

- 状态：FROZEN / Pilot implementation baseline
- 冻结日期：2026-08-27

v0.2.2 separates Coordinator, Worker, Verifier, and Merger responsibilities. LAS >= 90 is an upload gate and 不是中心最终验收. NRS is separate from LAS.

Required concepts include 保密验证点, ACCEPTED-only merge, 中位数 and percentile cost reporting, signed Task Bundles, hidden checks, deterministic rerender selection, and immutable event transitions.

Legal states:

`CREATED -> LEASED -> RUNNING -> LOCAL_REJECTED | UPLOADING -> UPLOADED -> CLOUD_CHECKING -> ACCEPTED | REJECTED | HUMAN_REVIEW | REASSIGNED`

