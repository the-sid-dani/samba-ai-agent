import time
import traceback
from collections import defaultdict
from collections.abc import Callable
from collections.abc import Generator
from collections.abc import Iterator
from typing import cast
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from sambaai.agents.agent_search.orchestration.nodes.call_tool import ToolCallException
from sambaai.chat.answer import Answer
from sambaai.chat.chat_utils import create_chat_chain
from sambaai.chat.chat_utils import create_temporary_persona
from sambaai.chat.models import AgenticMessageResponseIDInfo
from sambaai.chat.models import AgentMessageIDInfo
from sambaai.chat.models import AgentSearchPacket
from sambaai.chat.models import AllCitations
from sambaai.chat.models import AnswerPostInfo
from sambaai.chat.models import AnswerStyleConfig
from sambaai.chat.models import ChatSambaAIBotResponse
from sambaai.chat.models import CitationConfig
from sambaai.chat.models import CitationInfo
from sambaai.chat.models import CustomToolResponse
from sambaai.chat.models import DocumentPruningConfig
from sambaai.chat.models import ExtendedToolResponse
from sambaai.chat.models import FileChatDisplay
from sambaai.chat.models import FinalUsedContextDocsResponse
from sambaai.chat.models import LLMRelevanceFilterResponse
from sambaai.chat.models import MessageResponseIDInfo
from sambaai.chat.models import MessageSpecificCitations
from sambaai.chat.models import SambaAIAnswerPiece
from sambaai.chat.models import PromptConfig
from sambaai.chat.models import QADocsResponse
from sambaai.chat.models import RefinedAnswerImprovement
from sambaai.chat.models import StreamingError
from sambaai.chat.models import StreamStopInfo
from sambaai.chat.models import StreamStopReason
from sambaai.chat.models import SubQuestionKey
from sambaai.chat.models import UserKnowledgeFilePacket
from sambaai.chat.prompt_builder.answer_prompt_builder import AnswerPromptBuilder
from sambaai.chat.prompt_builder.answer_prompt_builder import default_build_system_message
from sambaai.chat.prompt_builder.answer_prompt_builder import default_build_user_message
from sambaai.configs.chat_configs import CHAT_TARGET_CHUNK_PERCENTAGE
from sambaai.configs.chat_configs import DISABLE_LLM_CHOOSE_SEARCH
from sambaai.configs.chat_configs import MAX_CHUNKS_FED_TO_CHAT
from sambaai.configs.chat_configs import SELECTED_SECTIONS_MAX_WINDOW_PERCENTAGE
from sambaai.configs.constants import AGENT_SEARCH_INITIAL_KEY
from sambaai.configs.constants import BASIC_KEY
from sambaai.configs.constants import MessageType
from sambaai.configs.constants import MilestoneRecordType
from sambaai.configs.constants import NO_AUTH_USER_ID
from sambaai.context.search.enums import LLMEvaluationType
from sambaai.context.search.enums import OptionalSearchSetting
from sambaai.context.search.enums import QueryFlow
from sambaai.context.search.enums import SearchType
from sambaai.context.search.models import BaseFilters
from sambaai.context.search.models import InferenceSection
from sambaai.context.search.models import RetrievalDetails
from sambaai.context.search.retrieval.search_runner import (
    inference_sections_from_ids,
)
from sambaai.context.search.utils import chunks_or_sections_to_search_docs
from sambaai.context.search.utils import dedupe_documents
from sambaai.context.search.utils import drop_llm_indices
from sambaai.context.search.utils import relevant_sections_to_indices
from sambaai.db.chat import attach_files_to_chat_message
from sambaai.db.chat import create_db_search_doc
from sambaai.db.chat import create_new_chat_message
from sambaai.db.chat import create_search_doc_from_user_file
from sambaai.db.chat import get_chat_message
from sambaai.db.chat import get_chat_session_by_id
from sambaai.db.chat import get_db_search_doc_by_id
from sambaai.db.chat import get_doc_query_identifiers_from_model
from sambaai.db.chat import get_or_create_root_message
from sambaai.db.chat import reserve_message_id
from sambaai.db.chat import translate_db_message_to_chat_message_detail
from sambaai.db.chat import translate_db_search_doc_to_server_search_doc
from sambaai.db.chat import update_chat_session_updated_at_timestamp
from sambaai.db.engine import get_session_context_manager
from sambaai.db.milestone import check_multi_assistant_milestone
from sambaai.db.milestone import create_milestone_if_not_exists
from sambaai.db.milestone import update_user_assistant_milestone
from sambaai.db.models import ChatMessage
from sambaai.db.models import Persona
from sambaai.db.models import SearchDoc as DbSearchDoc
from sambaai.db.models import ToolCall
from sambaai.db.models import User
from sambaai.db.models import UserFile
from sambaai.db.persona import get_persona_by_id
from sambaai.db.search_settings import get_current_search_settings
from sambaai.document_index.factory import get_default_document_index
from sambaai.file_store.models import ChatFileType
from sambaai.file_store.models import FileDescriptor
from sambaai.file_store.models import InMemoryChatFile
from sambaai.file_store.utils import get_user_files
from sambaai.file_store.utils import load_all_chat_files
from sambaai.file_store.utils import load_in_memory_chat_files
from sambaai.file_store.utils import save_files
from sambaai.llm.exceptions import GenAIDisabledException
from sambaai.llm.factory import get_llms_for_persona
from sambaai.llm.factory import get_main_llm_from_tuple
from sambaai.llm.interfaces import LLM
from sambaai.llm.models import PreviousMessage
from sambaai.llm.utils import litellm_exception_to_error_msg
from sambaai.natural_language_processing.utils import get_tokenizer
from sambaai.server.query_and_chat.models import ChatMessageDetail
from sambaai.server.query_and_chat.models import CreateChatMessageRequest
from sambaai.server.utils import get_json_line
from sambaai.tools.force import ForceUseTool
from sambaai.tools.models import SearchToolOverrideKwargs
from sambaai.tools.models import ToolResponse
from sambaai.tools.tool import Tool
from sambaai.tools.tool_constructor import construct_tools
from sambaai.tools.tool_constructor import CustomToolConfig
from sambaai.tools.tool_constructor import ImageGenerationToolConfig
from sambaai.tools.tool_constructor import InternetSearchToolConfig
from sambaai.tools.tool_constructor import SearchToolConfig
from sambaai.tools.tool_implementations.custom.custom_tool import (
    CUSTOM_TOOL_RESPONSE_ID,
)
from sambaai.tools.tool_implementations.custom.custom_tool import CustomToolCallSummary
from sambaai.tools.tool_implementations.images.image_generation_tool import (
    IMAGE_GENERATION_RESPONSE_ID,
)
from sambaai.tools.tool_implementations.images.image_generation_tool import (
    ImageGenerationResponse,
)
from sambaai.tools.tool_implementations.internet_search.internet_search_tool import (
    INTERNET_SEARCH_RESPONSE_ID,
)
from sambaai.tools.tool_implementations.internet_search.internet_search_tool import (
    internet_search_response_to_search_docs,
)
from sambaai.tools.tool_implementations.internet_search.internet_search_tool import (
    InternetSearchResponse,
)
from sambaai.tools.tool_implementations.internet_search.internet_search_tool import (
    InternetSearchTool,
)
from sambaai.tools.tool_implementations.search.search_tool import (
    FINAL_CONTEXT_DOCUMENTS_ID,
)
from sambaai.tools.tool_implementations.search.search_tool import (
    SEARCH_RESPONSE_SUMMARY_ID,
)
from sambaai.tools.tool_implementations.search.search_tool import SearchResponseSummary
from sambaai.tools.tool_implementations.search.search_tool import SearchTool
from sambaai.tools.tool_implementations.search.search_tool import (
    SECTION_RELEVANCE_LIST_ID,
)
from sambaai.tools.tool_runner import ToolCallFinalResult
from sambaai.utils.logger import setup_logger
from sambaai.utils.long_term_log import LongTermLogger
from sambaai.utils.telemetry import mt_cloud_telemetry
from sambaai.utils.timing import log_function_time
from sambaai.utils.timing import log_generator_function_time
from shared_configs.contextvars import get_current_tenant_id

