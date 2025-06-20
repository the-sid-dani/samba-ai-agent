import csv
import json
from bisect import bisect_left
from datetime import datetime
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sambaai.agents.agent_search.shared_graph_utils.models import QueryExpansionType
from sambaai.configs.app_configs import POSTGRES_API_SERVER_POOL_OVERFLOW
from sambaai.configs.app_configs import POSTGRES_API_SERVER_POOL_SIZE
from sambaai.configs.chat_configs import DOC_TIME_DECAY
from sambaai.configs.chat_configs import HYBRID_ALPHA
from sambaai.configs.chat_configs import HYBRID_ALPHA_KEYWORD
from sambaai.configs.chat_configs import NUM_RETURNED_HITS
from sambaai.configs.chat_configs import TITLE_CONTENT_RATIO
from sambaai.context.search.models import IndexFilters
from sambaai.context.search.models import InferenceChunk
from sambaai.context.search.models import RerankingDetails
from sambaai.context.search.postprocessing.postprocessing import semantic_reranking
from sambaai.context.search.preprocessing.preprocessing import query_analysis
from sambaai.context.search.retrieval.search_runner import get_query_embedding
from sambaai.context.search.utils import remove_stop_words_and_punctuation
from sambaai.db.engine import get_session_with_current_tenant
from sambaai.db.engine import SqlEngine
from sambaai.db.search_settings import get_current_search_settings
from sambaai.db.search_settings import get_multilingual_expansion
from sambaai.document_index.factory import get_default_document_index
from sambaai.document_index.interfaces import DocumentIndex
from sambaai.utils.logger import setup_logger
from shared_configs.configs import MULTI_TENANT

logger = setup_logger(__name__)


class SearchEvalParameters(BaseModel):
    hybrid_alpha: float
    hybrid_alpha_keyword: float
    doc_time_decay: float
    num_returned_hits: int
    rank_profile: QueryExpansionType
    offset: int
    title_content_ratio: float
    user_email: str | None
    skip_rerank: bool
    eval_topk: int
    export_folder: str


def _load_search_parameters() -> SearchEvalParameters:
    current_dir = Path(__file__).parent
    config_path = current_dir / "search_eval_config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Search eval config file not found at {config_path}")
    with config_path.open("r") as file:
        config = yaml.safe_load(file)

    export_folder = config.get("EXPORT_FOLDER", "eval-%Y-%m-%d-%H-%M-%S")
    export_folder = datetime.now().strftime(export_folder)

    export_path = Path(export_folder)
    export_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created export folder: {export_path}")

    search_parameters = SearchEvalParameters(
        hybrid_alpha=config.get("HYBRID_ALPHA") or HYBRID_ALPHA,
        hybrid_alpha_keyword=config.get("HYBRID_ALPHA_KEYWORD") or HYBRID_ALPHA_KEYWORD,
        doc_time_decay=config.get("DOC_TIME_DECAY") or DOC_TIME_DECAY,
        num_returned_hits=config.get("NUM_RETURNED_HITS") or NUM_RETURNED_HITS,
        rank_profile=config.get("RANK_PROFILE") or QueryExpansionType.SEMANTIC,
        offset=config.get("OFFSET") or 0,
        title_content_ratio=config.get("TITLE_CONTENT_RATIO") or TITLE_CONTENT_RATIO,
        user_email=config.get("USER_EMAIL"),
        skip_rerank=config.get("SKIP_RERANK", False),
        eval_topk=config.get("EVAL_TOPK", 20),
        export_folder=export_folder,
    )
    logger.info(f"Using search parameters: {search_parameters}")

    config_file = export_path / "search_eval_config.yaml"
    with config_file.open("w") as file:
        search_parameters_dict = search_parameters.model_dump(mode="python")
        search_parameters_dict["rank_profile"] = search_parameters.rank_profile.value
        yaml.dump(search_parameters_dict, file, sort_keys=False)
    logger.info(f"Exported config to {config_file}")

    return search_parameters


def _load_query_pairs() -> list[tuple[str, str]]:
    current_dir = Path(__file__).parent
    search_queries_path = current_dir / "search_queries.json"
    if not search_queries_path.exists():
        raise FileNotFoundError(
            f"Search queries file not found at {search_queries_path}"
        )
    with search_queries_path.open("r") as file:
        orig_queries = json.load(file)

    alt_queries_path = current_dir / "search_queries_modified.json"
    if not alt_queries_path.exists():
        raise FileNotFoundError(
            f"Modified search queries file not found at {alt_queries_path}. "
            "Try running generate_search_queries.py."
        )
    with alt_queries_path.open("r") as file:
        alt_queries = json.load(file)

    if len(orig_queries) != len(alt_queries):
        raise ValueError(
            "Number of original and modified queries must be the same. "
            "Try running generate_search_queries.py again."
        )

    return list(zip(orig_queries, alt_queries))


