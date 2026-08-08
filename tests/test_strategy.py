from uuid import uuid4

from job_os.models.identity import ProfessionalIdentity
from job_os.models.job import Job
from job_os.strategy.engine import StrategyEngine
from job_os.world_model.defaults import DEFAULT_WORLD_STATE


def test_strategy_ranks_remote_sponsorship_higher():
    identity = ProfessionalIdentity(
        id=uuid4(),
        slug="backend_engineer",
        display_name="Backend",
        role_focus="backend python",
        ats_keywords=["python", "backend"],
        performance_stats={"response_rate": 0.05},
    )
    engine = StrategyEngine(world_state=DEFAULT_WORLD_STATE, identities=[identity])

    base_job = Job(
        id=uuid4(),
        external_id="a",
        source="test",
        title="Junior Python Developer",
        url="https://example.com/a",
        eligibility_score=0.6,
        is_remote=False,
        offers_sponsorship=False,
        fresher_friendly=True,
    )
    strong_job = Job(
        id=uuid4(),
        external_id="b",
        source="test",
        title="Junior Python Developer Remote",
        url="https://example.com/b",
        eligibility_score=0.7,
        is_remote=True,
        offers_sponsorship=True,
        fresher_friendly=True,
    )

    ev_base, _, _ = engine.score_job(base_job)
    ev_strong, _, _ = engine.score_job(strong_job)
    assert ev_strong > ev_base