logger = setup_logger()
ERROR_TYPE_CANCELLED = "cancelled"

COMMON_TOOL_RESPONSE_TYPES = {
    "image": ChatFileType.IMAGE,
    "csv": ChatFileType.CSV,
}


class PartialResponse(Protocol):
    def __call__(
        self,
        message: str,
        rephrased_query: str | None,
        reference_docs: list[DbSearchDoc] | None,
        files: list[FileDescriptor],
        token_count: int,
        citations: dict[int, int] | None,
        error: str | None,
        tool_call: ToolCall | None,
    ) -> ChatMessage: ...


def _translate_citations(
    citations_list: list[CitationInfo], db_docs: list[DbSearchDoc]
) -> MessageSpecificCitations:
    """Always cites the first instance of the document_id, assumes the db_docs
    are sorted in the order displayed in the UI"""
    doc_id_to_saved_doc_id_map: dict[str, int] = {}
    for db_doc in db_docs:
        if db_doc.document_id not in doc_id_to_saved_doc_id_map:
            doc_id_to_saved_doc_id_map[db_doc.document_id] = db_doc.id

    citation_to_saved_doc_id_map: dict[int, int] = {}
    for citation in citations_list:
        if citation.citation_num not in citation_to_saved_doc_id_map:
            citation_to_saved_doc_id_map[citation.citation_num] = (
                doc_id_to_saved_doc_id_map[citation.document_id]
            )

    return MessageSpecificCitations(citation_map=citation_to_saved_doc_id_map)


def _handle_search_tool_response_summary(
    packet: ToolResponse,
    db_session: Session,
    selected_search_docs: list[DbSearchDoc] | None,
    dedupe_docs: bool = False,
    user_files: list[UserFile] | None = None,
    loaded_user_files: list[InMemoryChatFile] | None = None,
) -> tuple[QADocsResponse, list[DbSearchDoc], list[int] | None]:
    response_summary = cast(SearchResponseSummary, packet.response)

    is_extended = isinstance(packet, ExtendedToolResponse)
    dropped_inds = None

    if not selected_search_docs:
        top_docs = chunks_or_sections_to_search_docs(response_summary.top_sections)

        deduped_docs = top_docs
        if (
            dedupe_docs and not is_extended
        ):  # Extended tool responses are already deduped
            deduped_docs, dropped_inds = dedupe_documents(top_docs)

        reference_db_search_docs = [
            create_db_search_doc(server_search_doc=doc, db_session=db_session)
            for doc in deduped_docs
        ]

    else:
        reference_db_search_docs = selected_search_docs

    doc_ids = {doc.id for doc in reference_db_search_docs}
    if user_files is not None and loaded_user_files is not None:
        for user_file in user_files:
            if user_file.id in doc_ids:
                continue

            associated_chat_file = next(
                (
                    file
                    for file in loaded_user_files
                    if file.file_id == str(user_file.file_id)
                ),
                None,
            )
            # Use create_search_doc_from_user_file to properly add the document to the database
            if associated_chat_file is not None:
                db_doc = create_search_doc_from_user_file(
                    user_file, associated_chat_file, db_session
                )
                reference_db_search_docs.append(db_doc)

    response_docs = [
        translate_db_search_doc_to_server_search_doc(db_search_doc)
        for db_search_doc in reference_db_search_docs
    ]

    level, question_num = None, None
    if isinstance(packet, ExtendedToolResponse):
        level, question_num = packet.level, packet.level_question_num
    return (
        QADocsResponse(
            rephrased_query=response_summary.rephrased_query,
            top_documents=response_docs,
            predicted_flow=response_summary.predicted_flow,
            predicted_search=response_summary.predicted_search,
            applied_source_filters=response_summary.final_filters.source_type,
            applied_time_cutoff=response_summary.final_filters.time_cutoff,
            recency_bias_multiplier=response_summary.recency_bias_multiplier,
            level=level,
            level_question_num=question_num,
        ),
        reference_db_search_docs,
        dropped_inds,
    )


def _handle_internet_search_tool_response_summary(
    packet: ToolResponse,
    db_session: Session,
) -> tuple[QADocsResponse, list[DbSearchDoc]]:
    internet_search_response = cast(InternetSearchResponse, packet.response)
    server_search_docs = internet_search_response_to_search_docs(
        internet_search_response
    )

    reference_db_search_docs = [
        create_db_search_doc(server_search_doc=doc, db_session=db_session)
        for doc in server_search_docs
    ]
    response_docs = [
        translate_db_search_doc_to_server_search_doc(db_search_doc)
        for db_search_doc in reference_db_search_docs
    ]
    return (
        QADocsResponse(
            rephrased_query=internet_search_response.revised_query,
            top_documents=response_docs,
            predicted_flow=QueryFlow.QUESTION_ANSWER,
            predicted_search=SearchType.SEMANTIC,
            applied_source_filters=[],
            applied_time_cutoff=None,
            recency_bias_multiplier=1.0,
        ),
        reference_db_search_docs,
    )


