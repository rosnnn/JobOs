from sqlalchemy.ext.asyncio import AsyncSession

from job_os.agents.application_prep import ApplicationPrepAgent
from job_os.agents.auto_approve import AutoApproveAgent
from job_os.agents.browser_apply import BrowserApplyAgent
from job_os.agents.base import BaseAgent
from job_os.agents.cover_letter_agent import CoverLetterAgent
from job_os.agents.eligibility import EligibilityAgent
from job_os.agents.email_monitor import EmailMonitorAgent
from job_os.agents.job_discovery import JobDiscoveryAgent
from job_os.agents.rejection_analysis import RejectionAnalysisAgent
from job_os.agents.reflection import ReflectionAgent
from job_os.agents.resume_tailoring import ResumeTailoringAgent
from job_os.agents.scout import ScoutAgent
from job_os.agents.strategy_agent import StrategyAgent
from job_os.agents.tracking import TrackingAgent
from job_os.core.events import EventService


class AgentRegistry:
    def __init__(self, session: AsyncSession, events: EventService):
        self._session = session
        self._events = events
        self._agents: dict[str, BaseAgent] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for agent_cls in (
            ScoutAgent,
            JobDiscoveryAgent,
            EligibilityAgent,
            StrategyAgent,
            ResumeTailoringAgent,
            CoverLetterAgent,
            ApplicationPrepAgent,
            AutoApproveAgent,
            BrowserApplyAgent,
            EmailMonitorAgent,
            RejectionAnalysisAgent,
            TrackingAgent,
            ReflectionAgent,
        ):
            agent = agent_cls(self._session, self._events)
            self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())
