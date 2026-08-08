from job_os.agents.base import BaseAgent

from job_os.config import get_settings

from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext

from job_os.services.job_source_registry import GREENHOUSE_BOARDS, LEVER_COMPANIES

from job_os.services.profile_job_search import build_job_search_block

from job_os.services.profile_service import ProfileService



SOURCE_SEEDS: dict[str, list[dict]] = {

    "greenhouse": [{"board": b} for b in GREENHOUSE_BOARDS[:40]],

    "lever": [{"board": c} for c in LEVER_COMPANIES],

    "weworkremotely": [

        {"url": "https://weworkremotely.com/categories/remote-programming-jobs.rss"},

    ],

    "jobspresso": [{"url": "https://jobspresso.co/feed/"}],

    "startup_jobs": [{"url": "https://startup.jobs/software-engineer"}],

    "yc_jobs": [{"url": "https://www.ycombinator.com/jobs"}],

    "wellfound": [{"url": "https://wellfound.com/jobs"}],

}





def _profile_seeds(source: str, profile: dict) -> list[dict]:

    js = profile.get("job_search") or build_job_search_block(profile)

    dq = js.get("discovery_queries") or {}



    if source == "jsearch":

        return [{"q": q} for q in dq.get("jsearch", [])]

    if source == "himalayas":

        return [{"q": q} for q in dq.get("himalayas", [])]

    if source == "linkedin":

        return [{"q": q} for q in dq.get("linkedin", [])]

    if source == "wellfound":

        return [{"q": q} for q in dq.get("wellfound", [])]

    if source == "findwork":

        return [{"q": q} for q in dq.get("findwork", [])]

    if source.startswith("adzuna_"):

        country = source.replace("adzuna_", "")

        queries = dq.get(source) or dq.get(f"adzuna_{js.get('adzuna_home', 'in')}") or []

        if not queries:

            city = js.get("primary_city") or js.get("home_country") or ""

            role = (js.get("target_roles") or ["developer"])[0]

            queries = [f"{role} {city}".strip()]

        return [{"country": country, "what": q} for q in queries if q.strip()]

    return SOURCE_SEEDS.get(source, [])





class ScoutAgent(BaseAgent):

    name = "scout"

    version = "0.2.0"



    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:

        settings = get_settings()

        profile = ProfileService().load()

        sources: list[dict] = []



        for source in settings.sources_list:

            seeds = _profile_seeds(source, profile)

            sources.append(

                {

                    "source": source,

                    "seeds": seeds,

                    "enabled": True,

                    "health": "unknown",

                }

            )



        ctx.scratchpad["discovery_sources"] = sources



        await self._emit(

            ctx,

            msg,

            "scout.sources_resolved",

            {"source_count": len(sources), "sources": [s["source"] for s in sources]},

        )



        return AgentResult(

            success=True,

            output={"sources": sources},

            next_step_hint="job_discovery",

        )