def _get_force_search_settings(
    new_msg_req: CreateChatMessageRequest,
    tools: list[Tool],
    user_file_ids: list[int],
    user_folder_ids: list[int],
) -> ForceUseTool:
    internet_search_available = any(
        isinstance(tool, InternetSearchTool) for tool in tools
    )
    search_tool_available = any(isinstance(tool, SearchTool) for tool in tools)

    if not internet_search_available and not search_tool_available:
        if new_msg_req.force_user_file_search:
            return ForceUseTool(force_use=True, tool_name=SearchTool._NAME)
        else:
            # Does not matter much which tool is set here as force is false and neither tool is available
            return ForceUseTool(force_use=False, tool_name=SearchTool._NAME)

    tool_name = SearchTool._NAME if search_tool_available else InternetSearchTool._NAME
    # Currently, the internet search tool does not support query override
    args = (
        {"query": new_msg_req.query_override}
        if new_msg_req.query_override and tool_name == SearchTool._NAME
        else None
    )

    # Create override_kwargs for the search tool if user_file_ids are provided
    override_kwargs = None
    if (user_file_ids or user_folder_ids) and tool_name == SearchTool._NAME:
        override_kwargs = SearchToolOverrideKwargs(
            force_no_rerank=False,
            alternate_db_session=None,
            retrieved_sections_callback=None,
            skip_query_analysis=False,
            user_file_ids=user_file_ids,
            user_folder_ids=user_folder_ids,
        )

    if new_msg_req.file_descriptors:
        # If user has uploaded files they're using, don't run any of the search tools
        return ForceUseTool(force_use=False, tool_name=tool_name)

    should_force_search = any(
        [
            new_msg_req.force_user_file_search,
            new_msg_req.retrieval_options
            and new_msg_req.retrieval_options.run_search
            == OptionalSearchSetting.ALWAYS,
            new_msg_req.search_doc_ids,
            new_msg_req.query_override is not None,
            DISABLE_LLM_CHOOSE_SEARCH,
        ]
    )

    if should_force_search:
        # If we are using selected docs, just put something here so the Tool doesn't need to build its own args via an LLM call
        args = {"query": new_msg_req.message} if new_msg_req.search_doc_ids else args

        return ForceUseTool(
            force_use=True,
            tool_name=tool_name,
            args=args,
            override_kwargs=override_kwargs,
        )

    return ForceUseTool(
        force_use=False, tool_name=tool_name, args=args, override_kwargs=override_kwargs
    )


def _get_user_knowledge_files(
    info: AnswerPostInfo,
    user_files: list[InMemoryChatFile],
    file_id_to_user_file: dict[str, InMemoryChatFile],
) -> Generator[UserKnowledgeFilePacket, None, None]:
    if not info.qa_docs_response:
        return

    logger.info(
        f"ORDERING: Processing search results for ordering {len(user_files)} user files"
    )

    # Extract document order from search results
    doc_order = []
    for doc in info.qa_docs_response.top_documents:
        doc_id = doc.document_id
        if str(doc_id).startswith("USER_FILE_CONNECTOR__"):
            file_id = doc_id.replace("USER_FILE_CONNECTOR__", "")
            if file_id in file_id_to_user_file:
                doc_order.append(file_id)

    logger.info(f"ORDERING: Found {len(doc_order)} files from search results")

    # Add any files that weren't in search results at the end
    missing_files = [
        f_id for f_id in file_id_to_user_file.keys() if f_id not in doc_order
    ]

    missing_files.extend(doc_order)
    doc_order = missing_files

    logger.info(f"ORDERING: Added {len(missing_files)} missing files to the end")

    # Reorder user files based on search results
    ordered_user_files = [
        file_id_to_user_file[f_id] for f_id in doc_order if f_id in file_id_to_user_file
    ]

    yield UserKnowledgeFilePacket(
        user_files=[
            FileDescriptor(
                id=str(file.file_id),
                type=ChatFileType.USER_KNOWLEDGE,
            )
            for file in ordered_user_files
        ]
    )


def _get_persona_for_chat_session(
    new_msg_req: CreateChatMessageRequest,
    user: User | None,
    db_session: Session,
    default_persona: Persona,
) -> Persona:
    if new_msg_req.alternate_assistant_id is not None:
        # Allows users to specify a temporary persona (assistant) in the chat session
        # this takes highest priority since it's user specified
        persona = get_persona_by_id(
            new_msg_req.alternate_assistant_id,
            user=user,
            db_session=db_session,
            is_for_edit=False,
        )
    elif new_msg_req.persona_override_config:
        # Certain endpoints allow users to specify arbitrary persona settings
        # this should never conflict with the alternate_assistant_id
        persona = create_temporary_persona(
            db_session=db_session,
            persona_config=new_msg_req.persona_override_config,
            user=user,
        )
    else:
        persona = default_persona

    if not persona:
        raise RuntimeError("No persona specified or found for chat session")
    return persona


ChatPacket = (
    StreamingError
    | QADocsResponse
    | LLMRelevanceFilterResponse
    | FinalUsedContextDocsResponse
    | ChatMessageDetail
    | SambaAIAnswerPiece
    | AllCitations
    | CitationInfo
    | FileChatDisplay
    | CustomToolResponse
    | MessageSpecificCitations
    | MessageResponseIDInfo
    | AgenticMessageResponseIDInfo
    | StreamStopInfo
    | AgentSearchPacket
    | UserKnowledgeFilePacket
)
ChatPacketStream = Iterator[ChatPacket]


