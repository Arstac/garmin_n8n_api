from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = datetime.now()

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = {}
    timestamp: Optional[str] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime
    tokens_used: Optional[int] = None
    model_used: str