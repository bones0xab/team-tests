import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, Optional

from openai import OpenAI

from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


class OllamaAIService(AIService):
    """
    OLLAMA-backed AI service using the OpenAI-compatible chat completions API.
    This provider is synchronous: analyze_job_fit returns completed data directly.
    """

    ALLOWED_ELEMENT_TYPES = {"video", "article", "exercise", "resource"}

    def __init__(self) -> None:
        self.base_url = os.environ.get(
            "OLLAMA_BASE_URL",
            "http://102.54.244.89:8088/ollama/api/v1",
        )
        self.api_key = os.environ.get("OLLAMA_API_KEY")
        self.model = os.environ.get("OLLAMA_MODEL", "mistral")
        self.timeout_seconds = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))

        if not self.api_key:
            logger.error("OLLAMA_API_KEY is not set.")
            self.client = None
            return

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )

    def analyze_job_fit(
        self,
        user_skills: Dict[str, int],
        job_title: str,
        job_description: str,
        custom_prompt: str,
        analysis_depth: str = "deep",
    ) -> Optional[dict]:
        if not self.client:
            return {
                "status": "failed",
                "message": "OLLAMA client is not initialized. Check OLLAMA_API_KEY.",
            }

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": custom_prompt}],
                temperature=0.1,
            )
            raw_content = (completion.choices[0].message.content or "").strip()
            parsed = self._extract_json_payload(raw_content)
            normalized = self._normalize_analysis_payload(parsed)

            return {
                "response_id": f"ollama_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                "status": "completed",
                "data": normalized,
                "debug_prompt": custom_prompt,
            }
        except Exception as exc:
            logger.exception("OLLAMA analyze_job_fit failed")
            return {
                "status": "failed",
                "message": str(exc),
            }

    def check_response_status(self, response_id: str) -> Optional[dict]:
        return {
            "status": "pending",
            "message": "OLLAMA responses are synchronous; remote polling is not supported.",
        }

    def fetch_final_response(self, response_id: str) -> Optional[dict]:
        return None

    def cancel_analysis(self, response_id: str) -> bool:
        return False

    def _extract_json_payload(self, content: str) -> Any:
        if not content:
            raise ValueError("Empty response content from OLLAMA")

        # Remove markdown fences if present.
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])

        raise ValueError("No valid JSON object found in OLLAMA response")

    def _normalize_analysis_payload(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            raw_score = payload.get("match_score", 0)
            raw_path = payload.get("learning_path", [])
        elif isinstance(payload, list):
            raw_score = 0
            raw_path = payload
        else:
            raw_score = 0
            raw_path = []

        try:
            match_score = int(raw_score)
        except (TypeError, ValueError):
            match_score = 0
        match_score = max(0, min(100, match_score))

        if not isinstance(raw_path, list):
            raw_path = []

        learning_path = []
        for course in raw_path:
            if not isinstance(course, dict):
                continue
            course_title = str(course.get("course", "Untitled Course"))
            chapters_raw = course.get("chapters", [])
            if not isinstance(chapters_raw, list):
                chapters_raw = []

            chapters = []
            for chapter in chapters_raw:
                if not isinstance(chapter, dict):
                    continue
                chapter_title = str(chapter.get("title", "Untitled Chapter"))
                elements_raw = chapter.get("elements", [])
                if not isinstance(elements_raw, list):
                    elements_raw = []

                elements = []
                for element in elements_raw:
                    if not isinstance(element, dict):
                        continue
                    element_title = str(element.get("title", "Untitled Element"))
                    element_type = str(element.get("type", "resource")).lower()
                    if element_type not in self.ALLOWED_ELEMENT_TYPES:
                        element_type = "resource"
                    element_url = element.get("url")
                    if element_url is not None and not isinstance(element_url, str):
                        element_url = None
                    elements.append(
                        {
                            "title": element_title,
                            "type": element_type,
                            "url": element_url,
                        }
                    )

                chapters.append({"title": chapter_title, "elements": elements})

            learning_path.append({"course": course_title, "chapters": chapters})

        return {"match_score": match_score, "learning_path": learning_path}
 