def _process_tool_response(
    packet: ToolResponse,
    db_session: Session,
    selected_db_search_docs: list[DbSearchDoc] | None,
    info_by_subq: dict[SubQuestionKey, AnswerPostInfo],
    retrieval_options: RetrievalDetails | None,
    user_file_files: list[UserFile] | None,
    user_files: list[InMemoryChatFile] | None,
    file_id_to_user_file: dict[str, InMemoryChatFile],
    search_for_ordering_only: bool,
) -> Generator[ChatPacket, None, dict[SubQuestionKey, AnswerPostInfo]]:
    level, level_question_num = (
        (packet.level, packet.level_question_num)
        if isinstance(packet, ExtendedToolResponse)
        else BASIC_KEY
    )

    assert level is not None
    assert level_question_num is not None
    info = info_by_subq[SubQuestionKey(level=level, question_num=level_question_num)]

    # Skip LLM relevance processing entirely for ordering-only mode
    if search_for_ordering_only and packet.id == SECTION_RELEVANCE_LIST_ID:
        logger.info(
            "Fast path: Completely bypassing section relevance processing for ordering-only mode"
        )
        # Skip this packet entirely since it would trigger LLM processing
        return info_by_subq

    # TODO: don't need to dedupe here when we do it in agent flow
    if packet.id == SEARCH_RESPONSE_SUMMARY_ID:
        if search_for_ordering_only:
            logger.info(
                "Fast path: Skipping document deduplication for ordering-only mode"
            )

        (
            info.qa_docs_response,
            info.reference_db_search_docs,
            info.dropped_indices,
        ) = _handle_search_tool_response_summary(
            packet=packet,
            db_session=db_session,
            selected_search_docs=selected_db_search_docs,
            # Deduping happens at the last step to avoid harming quality by dropping content early on
            # Skip deduping completely for ordering-only mode to save time
            dedupe_docs=bool(
                not search_for_ordering_only
                and retrieval_options
                and retrieval_options.dedupe_docs
            ),
            user_files=user_file_files if search_for_ordering_only else [],
            loaded_user_files=(user_files if search_for_ordering_only else []),
        )

        # If we're using search just for ordering user files
        if search_for_ordering_only and user_files:
            yield from _get_user_knowledge_files(
                info=info,
                user_files=user_files,
                file_id_to_user_file=file_id_to_user_file,
            )

        yield info.qa_docs_response
    elif packet.id == SECTION_RELEVANCE_LIST_ID:
        relevance_sections = packet.response

        if search_for_ordering_only:
            logger.info(
                "Performance: Skipping relevance filtering for ordering-only mode"
            )
            return info_by_subq

        if info.reference_db_search_docs is None:
            logger.warning("No reference docs found for relevance filtering")
            return info_by_subq

        llm_indices = relevant_sections_to_indices(
            relevance_sections=relevance_sections,
            items=[
                translate_db_search_doc_to_server_search_doc(doc)
                for doc in info.reference_db_search_docs
            ],
        )

        if info.dropped_indices:
            llm_indices = drop_llm_indices(
                llm_indices=llm_indices,
                search_docs=info.reference_db_search_docs,
                dropped_indices=info.dropped_indices,
            )

        yield LLMRelevanceFilterResponse(llm_selected_doc_indices=llm_indices)
    elif packet.id == FINAL_CONTEXT_DOCUMENTS_ID:
        yield FinalUsedContextDocsResponse(final_context_docs=packet.response)

    elif packet.id == IMAGE_GENERATION_RESPONSE_ID:
        img_generation_response = cast(list[ImageGenerationResponse], packet.response)

        file_ids = save_files(
            urls=[img.url for img in img_generation_response if img.url],
            base64_files=[
                img.image_data for img in img_generation_response if img.image_data
            ],
        )
        info.ai_message_files.extend(
            [
                FileDescriptor(id=str(file_id), type=ChatFileType.IMAGE)
                for file_id in file_ids
            ]
        )
        yield FileChatDisplay(file_ids=[str(file_id) for file_id in file_ids])
    elif packet.id == INTERNET_SEARCH_RESPONSE_ID:
        (
            info.qa_docs_response,
            info.reference_db_search_docs,
        ) = _handle_internet_search_tool_response_summary(
            packet=packet,
            db_session=db_session,
        )
        yield info.qa_docs_response
    elif packet.id == CUSTOM_TOOL_RESPONSE_ID:
        custom_tool_response = cast(CustomToolCallSummary, packet.response)
        response_type = custom_tool_response.response_type
        if response_type in COMMON_TOOL_RESPONSE_TYPES:
            file_ids = custom_tool_response.tool_result.file_ids
            file_type = COMMON_TOOL_RESPONSE_TYPES[response_type]
            info.ai_message_files.extend(
                [
                    FileDescriptor(id=str(file_id), type=file_type)
                    for file_id in file_ids
                ]
            )
            yield FileChatDisplay(file_ids=[str(file_id) for file_id in file_ids])
        else:
            yield CustomToolResponse(
                response=custom_tool_response.tool_result,
                tool_name=custom_tool_response.tool_name,
            )

    return info_by_subq


