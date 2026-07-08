from pydantic import BaseModel, Field
from typing import List

class ExtractedEmployee(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(..., description="Full legal name, capitalized.")
    email: str = Field(..., description="Email, lowercase.")
    role: str
    department: str
    manager: str
    start_date: str = Field(..., description="ISO 8601 YYYY-MM-DD.")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)

class RoadmapSection(BaseModel):
    title: str
    details: str

class OnboardingPlan(BaseModel):
    model_config = {"extra": "forbid"}
    welcome_message: str
    day_30: RoadmapSection
    day_60: RoadmapSection
    day_90: RoadmapSection
    key_contacts: List[str]
