from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "0.2.2"


@dataclass(frozen=True)
class FrameRange:
    start_frame: int
    end_frame_exclusive: int

    def __post_init__(self) -> None:
        if self.start_frame < 0:
            raise ValueError("start_frame must be non-negative")
        if self.end_frame_exclusive <= self.start_frame:
            raise ValueError("end_frame_exclusive must be greater than start_frame")

    @property
    def frame_count(self) -> int:
        return self.end_frame_exclusive - self.start_frame

    def to_dict(self) -> dict[str, int]:
        return {
            "start_frame": self.start_frame,
            "end_frame_exclusive": self.end_frame_exclusive,
        }


@dataclass
class TaskBundle:
    task_id: str
    bundle_version: int
    asset_id: str
    core: FrameRange
    context: FrameRange
    input: dict[str, Any]
    execution: dict[str, Any]
    output: dict[str, Any]
    lease: dict[str, Any]
    verification: dict[str, Any]
    signature: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "bundle_version": self.bundle_version,
            "asset_id": self.asset_id,
            "core": self.core.to_dict(),
            "context": self.context.to_dict(),
            "input": self.input,
            "execution": self.execution,
            "output": self.output,
            "lease": self.lease,
            "verification": self.verification,
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.unsigned_payload()
        data["signature"] = self.signature
        return data