def stream_chat_message_objects(
    new_msg_req: CreateChatMessageRequest,
    user: User | None,
    db_session: Session,
    # Needed to translate persona num_chunks to tokens to the LLM
    default_num_chunks: float = MAX_CHUNKS_FED_TO_CHAT,
    # For flow with search, don't include as many chunks as possible since we need to leave space
    # for the chat history, for smaller models, we likely won't get MAX_CHUNKS_FED_TO_CHAT chunks
    max_document_percentage: float = CHAT_TARGET_CHUNK_PERCENTAGE,
    # if specified, uses the last user message and does not create a new user message based
    # on the `new_msg_req.message`. Currently, requires a state where the last message is a
    litellm_additional_headers: dict[str, str] | None = None,
    custom_tool_additional_headers: dict[str, str] | None = None,
    is_connected: Callable[[], bool] | None = None,
    enforce_chat_session_id_for_search_docs: bool = True,
    bypass_acl: bool = False,
    include_contexts: bool = False,
    # a string which represents the history of a conversation. Used in cases like
    # Slack threads where the conversation cannot be represented by a chain of User/Assistant
    # messages.
    # NOTE: is not stored in the database at all.
    single_message_history: str | None = None,
) -> ChatPacketStream:
    """Streams in order:
    1. [conditional] Retrieved documents if a search needs to be run
    2. [conditional] LLM selected chunk indices if LLM chunk filtering is turned on
    3. [always] A set of streamed LLM tokens or an error anywhere along the line if something fails
    4. [always] Details on the final AI response message that is created
    """
    tenant_id = get_current_tenant_id()
    use_existing_user_message = new_msg_req.use_existing_user_message
    existing_assistant_message_id = new_msg_req.existing_assistant_message_id

    # Currently surrounding context is not supported for chat
    # Chat is already token heavy and harder for the model to process plus it would roll history over much faster
    new_msg_req.chunks_above = 0
    new_msg_req.chunks_below = 0

    llm: LLM

    try:
        # Move these variables inside the try block
        file_id_to_user_file = {}

        user_id = user.id if user is not None else None

        chat_session = get_chat_session_by_id(
            chat_session_id=new_msg_req.chat_session_id,
            user_id=user_id,
            db_session=db_session,
        )

        message_text = new_msg_req.message
        chat_session_id = new_msg_req.chat_session_id
        parent_id = new_msg_req.parent_message_id
        reference_doc_ids = new_msg_req.search_doc_ids
        retrieval_options = new_msg_req.retrieval_options
        new_msg_req.alternate_assistant_id

        # permanent "log" store, used primarily for debugging
        long_term_logger = LongTermLogger(
            metadata={"user_id": str(user_id), "chat_session_id": str(chat_session_id)}
        )

        persona = _get_persona_for_chat_session(
            new_msg_req=new_msg_req,
            user=user,
            db_session=db_session,
            default_persona=chat_session.persona,
        )

        multi_assistant_milestone, _is_new = create_milestone_if_not_exists(
            user=user,
            event_type=MilestoneRecordType.MULTIPLE_ASSISTANTS,
            db_session=db_session,
        )

        update_user_assistant_milestone(
            milestone=multi_assistant_milestone,
            user_id=str(user.id) if user else NO_AUTH_USER_ID,
            assistant_id=persona.id,
            db_session=db_session,
        )

        _, just_hit_multi_assistant_milestone = check_multi_assistant_milestone(
            milestone=multi_assistant_milestone,
            db_session=db_session,
        )

        if just_hit_multi_assistant_milestone:
            mt_cloud_telemetry(
                distinct_id=tenant_id,
                event=MilestoneRecordType.MULTIPLE_ASSISTANTS,
                properties=None,
            )

        # If a prompt override is specified via the API, use that with highest priority
        # but for saving it, we are just mapping it to an existing prompt
        prompt_id = new_msg_req.prompt_id
        if prompt_id is None and persona.prompts:
            prompt_id = sorted(persona.prompts, key=lambda x: x.id)[-1].id

        if reference_doc_ids is None and retrieval_options is None:
            raise RuntimeError(
                "Must specify a set of documents for chat or specify search options"
            )

        try:
            llm, fast_llm = get_llms_for_persona(
                persona=persona,
                llm_override=new_msg_req.llm_override or chat_session.llm_override,
                additional_headers=litellm_additional_headers,
                long_term_logger=long_term_logger,
            )
        except GenAIDisabledException:
            raise RuntimeError("LLM is disabled. Can't use chat flow without LLM.")

        llm_provider = llm.config.model_provider
        llm_model_name = llm.config.model_name

        llm_tokenizer = get_tokenizer(
            model_name=llm_model_name,
            provider_type=llm_provider,
        )
        llm_tokenizer_encode_func = cast(
            Callable[[str], list[int]], llm_tokenizer.encode
        )

        search_settings = get_current_search_settings(db_session)
        document_index = get_default_document_index(search_settings, None)

        # Every chat Session begins with an empty root message
        root_message = get_or_create_root_message(
            chat_session_id=chat_session_id, db_session=db_session
        )

        if parent_id is not None:
            parent_message = get_chat_message(
                chat_message_id=parent_id,
                user_id=user_id,
                db_session=db_session,
            )
        else:
            parent_message = root_message

        user_message = None

        if new_msg_req.regenerate:
            final_msg, history_msgs = create_chat_chain(
                stop_at_message_id=parent_id,
                chat_session_id=chat_session_id,
                db_session=db_session,
            )

        elif not use_existing_user_message:
            # Create new message at the right place in the tree and update the parent's child pointer
            # Don't commit yet until we verify the chat message chain
            user_message = create_new_chat_message(
                chat_session_id=chat_session_id,
                parent_message=parent_message,
                prompt_id=prompt_id,
                message=message_text,
                token_count=len(llm_tokenizer_encode_func(message_text)),
                message_type=MessageType.USER,
                files=None,  # Need to attach later for optimization to only load files once in parallel
                db_session=db_session,
                commit=False,
            )
            # re-create linear history of messages
            final_msg, history_msgs = create_chat_chain(
                chat_session_id=chat_session_id, db_session=db_session
            )
            if final_msg.id != user_message.id:
                db_session.rollback()
                raise RuntimeError(
                    "The new message was not on the mainline. "
                    "Be sure to update the chat pointers before calling this."
                )

            # NOTE: do not commit user message - it will be committed when the
            # assistant message is successfully generated
        else:
            # re-create linear history of messages
            final_msg, history_msgs = create_chat_chain(
                chat_session_id=chat_session_id, db_session=db_session
            )
            if existing_assistant_message_id is None:
                if final_msg.message_type != MessageType.USER:
                    raise RuntimeError(
                        "The last message was not a user message. Cannot call "
                        "`stream_chat_message_objects` with `is_regenerate=True` "
                        "when the last message is not a user message."
                    )
            else:
                if final_msg.id != existing_assistant_message_id:
                    raise RuntimeError(
                        "The last message was not the existing assistant message. "
                        f"Final message id: {final_msg.id}, "
                        f"existing assistant message id: {existing_assistant_message_id}"
                    )

        # load all files needed for this chat chain in memory
        files = load_all_chat_files(
            history_msgs, new_msg_req.file_descriptors, db_session
        )
        req_file_ids = [f["id"] for f in new_msg_req.file_descriptors]
        latest_query_files = [file for file in files if file.file_id in req_file_ids]
        user_file_ids = new_msg_req.user_file_ids or []
        user_folder_ids = new_msg_req.user_folder_ids or []

        if persona.user_files:
            for file in persona.user_files:
                user_file_ids.append(file.id)
        if persona.user_folders:
            for folder in persona.user_folders:
                user_folder_ids.append(folder.id)

        # Initialize flag for user file search
        use_search_for_user_files = False

        user_files: list[InMemoryChatFile] | None = None
        search_for_ordering_only = False
        user_file_files: list[UserFile] | None = None
        if user_file_ids or user_folder_ids:
            # Load user files
            user_files = load_in_memory_chat_files(
                user_file_ids or [],
                user_folder_ids or [],
                db_session,
            )
            user_file_files = get_user_files(
                user_file_ids or [],
                user_folder_ids or [],
                db_session,
            )
            # Store mapping of file_id to file for later reordering
            if user_files:
                file_id_to_user_file = {file.file_id: file for file in user_files}

            # Calculate token count for the files
            from sambaai.db.user_documents import calculate_user_files_token_count
            from sambaai.chat.prompt_builder.citations_prompt import (
                compute_max_document_tokens_for_persona,
            )

            total_tokens = calculate_user_files_token_count(
                user_file_ids or [],
                user_folder_ids or [],
                db_session,
            )

            # Calculate available tokens for documents based on prompt, user input, etc.
            available_tokens = compute_max_document_tokens_for_persona(
                db_session=db_session,
                persona=persona,
                actual_user_input=message_text,  # Use the actual user message
            )

            logger.debug(
                f"Total file tokens: {total_tokens}, Available tokens: {available_tokens}"
            )

            # ALWAYS use search for user files, but track if we need it for context or just ordering
            use_search_for_user_files = True
            # If files are small enough for context, we'll just use search for ordering
            search_for_ordering_only = total_tokens <= available_tokens

            if search_for_ordering_only:
                # Add original user files to context since they fit
                if user_files:
                    latest_query_files.extend(user_files)

        if user_message:
            attach_files_to_chat_message(
                chat_message=user_message,
                files=[
                    new_file.to_file_descriptor() for new_file in latest_query_files
                ],
                db_session=db_session,
                commit=False,
            )

        selected_db_search_docs = None
        selected_sections: list[InferenceSection] | None = None
        if reference_doc_ids:
            identifier_tuples = get_doc_query_identifiers_from_model(
                search_doc_ids=reference_doc_ids,
                chat_session=chat_session,
                user_id=user_id,
                db_session=db_session,
                enforce_chat_session_id_for_search_docs=enforce_chat_session_id_for_search_docs,
            )

            # Generates full documents currently
            # May extend to use sections instead in the future
            selected_sections = inference_sections_from_ids(
                doc_identifiers=identifier_tuples,
                document_index=document_index,
            )

            # Add a maximum context size in the case of user-selected docs to prevent
            # slight inaccuracies in context window size pruning from causing
            # the entire query to fail
            document_pruning_config = DocumentPruningConfig(
                is_manually_selected_docs=True,
                max_window_percentage=SELECTED_SECTIONS_MAX_WINDOW_PERCENTAGE,
            )

            # In case the search doc is deleted, just don't include it
            # though this should never happen
            db_search_docs_or_none = [
                get_db_search_doc_by_id(doc_id=doc_id, db_session=db_session)
                for doc_id in reference_doc_ids
            ]

            selected_db_search_docs = [
                db_sd for db_sd in db_search_docs_or_none if db_sd
            ]

        else:
            document_pruning_config = DocumentPruningConfig(
                max_chunks=int(
                    persona.num_chunks
                    if persona.num_chunks is not None
                    else default_num_chunks
                ),
                max_window_percentage=max_document_percentage,
            )

        # we don't need to reserve a message id if we're using an existing assistant message
        reserved_message_id = (
            final_msg.id
            if existing_assistant_message_id is not None
            else reserve_message_id(
                db_session=db_session,
                chat_session_id=chat_session_id,
                parent_message=(
                    user_message.id if user_message is not None else parent_message.id
                ),
                message_type=MessageType.ASSISTANT,
            )
        )
        yield MessageResponseIDInfo(
            user_message_id=user_message.id if user_message else None,
            reserved_assistant_message_id=reserved_message_id,
        )

        overridden_model = (
            new_msg_req.llm_override.model_version if new_msg_req.llm_override else None
        )

        def create_response(
            message: str,
            rephrased_query: str | None,
            reference_docs: list[DbSearchDoc] | None,
            files: list[FileDescriptor],
            token_count: int,
            citations: dict[int, int] | None,
            error: str | None,
            tool_call: ToolCall | None,
        ) -> ChatMessage:
            return create_new_chat_message(
                chat_session_id=chat_session_id,
                parent_message=(
                    final_msg
                    if existing_assistant_message_id is None
                    else parent_message
                ),
                prompt_id=prompt_id,
                overridden_model=overridden_model,
                message=message,
                rephrased_query=rephrased_query,
                token_count=token_count,
                message_type=MessageType.ASSISTANT,
                alternate_assistant_id=new_msg_req.alternate_assistant_id,
                error=error,
                reference_docs=reference_docs,
                files=files,
                citations=citations,
                tool_call=tool_call,
                db_session=db_session,
                commit=False,
                reserved_message_id=reserved_message_id,
                is_agentic=new_msg_req.use_agentic_search,
            )

        partial_response = create_response

        prompt_override = new_msg_req.prompt_override or chat_session.prompt_override
        if new_msg_req.persona_override_config:
            prompt_config = PromptConfig(
                system_prompt=new_msg_req.persona_override_config.prompts[
                    0
                ].system_prompt,
                task_prompt=new_msg_req.persona_override_config.prompts[0].task_prompt,
                datetime_aware=new_msg_req.persona_override_config.prompts[
                    0
                ].datetime_aware,
                include_citations=new_msg_req.persona_override_config.prompts[
                    0
                ].include_citations,
            )
        elif prompt_override:
            if not final_msg.prompt:
                raise ValueError(
                    "Prompt override cannot be applied, no base prompt found."
                )
            prompt_config = PromptConfig.from_model(
                final_msg.prompt,
                prompt_override=prompt_override,
            )
        else:
            prompt_config = PromptConfig.from_model(
                final_msg.prompt or persona.prompts[0]
            )

        answer_style_config = AnswerStyleConfig(
            citation_config=CitationConfig(
                all_docs_useful=selected_db_search_docs is not None
            ),
            document_pruning_config=document_pruning_config,
            structured_response_format=new_msg_req.structured_response_format,
        )

        tool_dict = construct_tools(
            persona=persona,
            prompt_config=prompt_config,
            db_session=db_session,
            user=user,
            user_knowledge_present=bool(user_files or user_folder_ids),
            llm=llm,
            fast_llm=fast_llm,
            use_file_search=new_msg_req.force_user_file_search,
            search_tool_config=SearchToolConfig(
                answer_style_config=answer_style_config,
                document_pruning_config=document_pruning_config,
                retrieval_options=retrieval_options or RetrievalDetails(),
                rerank_settings=new_msg_req.rerank_settings,
                selected_sections=selected_sections,
                chunks_above=new_msg_req.chunks_above,
                chunks_below=new_msg_req.chunks_below,
                full_doc=new_msg_req.full_doc,
                latest_query_files=latest_query_files,
                bypass_acl=bypass_acl,
            ),
            internet_search_tool_config=InternetSearchToolConfig(
                answer_style_config=answer_style_config,
            ),
            image_generation_tool_config=ImageGenerationToolConfig(
                additional_headers=litellm_additional_headers,
            ),
            custom_tool_config=CustomToolConfig(
                chat_session_id=chat_session_id,
                message_id=user_message.id if user_message else None,
                additional_headers=custom_tool_additional_headers,
            ),
        )

        tools: list[Tool] = []
        for tool_list in tool_dict.values():
            tools.extend(tool_list)

        force_use_tool = _get_force_search_settings(
            new_msg_req, tools, user_file_ids, user_folder_ids
        )

        # Set force_use if user files exceed token limit
        if use_search_for_user_files:
            try:
                # Check if search tool is available in the tools list
                search_tool_available = any(
                    isinstance(tool, SearchTool) for tool in tools
                )

                # If no search tool is available, add one
                if not search_tool_available:
                    logger.info("No search tool available, creating one for user files")
                    # Create a basic search tool config
                    search_tool_config = SearchToolConfig(
                        answer_style_config=answer_style_config,
                        document_pruning_config=document_pruning_config,
                        retrieval_options=retrieval_options or RetrievalDetails(),
                    )

                    # Create and add the search tool
                    search_tool = SearchTool(
                        db_session=db_session,
                        user=user,
                        persona=persona,
                        retrieval_options=search_tool_config.retrieval_options,
                        prompt_config=prompt_config,
                        llm=llm,
                        fast_llm=fast_llm,
                        pruning_config=search_tool_config.document_pruning_config,
                        answer_style_config=search_tool_config.answer_style_config,
                        evaluation_type=(
                            LLMEvaluationType.BASIC
                            if persona.llm_relevance_filter
                            else LLMEvaluationType.SKIP
                        ),
                        bypass_acl=bypass_acl,
                    )

                    # Add the search tool to the tools list
                    tools.append(search_tool)

                    logger.info(
                        "Added search tool for user files that exceed token limit"
                    )

                # Now set force_use_tool.force_use to True
                force_use_tool.force_use = True
                force_use_tool.tool_name = SearchTool._NAME

                # Set query argument if not already set
                if not force_use_tool.args:
                    force_use_tool.args = {"query": final_msg.message}

                # Pass the user file IDs to the search tool
                if user_file_ids or user_folder_ids:
                    # Create a BaseFilters object with user_file_ids
                    if not retrieval_options:
                        retrieval_options = RetrievalDetails()
                    if not retrieval_options.filters:
                        retrieval_options.filters = BaseFilters()

                    # Set user file and folder IDs in the filters
                    retrieval_options.filters.user_file_ids = user_file_ids
                    retrieval_options.filters.user_folder_ids = user_folder_ids

                    # Create override kwargs for the search tool

                    override_kwargs = SearchToolOverrideKwargs(
                        force_no_rerank=search_for_ordering_only,  # Skip reranking for ordering-only
                        alternate_db_session=None,
                        retrieved_sections_callback=None,
                        skip_query_analysis=search_for_ordering_only,  # Skip query analysis for ordering-only
                        user_file_ids=user_file_ids,
                        user_folder_ids=user_folder_ids,
                        ordering_only=search_for_ordering_only,  # Set ordering_only flag for fast path
                    )

                    # Set the override kwargs in the force_use_tool
                    force_use_tool.override_kwargs = override_kwargs

                    if search_for_ordering_only:
                        logger.info(
                            "Fast path: Configured search tool with optimized settings for ordering-only"
                        )
                        logger.info(
                            "Fast path: Skipping reranking and query analysis for ordering-only mode"
                        )
                        logger.info(
                            f"Using {len(user_file_ids or [])} files and {len(user_folder_ids or [])} folders"
                        )
                    else:
                        logger.info(
                            "Configured search tool to use ",
                            f"{len(user_file_ids or [])} files and {len(user_folder_ids or [])} folders",
                        )
            except Exception as e:
                logger.exception(
                    f"Error configuring search tool for user files: {str(e)}"
                )
                use_search_for_user_files = False

        # TODO: unify message history with single message history
        message_history = [
            PreviousMessage.from_chat_message(msg, files) for msg in history_msgs
        ]
        if not use_search_for_user_files and user_files:
            yield UserKnowledgeFilePacket(
                user_files=[
                    FileDescriptor(
                        id=str(file.file_id), type=ChatFileType.USER_KNOWLEDGE
                    )
                    for file in user_files
                ]
            )

        if search_for_ordering_only:
            logger.info(
                "Performance: Forcing LLMEvaluationType.SKIP to prevent chunk evaluation for ordering-only search"
            )

        prompt_builder = AnswerPromptBuilder(
            user_message=default_build_user_message(
                user_query=final_msg.message,
                prompt_config=prompt_config,
                files=latest_query_files,
                single_message_history=single_message_history,
            ),
            system_message=default_build_system_message(prompt_config, llm.config),
            message_history=message_history,
            llm_config=llm.config,
            raw_user_query=final_msg.message,
            raw_user_uploaded_files=latest_query_files or [],
            single_message_history=single_message_history,
        )

        # LLM prompt building, response capturing, etc.

        answer = Answer(
            prompt_builder=prompt_builder,
            is_connected=is_connected,
            latest_query_files=latest_query_files,
            answer_style_config=answer_style_config,
            llm=(
                llm
                or get_main_llm_from_tuple(
                    get_llms_for_persona(
                        persona=persona,
                        llm_override=(
                            new_msg_req.llm_override or chat_session.llm_override
                        ),
                        additional_headers=litellm_additional_headers,
                    )
                )
            ),
            fast_llm=fast_llm,
            force_use_tool=force_use_tool,
            persona=persona,
            rerank_settings=new_msg_req.rerank_settings,
            chat_session_id=chat_session_id,
            current_agent_message_id=reserved_message_id,
            tools=tools,
            db_session=db_session,
            use_agentic_search=new_msg_req.use_agentic_search,
        )

        info_by_subq: dict[SubQuestionKey, AnswerPostInfo] = defaultdict(
            lambda: AnswerPostInfo(ai_message_files=[])
        )
        refined_answer_improvement = True
        for packet in answer.processed_streamed_output:
            if isinstance(packet, ToolResponse):
                info_by_subq = yield from _process_tool_response(
                    packet=packet,
                    db_session=db_session,
                    selected_db_search_docs=selected_db_search_docs,
                    info_by_subq=info_by_subq,
                    retrieval_options=retrieval_options,
                    user_file_files=user_file_files,
                    user_files=user_files,
                    file_id_to_user_file=file_id_to_user_file,
                    search_for_ordering_only=search_for_ordering_only,
                )

            elif isinstance(packet, StreamStopInfo):
                if packet.stop_reason == StreamStopReason.FINISHED:
                    yield packet
            elif isinstance(packet, RefinedAnswerImprovement):
                refined_answer_improvement = packet.refined_answer_improvement
                yield packet
            else:
                if isinstance(packet, ToolCallFinalResult):
                    level, level_question_num = (
                        (packet.level, packet.level_question_num)
                        if packet.level is not None
                        and packet.level_question_num is not None
                        else BASIC_KEY
                    )
                    info = info_by_subq[
                        SubQuestionKey(level=level, question_num=level_question_num)
                    ]
                    info.tool_result = packet
                yield cast(ChatPacket, packet)

    except ValueError as e:
        logger.exception("Failed to process chat message.")

        error_msg = str(e)
        yield StreamingError(error=error_msg)
        db_session.rollback()
        return

    except Exception as e:
        logger.exception(f"Failed to process chat message due to {e}")
        error_msg = str(e)
        stack_trace = traceback.format_exc()

        if isinstance(e, ToolCallException):
            yield StreamingError(error=error_msg, stack_trace=stack_trace)
        elif llm:
            client_error_msg = litellm_exception_to_error_msg(e, llm)
            if llm.config.api_key and len(llm.config.api_key) > 2:
                client_error_msg = client_error_msg.replace(
                    llm.config.api_key, "[REDACTED_API_KEY]"
                )
                stack_trace = stack_trace.replace(
                    llm.config.api_key, "[REDACTED_API_KEY]"
                )

            yield StreamingError(error=client_error_msg, stack_trace=stack_trace)

        db_session.rollback()
        return

    yield from _post_llm_answer_processing(
        answer=answer,
        info_by_subq=info_by_subq,
        tool_dict=tool_dict,
        partial_response=partial_response,
        llm_tokenizer_encode_func=llm_tokenizer_encode_func,
        db_session=db_session,
        chat_session_id=chat_session_id,
        refined_answer_improvement=refined_answer_improvement,
    )


