from pydantic import BaseModel, Field
from typing import Literal


class TriageResult(BaseModel):
    urgency: Literal["Critical","High","Medium","Low"]= Field(
        description="Urgency level of the support request."
    )
    category: Literal["Billing","Technical","Account","Feedback","Other"] = Field(
        description="Primary category of the support request."
    )
    sentiment: Literal["Angry","Frustrated","Neutral","Happy"] = Field(
        description="Emotional tone expressed by the user."
    )
    suggested_reply: str = Field(
        description="Concise, professional reply addressing the user's issue."
    )