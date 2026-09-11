from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ActorScope:
    """Trusted application context; never construct directly from a request body."""

    tenant_id: UUID
    actor_id: UUID

    def __post_init__(self):
        if not isinstance(self.tenant_id, UUID) or not isinstance(self.actor_id, UUID):
            raise TypeError("Tenant and actor must be UUIDs")


class RecordNotFoundError(Exception):
    """Missing, deleted and foreign-tenant records intentionally look identical."""


class VersionConflictError(Exception):
    """The caller must reload before retrying a write."""


class InvalidActorError(Exception):
    """Actor or tenant is inactive, deleted or outside the supplied scope."""
