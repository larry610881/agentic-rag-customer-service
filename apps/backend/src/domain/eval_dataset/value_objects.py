from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class EvalDatasetId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class EvalTestCaseId:
    value: str = field(default_factory=lambda: str(uuid4()))
