"""Initialize database schema and seed professional identities."""

import asyncio
import json
from pathlib import Path

from job_os.db.session import AsyncSessionLocal, engine
from job_os.models import Base, ProfessionalIdentity
from job_os.world_model.service import WorldModelService


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Auto-ingest resume PDF if present
    resume_dir = Path(__file__).parent.parent / "resume"
    pdfs = list(resume_dir.glob("*.pdf"))
    if pdfs:
        from job_os.services.resume_ingest import ingest

        print(f"Ingesting resume: {pdfs[0].name}")
        ingest(pdfs[0])

    async with AsyncSessionLocal() as session:
        world = WorldModelService(session)
        await world.get_current()

        seeds_path = Path(__file__).parent.parent / "data" / "identities.json"
        if seeds_path.exists():
            from sqlalchemy import select

            identities = json.loads(seeds_path.read_text())
            for item in identities:
                result = await session.execute(
                    select(ProfessionalIdentity).where(ProfessionalIdentity.slug == item["slug"])
                )
                if result.scalar_one_or_none():
                    continue
                resume_path = seeds_path.parent / "resumes" / f"{item['slug']}.md"
                session.add(
                    ProfessionalIdentity(
                        slug=item["slug"],
                        display_name=item["display_name"],
                        role_focus=item["role_focus"],
                        ats_keywords=item.get("ats_keywords", []),
                        project_emphasis=item.get("project_emphasis", []),
                        tone=item.get("tone", "professional"),
                        base_resume_path=str(resume_path) if resume_path.exists() else None,
                        performance_stats=item.get("performance_stats", {}),
                    )
                )
        await session.commit()
    print("Database initialized.")


if __name__ == "__main__":
    asyncio.run(main())
