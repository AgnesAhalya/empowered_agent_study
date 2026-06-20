from typing import Dict, Optional

from pydantic import BaseModel


class CompletionRequest(BaseModel):
    prefix: str
    method: str = "normal_selector"
    problem_id: Optional[str] = "palindrome"
    participant_id: Optional[str] = "pilot"


class CompletionResponse(BaseModel):
    suggestion: str
    selected_option: str
    method: str
    problem_id: Optional[str]
    model: str
    suggestion_length: int
    option_counts: Dict[str, int]
    option_percentages: Dict[str, float]
    option_total: int


class SubmissionRequest(BaseModel):
    problem_id: str
    participant_id: str = "pilot"
    method: str = "normal_selector"
    selected_option: Optional[str] = None
    code: str
