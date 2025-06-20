import json
from pathlib import Path

from langgraph.types import StreamWriter

from sambaai.agents.agent_search.basic.utils import process_llm_stream
from sambaai.chat.models import PromptConfig
from sambaai.chat.prompt_builder.answer_prompt_builder import AnswerPromptBuilder
from sambaai.chat.prompt_builder.answer_prompt_builder import default_build_system_message
from sambaai.chat.prompt_builder.answer_prompt_builder import default_build_user_message
from sambaai.configs.app_configs import POSTGRES_API_SERVER_POOL_OVERFLOW
from sambaai.configs.app_configs import POSTGRES_API_SERVER_POOL_SIZE
from sambaai.configs.constants import DEFAULT_PERSONA_ID
from sambaai.db.engine import get_session_with_current_tenant
from sambaai.db.engine import SqlEngine
from sambaai.db.persona import get_persona_by_id
from sambaai.llm.factory import get_llms_for_persona
from sambaai.llm.interfaces import LLM
from sambaai.tools.tool_implementations.search.search_tool import SearchTool
from sambaai.tools.utils import explicit_tool_calling_supported
from sambaai.utils.logger import setup_logger
from shared_configs.configs import MULTI_TENANT

logger = setup_logger()


def _load_queries() -> list[str]:
    current_dir = Path(__file__).parent
    search_queries_path = current_dir / "search_queries.json"
    if not search_queries_path.exists():
        raise FileNotFoundError(
            f"Search queries file not found at {search_queries_path}"
        )
    with search_queries_path.open("r") as file:
        return json.load(file)


def _modify_one_query(
    query: str,
    llm: LLM,
    prompt_config: PromptConfig,
    tool_definition: dict,
    writer: StreamWriter = lambda _: None,
) -> str:
    prompt_builder = AnswerPromptBuilder(
        user_message=default_build_user_message(
            user_query=query,
            prompt_config=prompt_config,
            files=[],
            single_message_history=None,
        ),
        system_message=default_build_system_message(prompt_config, llm.config),
        message_history=[],
        llm_config=llm.config,
        raw_user_query=query,
        raw_user_uploaded_files=[],
        single_message_history=None,
    )
    prompt = prompt_builder.build()

    stream = llm.stream(
        prompt=prompt,
        tools=[tool_definition],
        tool_choice="required",
        structured_response_format=None,
    )
    tool_message = process_llm_stream(
        messages=stream,
        should_stream_answer=False,
        writer=writer,
    )
    return (
        tool_message.tool_calls[0]["args"]["query"]
        if tool_message.tool_calls
        else query
    )


class SearchToolOverride(SearchTool):
    def __init__(self) -> None:
        # do nothing, the tool_definition function doesn't require variables to be initialized
        pass


def generate_search_queries() -> None:
    if MULTI_TENANT:
        raise ValueError("Multi-tenant is not supported currently")

    SqlEngine.init_engine(
        pool_size=POSTGRES_API_SERVER_POOL_SIZE,
        max_overflow=POSTGRES_API_SERVER_POOL_OVERFLOW,
    )

    queries = _load_queries()

    with get_session_with_current_tenant() as db_session:
        persona = get_persona_by_id(DEFAULT_PERSONA_ID, None, db_session)
        llm, _ = get_llms_for_persona(persona)
        prompt_config = PromptConfig.from_model(persona.prompts[0])
        tool_definition = SearchToolOverride().tool_definition()

        tool_call_supported = explicit_tool_calling_supported(
            llm.config.model_provider, llm.config.model_name
        )

        if tool_call_supported:
            logger.info(
                "Tool calling is supported for the current model. Modifying queries."
            )
            modified_queries = [
                _modify_one_query(
                    query=query,
                    llm=llm,
                    prompt_config=prompt_config,
                    tool_definition=tool_definition,
                )
                for query in queries
            ]
        else:
            logger.warning(
                "Tool calling is not supported for the current model. "
                "Using the original queries."
            )
            modified_queries = queries

        with open("search_queries_modified.json", "w") as file:
            json.dump(modified_queries, file, indent=4)

    logger.info("Exported modified queries to search_queries_modified.json")


if __name__ == "__main__":
    generate_search_queries()
