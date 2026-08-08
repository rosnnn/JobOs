"""Workflow definitions — step sequences for the Coordinator."""

DAILY_DISCOVERY_STEPS: list[dict] = [
    {"step_id": "scout", "agent_name": "scout", "intent": "refresh_sources"},
    {"step_id": "discover", "agent_name": "job_discovery", "intent": "discover_jobs"},
    {"step_id": "eligibility", "agent_name": "eligibility", "intent": "filter_jobs"},
    {"step_id": "strategy", "agent_name": "strategy", "intent": "rank_jobs"},
    {"step_id": "resume_tailoring", "agent_name": "resume_tailoring", "intent": "tailor_resumes"},
    {"step_id": "cover_letter", "agent_name": "cover_letter", "intent": "generate_cover_letters"},
    {"step_id": "application_prep", "agent_name": "application_prep", "intent": "prepare_applications"},
    {"step_id": "tracking", "agent_name": "tracking", "intent": "record_metrics"},
    {"step_id": "reflection", "agent_name": "reflection", "intent": "analyze_session"},
]

# Legacy alias: discovery-only without tailoring (faster/cheaper runs)
DISCOVERY_ONLY_STEPS: list[dict] = [
    {"step_id": "scout", "agent_name": "scout", "intent": "refresh_sources"},
    {"step_id": "discover", "agent_name": "job_discovery", "intent": "discover_jobs"},
    {"step_id": "eligibility", "agent_name": "eligibility", "intent": "filter_jobs"},
    {"step_id": "strategy", "agent_name": "strategy", "intent": "rank_jobs"},
    {"step_id": "tracking", "agent_name": "tracking", "intent": "record_metrics"},
    {"step_id": "reflection", "agent_name": "reflection", "intent": "analyze_session"},
]

SUBMIT_APPLICATIONS_STEPS: list[dict] = [
    {"step_id": "browser_apply", "agent_name": "browser_apply", "intent": "submit_approved_applications"},
    {"step_id": "email_monitor", "agent_name": "email_monitor", "intent": "sync_company_replies"},
    {"step_id": "tracking", "agent_name": "tracking", "intent": "record_metrics"},
    {"step_id": "reflection", "agent_name": "reflection", "intent": "analyze_session"},
]

# Full pipeline including browser (dry-run by default until apps approved)
DAILY_PIPELINE_STEPS: list[dict] = [
    *DAILY_DISCOVERY_STEPS[:-2],  # through application_prep
    {"step_id": "browser_apply", "agent_name": "browser_apply", "intent": "submit_ready_applications"},
    {"step_id": "tracking", "agent_name": "tracking", "intent": "record_metrics"},
    {"step_id": "reflection", "agent_name": "reflection", "intent": "analyze_session"},
]

# Autonomous: discover → tailor → auto-approve → apply
AUTO_APPLY_STEPS: list[dict] = [
    {"step_id": "scout", "agent_name": "scout", "intent": "refresh_sources"},
    {"step_id": "discover", "agent_name": "job_discovery", "intent": "discover_jobs"},
    {"step_id": "eligibility", "agent_name": "eligibility", "intent": "filter_jobs"},
    {"step_id": "strategy", "agent_name": "strategy", "intent": "rank_jobs"},
    {"step_id": "resume_tailoring", "agent_name": "resume_tailoring", "intent": "tailor_resumes"},
    {"step_id": "cover_letter", "agent_name": "cover_letter", "intent": "generate_cover_letters"},
    {"step_id": "application_prep", "agent_name": "application_prep", "intent": "prepare_applications"},
    {"step_id": "auto_approve", "agent_name": "auto_approve", "intent": "approve_all_pending"},
    {"step_id": "browser_apply", "agent_name": "browser_apply", "intent": "submit_approved_applications"},
    {"step_id": "email_monitor", "agent_name": "email_monitor", "intent": "sync_inbox"},
    {"step_id": "rejection_analysis", "agent_name": "rejection_analysis", "intent": "analyze_rejections"},
    {"step_id": "tracking", "agent_name": "tracking", "intent": "record_metrics"},
    {"step_id": "reflection", "agent_name": "reflection", "intent": "analyze_session"},
]

EMAIL_SYNC_STEPS: list[dict] = [
    {"step_id": "email_monitor", "agent_name": "email_monitor", "intent": "sync_inbox"},
    {"step_id": "rejection_analysis", "agent_name": "rejection_analysis", "intent": "analyze_rejections"},
    {"step_id": "tracking", "agent_name": "tracking", "intent": "record_metrics"},
]

WORKFLOW_DEFINITIONS: dict[str, list[dict]] = {
    "daily_discovery": DAILY_DISCOVERY_STEPS,
    "discovery_only": DISCOVERY_ONLY_STEPS,
    "submit_applications": SUBMIT_APPLICATIONS_STEPS,
    "daily_pipeline": DAILY_PIPELINE_STEPS,
    "auto_apply_all": AUTO_APPLY_STEPS,
    "email_sync": EMAIL_SYNC_STEPS,
}
