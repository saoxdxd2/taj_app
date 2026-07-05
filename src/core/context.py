from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from typing import Set

@dataclass
class RequestContext:
    """
    Enterprise Execution Context.
    Passed to all business layer methods to provide contextual boundaries.
    """
    user_id: str
    username: str
    role: str
    permissions: Set[str] = field(default_factory=set)
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    workstation: str = "Unknown"
    language: str = "en"
    timestamp: datetime = field(default_factory=datetime.utcnow)
