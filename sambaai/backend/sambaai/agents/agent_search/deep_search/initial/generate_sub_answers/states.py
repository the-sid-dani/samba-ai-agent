from typing import TypedDict

from sambaai.agents.agent_search.core_state import CoreState
from sambaai.agents.agent_search.deep_search.main.states import (
    InitialAnswerUpdate,
)
from sambaai.agents.agent_search.deep_search.main.states import (
    InitialQuestionDecompositionUpdate,
)
from sambaai.agents.agent_search.deep_search.main.states import (
    SubQuestionResultsUpdate,
)
from sambaai.context.search.models import InferenceSection


### States ###
class SubQuestionAnsweringInput(CoreState):
    exploratory_search_results: list[InferenceSection]


## Graph State
class SubQuestionAnsweringState(
    # This includes the core state
    SubQuestionAnsweringInput,
    InitialQuestionDecompositionUpdate,
    InitialAnswerUpdate,
    SubQuestionResultsUpdate,
):
    pass


## Graph Output State
class SubQuestionAnsweringOutput(TypedDict):
    log_messages: list[str]
