from uuid import UUID

from pydantic import BaseModel
from pydantic import model_validator
from sqlalchemy.orm import Session

from sambaai.chat.prompt_builder.answer_prompt_builder import AnswerPromptBuilder
from sambaai.context.search.models import RerankingDetails
from sambaai.db.models import Persona
from sambaai.file_store.utils import InMemoryChatFile
from sambaai.llm.interfaces import LLM
from sambaai.tools.force import ForceUseTool
from sambaai.tools.tool import Tool
from sambaai.tools.tool_implementations.search.search_tool import SearchTool


class GraphInputs(BaseModel):
    """Input data required for the graph execution"""

    persona: Persona | None = None
    rerank_settings: RerankingDetails | None = None
    prompt_builder: AnswerPromptBuilder
    files: list[InMemoryChatFile] | None = None
    structured_response_format: dict | None = None

    class Config:
        arbitrary_types_allowed = True


class GraphTooling(BaseModel):
    """Tools and LLMs available to the graph"""

    primary_llm: LLM
    fast_llm: LLM
    search_tool: SearchTool | None = None
    tools: list[Tool]
    # Whether to force use of a tool, or to
    # force tool args IF the tool is used
    force_use_tool: ForceUseTool
    using_tool_calling_llm: bool = False

    class Config:
        arbitrary_types_allowed = True


class GraphPersistence(BaseModel):
    """Configuration for data persistence"""

    chat_session_id: UUID
    # The message ID of the to-be-created first agent message
    # in response to the user message that triggered the Pro Search
    message_id: int

    # The database session the user and initial agent
    # message were flushed to; only needed for agentic search
    db_session: Session

    class Config:
        arbitrary_types_allowed = True


class GraphSearchConfig(BaseModel):
    """Configuration controlling search behavior"""

    use_agentic_search: bool = False
    # Whether to perform initial search to inform decomposition
    perform_initial_search_decomposition: bool = True

    # Whether to allow creation of refinement questions (and entity extraction, etc.)
    allow_refinement: bool = True
    skip_gen_ai_answer_generation: bool = False
    allow_agent_reranking: bool = False


class GraphConfig(BaseModel):
    """
    Main container for data needed for Langgraph execution
    """

    inputs: GraphInputs
    tooling: GraphTooling
    behavior: GraphSearchConfig
    # Only needed for agentic search
    persistence: GraphPersistence

    @model_validator(mode="after")
    def validate_search_tool(self) -> "GraphConfig":
        if self.behavior.use_agentic_search and self.tooling.search_tool is None:
            raise ValueError("search_tool must be provided for agentic search")
        return self

    class Config:
        arbitrary_types_allowed = True
