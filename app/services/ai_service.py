from abc import ABC, abstractmethod
from typing import Dict, Optional

from orchestration.agentV2 import run_ai_analysis


def execute_ai():
    return run_ai_analysis()


class AIService(ABC):

    @abstractmethod
    def analyze_job_fit(
        self,
        user_skills: Dict[str, int],
        job_title: str,
        job_description: str,
        custom_prompt: str,
        analysis_depth: str = "deep",
    ) -> Optional[dict]: ...

    @abstractmethod
    def check_response_status(self, response_id: str) -> Optional[dict]: ...

    @abstractmethod
    def fetch_final_response(self, response_id: str) -> Optional[dict]: ...

    @abstractmethod
    def cancel_analysis(self, response_id: str) -> bool: ...