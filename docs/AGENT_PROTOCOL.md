# Agent Protocol Specification

## Execution Lifecycle

Every agent action follows:

```
INTENT → VALIDATE → EXECUTE → LOG → (optional) REFLECT_HOOK
```

1. **INTENT** — `AgentMessage.intent` declares what will happen
2. **VALIDATE** — Pydantic input schema + `SafetyValidator` rules
3. **EXECUTE** — Side effects (DB, HTTP, browser)
4. **LOG** — `EventService.emit()` with full payload hash
5. **REFLECT_HOOK** — Coordinator may queue reflection on failure clusters

## AgentResult Schema

```python
{
  "success": bool,
  "output": dict,              # downstream-consumable structured data
  "artifacts": list[str],      # S3 paths or artifact IDs
  "memory_writes": list[dict], # {key, type, content, metadata}
  "next_step_hint": str | null,
  "requires_approval": bool,
  "error_code": str | null,
  "error_detail": str | null,
}
```

## Coordinator Dispatch Rules

| Condition | Action |
|-----------|--------|
| `requires_approval=True` | Transition workflow → `awaiting_approval` |
| `success=False` and retriable | Retry step up to `max_retries` |
| `success=False` and fatal | Mark step failed; continue or abort per workflow config |
| All steps done | Queue `ReflectionAgent` if configured |

## Inter-Agent Data Contracts

### JobDiscovery → Eligibility

```json
{ "jobs": [{ "external_id", "title", "company_name", "source", "url", "raw_description", "metadata" }] }
```

### Eligibility → Strategy

```json
{ "qualified_jobs": [{ "job_id", "eligibility_score", "flags": { "remote", "sponsorship", "fresher_ok" }, "reject_reasons": [] }] }
```

### Strategy → ResumeTailoring

```json
{ "ranked_jobs": [{ "job_id", "ev_score", "recommended_identity_id" }] }
```

## Versioning

Agents expose `version: str` in registry. Workflow definitions pin compatible agent versions for reproducibility.

## Testing Agents

Each agent module includes `tests/agents/test_<name>.py` with:

- Schema validation fixtures
- Mocked LLM responses
- Golden-file structured outputs

No live LLM calls in unit tests.