def _post_llm_answer_processing(
    answer: Answer,
    info_by_subq: dict[SubQuestionKey, AnswerPostInfo],
    tool_dict: dict[int, list[Tool]],
    partial_response: PartialResponse,
    llm_tokenizer_encode_func: Callable[[str], list[int]],
    db_session: Session,
    chat_session_id: UUID,
    refined_answer_improvement: bool | None,
) -> Generator[ChatPacket, None, None]:
    """
    Stores messages in the db and yields some final packets to the frontend
    """
    # Post-LLM answer processing
    try:
        tool_name_to_tool_id: dict[str, int] = {}
        for tool_id, tool_list in tool_dict.items():
            for tool in tool_list:
                tool_name_to_tool_id[tool.name] = tool_id

        subq_citations = answer.citations_by_subquestion()
        for subq_key in subq_citations:
            info = info_by_subq[subq_key]
            logger.debug("Post-LLM answer processing")
            if info.reference_db_search_docs:
                info.message_specific_citations = _translate_citations(
                    citations_list=subq_citations[subq_key],
                    db_docs=info.reference_db_search_docs,
                )

            # TODO: AllCitations should contain subq info?
            if not answer.is_cancelled():
                yield AllCitations(citations=subq_citations[subq_key])

        # Saving Gen AI answer and responding with message info

        basic_key = SubQuestionKey(level=BASIC_KEY[0], question_num=BASIC_KEY[1])
        info = (
            info_by_subq[basic_key]
            if basic_key in info_by_subq
            else info_by_subq[
                SubQuestionKey(
                    level=AGENT_SEARCH_INITIAL_KEY[0],
                    question_num=AGENT_SEARCH_INITIAL_KEY[1],
                )
            ]
        )
        gen_ai_response_message = partial_response(
            message=answer.llm_answer,
            rephrased_query=(
                info.qa_docs_response.rephrased_query if info.qa_docs_response else None
            ),
            reference_docs=info.reference_db_search_docs,
            files=info.ai_message_files,
            token_count=len(llm_tokenizer_encode_func(answer.llm_answer)),
            citations=(
                info.message_specific_citations.citation_map
                if info.message_specific_citations
                else None
            ),
            error=ERROR_TYPE_CANCELLED if answer.is_cancelled() else None,
            tool_call=(
                ToolCall(
                    tool_id=(
                        tool_name_to_tool_id.get(info.tool_result.tool_name, 0)
                        if info.tool_result
                        else None
                    ),
                    tool_name=info.tool_result.tool_name if info.tool_result else None,
                    tool_arguments=(
                        info.tool_result.tool_args if info.tool_result else None
                    ),
                    tool_result=(
                        info.tool_result.tool_result if info.tool_result else None
                    ),
                )
                if info.tool_result
                else None
            ),
        )

        # add answers for levels >= 1, where each level has the previous as its parent. Use
        # the answer_by_level method in answer.py to get the answers for each level
        next_level = 1
        prev_message = gen_ai_response_message
        agent_answers = answer.llm_answer_by_level()
        agentic_message_ids = []
        while next_level in agent_answers:
            next_answer = agent_answers[next_level]
            info = info_by_subq[
                SubQuestionKey(
                    level=next_level, question_num=AGENT_SEARCH_INITIAL_KEY[1]
                )
            ]
            next_answer_message = create_new_chat_message(
                chat_session_id=chat_session_id,
                parent_message=prev_message,
                message=next_answer,
                prompt_id=None,
                token_count=len(llm_tokenizer_encode_func(next_answer)),
                message_type=MessageType.ASSISTANT,
                db_session=db_session,
                files=info.ai_message_files,
                reference_docs=info.reference_db_search_docs,
                citations=(
                    info.message_specific_citations.citation_map
                    if info.message_specific_citations
                    else None
                ),
                error=ERROR_TYPE_CANCELLED if answer.is_cancelled() else None,
                refined_answer_improvement=refined_answer_improvement,
                is_agentic=True,
            )
            agentic_message_ids.append(
                AgentMessageIDInfo(level=next_level, message_id=next_answer_message.id)
            )
            next_level += 1
            prev_message = next_answer_message

        logger.debug("Committing messages")
        # Explicitly update the timestamp on the chat session
        update_chat_session_updated_at_timestamp(chat_session_id, db_session)
        db_session.commit()  # actually save user / assistant message

        yield AgenticMessageResponseIDInfo(agentic_message_ids=agentic_message_ids)

        yield translate_db_message_to_chat_message_detail(gen_ai_response_message)
    except Exception as e:
        error_msg = str(e)
        logger.exception(error_msg)

        # Frontend will erase whatever answer and show this instead
        yield StreamingError(error="Failed to parse LLM output")


