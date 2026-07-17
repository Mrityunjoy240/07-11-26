import os
from dataclasses import dataclass, field
from typing import Dict, Callable


@dataclass
class FeatureFlags:
    """Central feature flag registry. All flags default to False (off).

    Environment variable convention: FF_<NAME> = "1" to enable.
    """

    # Phase 0: Foundation
    use_pipeline: bool = False
    use_event_bus: bool = False
    use_channel_adapters: bool = False

    # Phase 1: Channel Adapters
    use_web_adapter: bool = False
    use_telephony_adapter: bool = False

    # Phase 2: Stage Pipeline
    use_intent_stage: bool = False
    use_fee_engine_stage: bool = False

    # Phase 3: Observability
    use_event_driven_logging: bool = False
    use_structured_tracing: bool = False

    # Phase 4: Multi-tenant
    use_tenant_isolation: bool = False
    use_tenant_aware_routing: bool = False

    # Migration enforcement
    migration_deadline: str = ""  # ISO date e.g. "2026-10-01"
    migration_enforced: bool = False  # set to True after deadline

    _registry: Dict[str, Callable[[], bool]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._load_from_env()
        self._check_migration_deadline()

    def _load_from_env(self) -> None:
        for field_name in self.__dataclass_fields__:
            if field_name.startswith("_"):
                continue
            env_val = os.environ.get(f"FF_{field_name.upper()}")
            if env_val is not None:
                setattr(self, field_name, env_val.strip() in ("1", "true", "True", "yes"))

    def _check_migration_deadline(self) -> None:
        if not self.migration_deadline:
            return
        from datetime import datetime, timezone
        try:
            deadline = datetime.fromisoformat(self.migration_deadline)
            if datetime.now(timezone.utc) > deadline.replace(tzinfo=timezone.utc):
                self.migration_enforced = True
                import warnings
                warnings.warn(
                    f"MIGRATION DEADLINE {self.migration_deadline} HAS PASSED. "
                    "Set FF_USE_PIPELINE=1 and remove legacy code paths."
                )
        except ValueError:
            pass

    def is_enabled(self, flag: str) -> bool:
        return bool(getattr(self, flag, False))


# Singleton
feature_flags = FeatureFlags()
