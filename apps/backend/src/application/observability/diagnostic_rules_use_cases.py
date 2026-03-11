"""診斷規則 CRUD 用例"""

from dataclasses import dataclass

from src.domain.observability.diagnostic import (
    get_default_combo_rules,
    get_default_single_rules,
)
from src.domain.observability.rule_config import (
    DiagnosticRulesConfig,
    DiagnosticRulesConfigRepository,
)


class GetDiagnosticRulesUseCase:
    def __init__(
        self,
        diagnostic_rules_config_repository: DiagnosticRulesConfigRepository,
    ) -> None:
        self._repo = diagnostic_rules_config_repository

    async def execute(self) -> DiagnosticRulesConfig:
        config = await self._repo.get()
        if config is not None:
            return config
        return DiagnosticRulesConfig(
            single_rules=get_default_single_rules(),
            combo_rules=get_default_combo_rules(),
        )


@dataclass(frozen=True)
class UpdateDiagnosticRulesCommand:
    single_rules: list[dict]
    combo_rules: list[dict]


class UpdateDiagnosticRulesUseCase:
    def __init__(
        self,
        diagnostic_rules_config_repository: DiagnosticRulesConfigRepository,
    ) -> None:
        self._repo = diagnostic_rules_config_repository

    async def execute(
        self, command: UpdateDiagnosticRulesCommand
    ) -> DiagnosticRulesConfig:
        config = DiagnosticRulesConfig(
            single_rules=command.single_rules,
            combo_rules=command.combo_rules,
        )
        await self._repo.save(config)
        return config


class ResetDiagnosticRulesUseCase:
    def __init__(
        self,
        diagnostic_rules_config_repository: DiagnosticRulesConfigRepository,
    ) -> None:
        self._repo = diagnostic_rules_config_repository

    async def execute(self) -> DiagnosticRulesConfig:
        await self._repo.delete()
        return DiagnosticRulesConfig(
            single_rules=get_default_single_rules(),
            combo_rules=get_default_combo_rules(),
        )
