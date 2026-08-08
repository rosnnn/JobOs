"""Expected-value scoring for job prioritization."""

from job_os.models.identity import ProfessionalIdentity
from job_os.models.job import Job

DEFAULT_WEIGHTS = {
    "base": 0.3,
    "remote": 0.15,
    "sponsorship": 0.2,
    "fresher": 0.15,
    "eligibility": 0.2,
}


class StrategyEngine:
    def __init__(
        self,
        *,
        world_state: dict,
        identities: list[ProfessionalIdentity],
        weights: dict[str, float] | None = None,
    ):
        self._world = world_state
        self._identities = {i.slug: i for i in identities}
        self._weights = weights or self._load_weights_from_world()

    def _load_weights_from_world(self) -> dict[str, float]:
        stored = self._world.get("strategy_weights", {})
        return {**DEFAULT_WEIGHTS, **stored}

    def score_job(self, job: Job) -> tuple[float, str | None, str]:
        w = self._weights
        score = w["base"]

        if job.is_remote:
            score += w["remote"]
        if job.offers_sponsorship:
            score += w["sponsorship"]
        if job.fresher_friendly:
            score += w["fresher"]
        if job.eligibility_score:
            score += w["eligibility"] * job.eligibility_score

        # Country / visa friendliness from world model
        location = (job.location or "").upper()
        visa_map = self._world.get("visa_friendliness", {})
        for country, bonus in visa_map.items():
            if country.upper() in location:
                score += float(bonus) * 0.1

        identity_slug, rationale = self._pick_identity(job)
        perf = self._world.get("resume_performance", {}).get(identity_slug or "", {})
        response_rate = float(perf.get("response_rate", 0.05))
        score += response_rate * 0.5

        ev = round(min(1.0, max(0.0, score)), 4)
        return ev, identity_slug, rationale

    def _pick_identity(self, job: Job) -> tuple[str | None, str]:
        if not self._identities:
            return None, "no_identities_configured"

        title = job.title.lower()
        best_slug: str | None = None
        best_score = -1.0

        for slug, identity in self._identities.items():
            fit = 0.0
            focus = identity.role_focus.lower()
            for kw in identity.ats_keywords:
                if kw.lower() in title:
                    fit += 0.2
            if focus.split()[0] in title:
                fit += 0.3
            perf = (identity.performance_stats or {}).get("response_rate", 0.05)
            fit += float(perf)
            if fit > best_score:
                best_score = fit
                best_slug = slug

        return best_slug, f"identity_fit_score={best_score:.2f}"
