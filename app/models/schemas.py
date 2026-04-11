from pydantic import BaseModel, Field
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


# ── Enums ──

class AgentName(str, Enum):
    orchestrator     = "orchestrator"
    document_analyst = "document_analyst"
    requirements     = "requirements_agent"
    competitor       = "competitor_analyst"
    bpmn             = "bpmn_agent"
    entity           = "entity_agent"
    export           = "export_agent"
    image_analyst    = "image_analyst"
    clarification    = "clarification"


class ExportFormat(str, Enum):
    word = "word"
    pdf  = "pdf"
    bpmn = "bpmn"


class RequirementType(str, Enum):
    fr  = "fr"   # Functional Requirement
    nfr = "nfr"  # Non-Functional Requirement
    br  = "br"   # Business Rule
    oq  = "oq"   # Open Question


class ProjectStatus(str, Enum):
    draft    = "draft"
    active   = "active"
    archived = "archived"


# ── Chat ──

class ChatMessage(BaseModel):
    role: str                          # "user" | "assistant"
    content: str
    agent: Optional[AgentName] = None
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    session_id: UUID
    project_id: UUID
    message: str
    file_ids: List[UUID] = Field(default_factory=list)
    image_ids: List[UUID] = Field(default_factory=list)


class OrchestratorResult(BaseModel):
    agents: List[AgentName]
    intent: str
    priority_agent: AgentName
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: UUID
    message_id: UUID
    agent: AgentName
    content: str
    artifacts: List[dict] = Field(default_factory=list)
    requirements: List[dict] = Field(default_factory=list)
    bpmn_xml: Optional[str] = None


# ── Projects ──

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    color: str = "#005BFF"
    team_id: Optional[UUID] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    status: Optional[ProjectStatus] = None


class Project(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    color: str
    status: ProjectStatus
    team_id: Optional[UUID]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


# ── Sessions ──

class SessionCreate(BaseModel):
    project_id: UUID
    title: Optional[str] = "Новая сессия"


class Session(BaseModel):
    id: UUID
    project_id: UUID
    user_id: UUID
    title: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ── Files ──

class FileRecord(BaseModel):
    id: UUID
    project_id: UUID
    session_id: Optional[UUID]
    filename: str
    file_type: str           # pdf | docx | bpmn | xml | image
    storage_path: str
    extracted_text: Optional[str] = None
    file_size: int
    created_at: datetime


# ── Requirements ──

class Requirement(BaseModel):
    id: UUID
    project_id: UUID
    session_id: Optional[UUID]
    code: str                # FR-001, NFR-001 и т.д.
    type: RequirementType
    content: str
    version: int = 1
    source_message: Optional[str] = None
    created_by: UUID
    created_at: datetime


class RequirementCreate(BaseModel):
    project_id: UUID
    session_id: Optional[UUID] = None
    type: RequirementType
    content: str


# ── BPMN ──

class BpmnDiagram(BaseModel):
    id: UUID
    project_id: UUID
    requirement_ids: List[UUID] = Field(default_factory=list)
    version: int
    xml_content: str
    edited_by: Optional[UUID]
    updated_at: datetime


# ── Export ──

class ExportRequest(BaseModel):
    project_id: UUID
    formats: List[ExportFormat]
    include_requirements: bool = True
    include_bpmn: bool = True
    include_entities: bool = False
    include_rtm: bool = False


class ExportResult(BaseModel):
    files: List[dict]        # [{"format": "word", "url": "...", "filename": "..."}]
    expires_at: datetime
