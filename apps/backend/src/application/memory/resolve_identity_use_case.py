"""身份解析用例 — 根據 visitor_id + source 解析或建立 VisitorProfile"""

from dataclasses import dataclass

import structlog

from src.domain.memory.entity import VisitorProfile
from src.domain.memory.repository import VisitorProfileRepository
from src.domain.memory.value_objects import VisitorProfileId

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ResolveIdentityCommand:
    tenant_id: str
    source: str  # "widget" | "line" | "jwt"
    external_id: str


class ResolveIdentityUseCase:
    def __init__(
        self, visitor_profile_repository: VisitorProfileRepository
    ) -> None:
        self._profile_repo = visitor_profile_repository

    async def execute(self, command: ResolveIdentityCommand) -> str:
        """Resolve identity to a profile_id. Creates profile if not found.

        Returns:
            profile_id (str)
        """
        # Look up existing identity
        identity = await self._profile_repo.find_identity(
            tenant_id=command.tenant_id,
            source=command.source,
            external_id=command.external_id,
        )
        if identity is not None:
            logger.debug(
                "identity.resolved",
                profile_id=identity.profile_id,
                source=command.source,
            )
            return identity.profile_id

        # Create new profile + identity
        profile = VisitorProfile(
            id=VisitorProfileId(),
            tenant_id=command.tenant_id,
        )
        await self._profile_repo.save(profile)

        new_identity = profile.add_identity(
            source=command.source,
            external_id=command.external_id,
        )
        await self._profile_repo.save_identity(new_identity)

        logger.info(
            "identity.created",
            profile_id=profile.id.value,
            source=command.source,
            tenant_id=command.tenant_id,
        )
        return profile.id.value
