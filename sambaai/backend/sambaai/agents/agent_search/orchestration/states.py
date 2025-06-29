from pydantic import BaseModel

from sambaai.chat.prompt_builder.answer_prompt_builder import PromptSnapshot
from sambaai.tools.message import ToolCallSummary
from sambaai.tools.models import SearchToolOverrideKwargs
from sambaai.tools.models import ToolCallFinalResult
from sambaai.tools.models import ToolCallKickoff
from sambaai.tools.models import ToolResponse
from sambaai.tools.tool import Tool


# TODO: adapt the tool choice/tool call to allow for parallel tool calls by
# creating a subgraph that can be invoked in parallel via Send/Command APIs
class ToolChoiceInput(BaseModel):
    should_stream_answer: bool = True
    # default to the prompt builder from the config, but
    # allow overrides for arbitrary tool calls
    prompt_snapshot: PromptSnapshot | None = None

    # names of tools to use for tool calling. Filters the tools available in the config
    tools: list[str] = []


class ToolCallOutput(BaseModel):
    tool_call_summary: ToolCallSummary
    tool_call_kickoff: ToolCallKickoff
    tool_call_responses: list[ToolResponse]
    tool_call_final_result: ToolCallFinalResult


class ToolCallUpdate(BaseModel):
    tool_call_output: ToolCallOutput | None = None


class ToolChoice(BaseModel):
    tool: Tool
    tool_args: dict
    id: str | None
    search_tool_override_kwargs: SearchToolOverrideKwargs = SearchToolOverrideKwargs()

    class Config:
        arbitrary_types_allowed = True


class ToolChoiceUpdate(BaseModel):
    tool_choice: ToolChoice | None = None


class ToolChoiceState(ToolChoiceUpdate, ToolChoiceInput):
    pass
