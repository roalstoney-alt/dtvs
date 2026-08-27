from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from dtvs.common.canonical_json import dumps
from dtvs.common.hashing import sha256_bytes

State = Literal[
    "CREATED",
    "LEASED",
    "RUNNING",
    "LOCAL_REJECTED",
    "UPLOADING",
    "UPLOADED",
    "CLOUD_CHECKING",
    "ACCEPTED",
    "REJECTED",
    "HUMAN_REVIEW",
    "REASSIGNED",
]

ROLE_MAX_STATES = {
    "coordinator": {"CREATED", "LEASED", "REASSIGNED"},
    "worker": {"RUNNING", "LOCAL_REJECTED", "UPLOADING", "UPLOADED"},
    "verifier": {"CLOUD_CHECKING", "ACCEPTED", "REJECTED", "HUMAN_REVIEW"},
    "merger": set(),
}

ALLOWED: dict[str, set[str]] = {
    "CREATED": {"LEASED"},
    "LEASED": {"RUNNING", "REASSIGNED"},
    "RUNNING": {"LOCAL_REJECTED", "UPLOADING", "REASSIGNED"},
    "UPLOADING": {"UPLOADED", "REASSIGNED"},
    "UPLOADED": {"CLOUD_CHECKING"},
    "CLOUD_CHECKING": {"ACCEPTED", "REJECTED", "HUMAN_REVIEW"},
    "LOCAL_REJECTED": {"REASSIGNED"},
    "REJECTED": {"REASSIGNED"},
    "HUMAN_REVIEW": {"ACCEPTED", "REJECTED"},
    "ACCEPTED": set(),
    "REASSIGNED": {"LEASED"},
}


@dataclass(frozen=True)
class TransitionEvent:
    old_state: str
    new_state: str
    actor: str
    reason_code: str
    evidence_hash: str
    timestamp_utc: str

    def to_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


def transition(old_state: str, new_state: str, *, actor: str, reason_code: str, evidence: dict) -> TransitionEvent:
    if new_state not in ALLOWED.get(old_state, set()):
        raise ValueError(f"illegal transition {old_state} -> {new_state}")
    if new_state not in ROLE_MAX_STATES.get(actor, set()):
        raise PermissionError(f"{actor} cannot write {new_state}")
    evidence_hash = sha256_bytes(dumps(evidence))
    return TransitionEvent(
        old_state=old_state,
        new_state=new_state,
        actor=actor,
        reason_code=reason_code,
        evidence_hash=evidence_hash,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )

