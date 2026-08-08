"""Parse and resolve when a job was posted (for newest-first ordering)."""

from __future__ import annotations

from datetime import datetime, timezone

from job_os.models.job import Job


def parse_posted_at(metadata: dict | None) -> datetime | None:
    if not metadata:
        return None
    for key in ("posted_at", "pub_date", "publication_date", "created", "date"):
        raw = metadata.get(key)
        if not raw:
            continue
        if isinstance(raw, datetime):
            return _aware(raw)
        if isinstance(raw, (int, float)):
            try:
                return datetime.fromtimestamp(raw, tz=timezone.utc)
            except (OSError, ValueError):
                continue
        text = str(raw).strip()
        if not text:
            continue
        iso = text.replace("Z", "+00:00")
        try:
            return _aware(datetime.fromisoformat(iso))
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            from email.utils import parsedate_to_datetime

            return _aware(parsedate_to_datetime(text))
        except Exception:
            continue
    return None


def effective_posted_at(job: Job) -> datetime:
    if job.posted_at:
        return _aware(job.posted_at)
    parsed = parse_posted_at(job.parsed_metadata)
    if parsed:
        return parsed
    if job.discovered_at:
        return _aware(job.discovered_at)
    return _aware(job.created_at)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