@log_generator_function_time()
def stream_chat_message(
    new_msg_req: CreateChatMessageRequest,
    user: User | None,
    litellm_additional_headers: dict[str, str] | None = None,
    custom_tool_additional_headers: dict[str, str] | None = None,
    is_connected: Callable[[], bool] | None = None,
) -> Iterator[str]:
    start_time = time.time()
    with get_session_context_manager() as db_session:
        objects = stream_chat_message_objects(
            new_msg_req=new_msg_req,
            user=user,
            db_session=db_session,
            litellm_additional_headers=litellm_additional_headers,
            custom_tool_additional_headers=custom_tool_additional_headers,
            is_connected=is_connected,
        )
        for obj in objects:
            # Check if this is a QADocsResponse with document results
            if isinstance(obj, QADocsResponse):
                document_retrieval_latency = time.time() - start_time
                logger.debug(f"First doc time: {document_retrieval_latency}")

            yield get_json_line(obj.model_dump())


@log_function_time()
def gather_stream_for_slack(
    packets: ChatPacketStream,
) -> ChatSambaAIBotResponse:
    response = ChatSambaAIBotResponse()

    answer = ""
    for packet in packets:
        if isinstance(packet, SambaAIAnswerPiece) and packet.answer_piece:
            answer += packet.answer_piece
        elif isinstance(packet, QADocsResponse):
            response.docs = packet
        elif isinstance(packet, StreamingError):
            response.error_msg = packet.error
        elif isinstance(packet, ChatMessageDetail):
            response.chat_message_id = packet.message_id
        elif isinstance(packet, LLMRelevanceFilterResponse):
            response.llm_selected_doc_indices = packet.llm_selected_doc_indices
        elif isinstance(packet, AllCitations):
            response.citations = packet.citations

    if answer:
        response.answer = answer

    return response