def _search_one_query(
    alt_query: str,
    multilingual_expansion: list[str],
    document_index: DocumentIndex,
    db_session: Session,
    search_parameters: SearchEvalParameters,
) -> list[InferenceChunk]:
    # the retrieval preprocessing is fairly stripped down so the query doesn't unexpectly change
    query_embedding = get_query_embedding(alt_query, db_session)

    all_query_terms = alt_query.split()
    processed_keywords = (
        remove_stop_words_and_punctuation(all_query_terms)
        if not multilingual_expansion
        else all_query_terms
    )

    is_keyword = query_analysis(alt_query)[0]
    hybrid_alpha = (
        search_parameters.hybrid_alpha_keyword
        if is_keyword
        else search_parameters.hybrid_alpha
    )

    access_control_list = ["PUBLIC"]
    if search_parameters.user_email:
        access_control_list.append(f"user_email:{search_parameters.user_email}")
    filters = IndexFilters(
        tags=[],
        user_file_ids=[],
        user_folder_ids=[],
        access_control_list=access_control_list,
        tenant_id=None,
    )

    results = document_index.hybrid_retrieval(
        query=alt_query,
        query_embedding=query_embedding,
        final_keywords=processed_keywords,
        filters=filters,
        hybrid_alpha=hybrid_alpha,
        time_decay_multiplier=search_parameters.doc_time_decay,
        num_to_retrieve=search_parameters.num_returned_hits,
        ranking_profile_type=search_parameters.rank_profile,
        offset=search_parameters.offset,
        title_content_ratio=search_parameters.title_content_ratio,
    )

    return [result.to_inference_chunk() for result in results]


def _rerank_one_query(
    orig_query: str,
    retrieved_chunks: list[InferenceChunk],
    rerank_settings: RerankingDetails,
    search_parameters: SearchEvalParameters,
) -> list[InferenceChunk]:
    assert not search_parameters.skip_rerank, "Reranking is disabled"
    return semantic_reranking(
        query_str=orig_query,
        rerank_settings=rerank_settings,
        chunks=retrieved_chunks,
        rerank_metrics_callback=None,
    )[0]


def _evaluate_one_query(
    search_results: list[InferenceChunk],
    rerank_results: list[InferenceChunk],
    search_parameters: SearchEvalParameters,
) -> list[float]:
    search_topk = search_results[: search_parameters.eval_topk]
    rerank_topk = rerank_results[: search_parameters.eval_topk]

    # get the score adjusted topk (topk where the score is at least 50% of the top score)
    # could be more than topk if top scores are similar, may or may not be a good thing
    # can change by swapping rerank_results with rerank_topk in bisect
    adj_topk = bisect_left(
        rerank_results,
        -0.5 * cast(float, rerank_results[0].score),
        key=lambda x: -cast(float, x.score),
    )
    search_adj_topk = search_results[:adj_topk]
    rerank_adj_topk = rerank_results[:adj_topk]

    # compute metrics
    search_ranks = {chunk.unique_id: rank for rank, chunk in enumerate(search_results)}
    return [
        *_compute_jaccard_and_missing_chunks_ratio(search_topk, rerank_topk),
        _compute_average_rank_change(search_ranks, rerank_topk),
        # score adjusted metrics
        *_compute_jaccard_and_missing_chunks_ratio(search_adj_topk, rerank_adj_topk),
        _compute_average_rank_change(search_ranks, rerank_adj_topk),
    ]


def _compute_jaccard_and_missing_chunks_ratio(
    search_topk: list[InferenceChunk], rerank_topk: list[InferenceChunk]
) -> tuple[float, float]:
    search_chunkids = {chunk.unique_id for chunk in search_topk}
    rerank_chunkids = {chunk.unique_id for chunk in rerank_topk}
    jaccard_similarity = len(search_chunkids & rerank_chunkids) / len(
        search_chunkids | rerank_chunkids
    )
    missing_chunks_ratio = len(rerank_chunkids - search_chunkids) / len(rerank_chunkids)
    return jaccard_similarity, missing_chunks_ratio


