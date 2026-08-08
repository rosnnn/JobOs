"""Audit inbox classification."""
import asyncio
from collections import Counter
from sqlalchemy import select
from job_os.db.session import AsyncSessionLocal
from job_os.models.email_message import EmailMessage
from job_os.services.email_service import GmailService


async def main():
    g = GmailService()
    async with AsyncSessionLocal() as s:
        r = await s.execute(select(EmailMessage).order_by(EmailMessage.received_at.desc()))
        rows = list(r.scalars().all())
        c_old = Counter(row.classified_outcome for row in rows)
        c_new = Counter()
        mismatches = []
        for row in rows:
            cl = g.classify(row.subject, row.body_preview or "", row.from_address)
            c_new[cl["outcome"]] += 1
            if cl["outcome"] != row.classified_outcome:
                mismatches.append((row.classified_outcome, cl["outcome"], row.subject))
        print("DB stored:", dict(c_old))
        print("Re-classified:", dict(c_new))
        print("\nMismatches (stored -> new):")
        for old, new, subj in mismatches:
            print(f"  {old:22} -> {new:22} | {(subj or '')[:70]}")
        print("\nAll emails (new outcome):")
        for row in rows:
            cl = g.classify(row.subject, row.body_preview or "", row.from_address)
            subj = (row.subject or "")[:70]
            print(f"  {cl['outcome']:22} | {subj}")


if __name__ == "__main__":
    asyncio.run(main())
