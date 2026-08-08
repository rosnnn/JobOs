"""Re-fetch Gmail and reclassify all stored messages."""
import asyncio
from collections import Counter

from sqlalchemy import select

from job_os.db.session import AsyncSessionLocal
from job_os.models.email_message import EmailMessage
from job_os.services.email_service import GmailService


async def main():
    gmail = GmailService()
    emails = gmail.fetch_recent(limit=200)
    print(f"Fetched {len(emails)} messages from Gmail")

    async with AsyncSessionLocal() as session:
        synced = 0
        for parsed in emails:
            cl = gmail.classify(parsed.subject, parsed.body_preview, parsed.from_address)
            existing = await session.execute(
                select(EmailMessage).where(EmailMessage.message_id == parsed.message_id)
            )
            record = existing.scalar_one_or_none()
            if record:
                record.body_preview = parsed.body_preview
                record.classified_outcome = cl["outcome"]
                record.rejection_reason = cl.get("rejection_reason")
                record.is_walk_in = cl.get("is_walk_in", False)
                record.is_interview = cl.get("is_interview", False)
                if cl.get("company_name"):
                    record.company_name = cl["company_name"]
            else:
                record = EmailMessage(
                    message_id=parsed.message_id,
                    subject=parsed.subject,
                    from_address=parsed.from_address,
                    body_preview=parsed.body_preview,
                    received_at=parsed.received_at,
                    classified_outcome=cl["outcome"],
                    company_name=cl.get("company_name"),
                    rejection_reason=cl.get("rejection_reason"),
                    is_walk_in=cl.get("is_walk_in", False),
                    is_interview=cl.get("is_interview", False),
                    raw_headers=parsed.raw_headers,
                )
                session.add(record)
                synced += 1
        await session.commit()

        r = await session.execute(select(EmailMessage))
        rows = list(r.scalars().all())
        c = Counter(row.classified_outcome for row in rows)
        bad = [
            (row.subject, row.classified_outcome)
            for row in rows
            if row.classified_outcome == "application_received"
            and gmail.classify(row.subject, row.body_preview or "", row.from_address)["outcome"]
            == "rejected"
        ]
        print("Outcomes:", dict(c))
        print("Mislabeled rejections as app_received:", len(bad))
        for subj, out in bad:
            print(" ", out, "|", (subj or "")[:70])


if __name__ == "__main__":
    asyncio.run(main())
