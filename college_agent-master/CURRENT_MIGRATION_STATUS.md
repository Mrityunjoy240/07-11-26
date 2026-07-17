# Current Migration Status

---

## Overview

The project is mid-migration from a monolithic architecture (GroqService God Object) to a channel-adapter + pipeline-stage architecture. Phase 0 is complete but **inactive** — all new architecture components are behind feature flags that default to `False`.

---

## Completed Phases

### Phase 0 — Foundation (2026-07-13)
**Status:** ✅ Code complete, behind feature flags

**Deliverables:**
- Core interfaces (8 abstract contracts)
- ConversationRequest / ConversationResponse dataclasses
- ConversationEngine (single entry point)
- PipelineRunner with 6 pipeline stages
- WebChannelAdapter (wired to ConversationEngine)
- In-memory EventBus
- Lightweight DI container
- Feature flag registry with migration deadline

**Verification:** All imports pass. All 396 standard tests pass. Zero source code changes to production code paths.

---

## Pending Phases

### Phase 1 — Channel Adapters (Not Started)
| Task | Dependencies | Estimated Effort |
|---|---|---|
| VoiceChannelAdapter | Phase 0 interfaces | 2-3 days |
| TelephonyChannelAdapter | Phase 0 interfaces | 3-5 days |
| Conversation persistence integration | Phase 0 engine | 1-2 days |
| Activate web adapter (FF use_channel_adapters=True) | Stable adapters | 1 day |

### Phase 2 — Stage Pipeline Expansion (Not Started)
| Task | Dependencies | Estimated Effort |
|---|---|---|
| FeeEngineStage extraction from GroqService | Stable pipeline | 2-3 days |
| StructuredLookupStage | Stable pipeline | 1-2 days |
| PromptManager stage | Stable pipeline | 2-3 days |
| Activate pipeline (FF use_pipeline=True) | All stages stable | 1 day |

### Phase 3 — Observability (Not Started)
| Task | Dependencies | Estimated Effort |
|---|---|---|
| Event-driven logging | EventBus | 1-2 days |
| Structured tracing | Phase 1-2 stable | 2-3 days |
| Latency tracking via PipelineRunner | Phase 2 | 1 day |
| Activate event bus (FF use_event_bus=True) | Subscribers exist | 1 day |

### Phase 4 — Multi-tenant (Not Started)
| Task | Dependencies | Estimated Effort |
|---|---|---|
| Tenant isolation | Full Phase 0-3 stable | 3-5 days |
| Tenant-aware routing | Phase 1-2 stable | 2-3 days |
| Database per tenant | Phase 3 | 3-5 days |

---

## Feature Flags

| Flag | Default | Phase | Currently Used By | Migration Plan |
|---|---|---|---|---|
| `use_pipeline` | False | Phase 0 | PipelineRunner, stages | Set True in Phase 2, remove in Phase 3 |
| `use_event_bus` | False | Phase 0 | EventBus | Set True in Phase 3, keep permanently |
| `use_channel_adapters` | False | Phase 0 | WebChannelAdapter | Set True in Phase 1, remove in Phase 3 |
| `use_web_adapter` | False | Phase 1 | (future) | Merge with use_channel_adapters |
| `use_telephony_adapter` | False | Phase 1 | (future) | Set True in Phase 1, remove in Phase 3 |
| `use_intent_stage` | False | Phase 2 | (future) | Remove when use_pipeline=True |
| `use_fee_engine_stage` | False | Phase 2 | (future) | Remove when use_pipeline=True |
| `use_event_driven_logging` | False | Phase 3 | (future) | Keep permanently |
| `use_structured_tracing` | False | Phase 3 | (future) | Keep permanently |
| `use_tenant_isolation` | False | Phase 4 | (future) | Keep permanently |
| `use_tenant_aware_routing` | False | Phase 4 | (future) | Keep permanently |

### Migration Deadline
- `migration_deadline`: "" (not set)
- `migration_enforced`: False
- After setting `migration_deadline` to a past date, the engine emits a warning on every legacy path request

---

## Unused Modules

| Module | Reason Unused | Should Delete? |
|---|---|---|
| `app/core/event_bus.py` | No subscribers registered | No (keep interface, use in Phase 3) |
| `app/core/di.py` | All active code uses direct imports | No (keep for Phase 1 adapter registration) |
| `app/core/conversation_engine.py` | `use_pipeline=False` by default | No (core of new architecture) |
| `app/pipeline/runner.py` | `use_pipeline=False` by default | No (core of new architecture) |
| `app/pipeline/stages/*.py` | `use_pipeline=False` by default | No (core of new architecture) |
| `app/channel/web_adapter.py` | `use_channel_adapters=False` by default | No (core of new architecture) |
| `app/services/backup.py` | Stub only | Yes (or implement properly) |
| `app/api/monitoring.py` | Stub only (7 lines) | No (expand in Phase 3) |
| `scripts/livekit_agent.py` | Incomplete | No (needed for telephony) |

---

## Legacy Code (Targeted for Deletion)

| Code | Lines | Status | Deletion Target |
|---|---|---|---|
| `groq_service.py` (monolithic) | ~5046 | ACTIVE — implements all functionality | Phase 3 (after all stages extracted) |
| `FEE_GROUP_MAP` in groq_service.py | ~200 | ACTIVE — legacy fee path | Phase 2 (after FeeEngineStage) |
| `conversation_logger.py` | ~710 | ACTIVE — current telemetry | Phase 3 (replaced by event bus) |
| `safe_point.py` post-processing in qa.py | ~5 | ACTIVE — demo_safepoint | Phase 1 (moved to GuardStage) |

---

## Dual-System Risk

The migration currently has **two active code paths**:
1. **Old:** `POST /qa/query` → `GroqService.generate_response()` (always active)
2. **New:** `ConversationEngine` → `PipelineRunner` → stages (behind `use_pipeline=False`)

Since the old path is always active and the new path is behind a disabled flag, there is zero risk of behavioral change. However, every day the migration remains incomplete, the old code accumulates more entropy.

**Deadline:** The `migration_deadline` field should be set to a concrete date (e.g., 2026-10-01) to force convergence.