def _compute_average_rank_change(
    search_ranks: dict[str, int], rerank_topk: list[InferenceChunk]
) -> float:
    rank_changes = [
        abs(search_ranks[chunk.unique_id] - rerank_rank)
        for rerank_rank, chunk in enumerate(rerank_topk)
    ]
    return sum(rank_changes) / len(rank_changes)


def run_search_eval() -> None:
    if MULTI_TENANT:
        raise ValueError("Multi-tenant is not supported currently")

    SqlEngine.init_engine(
        pool_size=POSTGRES_API_SERVER_POOL_SIZE,
        max_overflow=POSTGRES_API_SERVER_POOL_OVERFLOW,
    )

    query_pairs = _load_query_pairs()
    search_parameters = _load_search_parameters()

    with get_session_with_current_tenant() as db_session:
        multilingual_expansion = get_multilingual_expansion(db_session)
        search_settings = get_current_search_settings(db_session)
        document_index = get_default_document_index(search_settings, None)
        rerank_settings = RerankingDetails.from_db_model(search_settings)

        if search_parameters.skip_rerank:
            logger.warning("Reranking is disabled, evaluation will not run")
        elif rerank_settings.rerank_model_name is None:
            raise ValueError(
                "Reranking is enabled but no reranker is configured. "
                "Please set the reranker in the admin panel search settings."
            )

        export_path = Path(search_parameters.export_folder)
        search_result_file = export_path / "search_results.csv"
        eval_result_file = export_path / "eval_results.csv"
        with (
            search_result_file.open("w") as search_file,
            eval_result_file.open("w") as eval_file,
        ):
            search_csv_writer = csv.writer(search_file)
            eval_csv_writer = csv.writer(eval_file)
            search_csv_writer.writerow(
                ["source", "query", "rank", "score", "doc_id", "chunk_id"]
            )
            eval_csv_writer.writerow(
                [
                    "query",
                    "jaccard_similarity",
                    "missing_chunks_ratio",
                    "average_rank_change",
                    "jaccard_similarity_adj",
                    "missing_chunks_ratio_adj",
                    "average_rank_change_adj",
                ]
            )

            sum_metrics = [0.0] * 6
            for orig_query, alt_query in query_pairs:
                search_results = _search_one_query(
                    alt_query,
                    multilingual_expansion,
                    document_index,
                    db_session,
                    search_parameters,
                )
                for rank, result in enumerate(search_results):
                    search_csv_writer.writerow(
                        [
                            "search",
                            alt_query,
                            rank,
                            result.score,
                            result.document_id,
                            result.chunk_id,
                        ]
                    )

                if not search_parameters.skip_rerank:
                    rerank_results = _rerank_one_query(
                        orig_query, search_results, rerank_settings, search_parameters
                    )
                    for rank, result in enumerate(rerank_results):
                        search_csv_writer.writerow(
                            [
                                "rerank",
                                orig_query,
                                rank,
                                result.score,
                                result.document_id,
                                result.chunk_id,
                            ]
                        )

                    metrics = _evaluate_one_query(
                        search_results, rerank_results, search_parameters
                    )
                    eval_csv_writer.writerow([orig_query, *metrics])
                    sum_metrics = [
                        sum_metric + metric
                        for sum_metric, metric in zip(sum_metrics, metrics)
                    ]

    logger.info(
        f"Exported individual results to {search_result_file} and {eval_result_file}"
    )

    if not search_parameters.skip_rerank:
        average_metrics = [metric / len(query_pairs) for metric in sum_metrics]
        logger.info(f"Jaccard similarity: {average_metrics[0]}")
        logger.info(f"Average missing chunks ratio: {average_metrics[1]}")
        logger.info(f"Average rank change: {average_metrics[2]}")
        logger.info(f"Jaccard similarity (adjusted): {average_metrics[3]}")
        logger.info(f"Average missing chunks ratio (adjusted): {average_metrics[4]}")
        logger.info(f"Average rank change (adjusted): {average_metrics[5]}")

        aggregate_file = export_path / "aggregate_results.csv"
        with aggregate_file.open("w") as file:
            aggregate_csv_writer = csv.writer(file)
            aggregate_csv_writer.writerow(
                [
                    "jaccard_similarity",
                    "missing_chunks_ratio",
                    "average_rank_change",
                    "jaccard_similarity_adj",
                    "missing_chunks_ratio_adj",
                    "average_rank_change_adj",
                ]
            )
            aggregate_csv_writer.writerow(average_metrics)
            logger.info(f"Exported aggregate results to {aggregate_file}")


if __name__ == "__main__":
    run_search_eval()
