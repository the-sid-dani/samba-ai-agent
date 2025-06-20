import csv
import io
from datetime import datetime
from datetime import timezone

from celery import shared_task
from celery import Task

from ee.sambaai.background.task_name_builders import query_history_task_name
from ee.sambaai.server.query_history.api import fetch_and_process_chat_session_history
from ee.sambaai.server.query_history.api import ONYX_ANONYMIZED_EMAIL
from ee.sambaai.server.query_history.models import QuestionAnswerPairSnapshot
from sambaai.background.celery.apps.heavy import celery_app
from sambaai.background.task_utils import construct_query_history_report_name
from sambaai.configs.app_configs import JOB_TIMEOUT
from sambaai.configs.app_configs import ONYX_QUERY_HISTORY_TYPE
from sambaai.configs.constants import FileOrigin
from sambaai.configs.constants import FileType
from sambaai.configs.constants import SambaAICeleryTask
from sambaai.configs.constants import QueryHistoryType
from sambaai.db.engine import get_session_with_current_tenant
from sambaai.db.enums import TaskStatus
from sambaai.db.tasks import delete_task_with_id
from sambaai.db.tasks import mark_task_as_finished_with_id
from sambaai.db.tasks import register_task
from sambaai.file_store.file_store import get_default_file_store
from sambaai.utils.logger import setup_logger


logger = setup_logger()


@shared_task(
    name=SambaAICeleryTask.EXPORT_QUERY_HISTORY_TASK,
    ignore_result=True,
    soft_time_limit=JOB_TIMEOUT,
    bind=True,
    trail=False,
)
def export_query_history_task(self: Task, *, start: datetime, end: datetime) -> None:
    if not self.request.id:
        raise RuntimeError("No task id defined for this task; cannot identify it")

    task_id = self.request.id
    start_time = datetime.now(tz=timezone.utc)

    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=list(QuestionAnswerPairSnapshot.model_fields.keys()),
    )
    writer.writeheader()

    with get_session_with_current_tenant() as db_session:
        try:
            register_task(
                db_session=db_session,
                task_name=query_history_task_name(start=start, end=end),
                task_id=task_id,
                status=TaskStatus.STARTED,
                start_time=start_time,
            )

            snapshot_generator = fetch_and_process_chat_session_history(
                db_session=db_session,
                start=start,
                end=end,
            )

            for snapshot in snapshot_generator:
                if ONYX_QUERY_HISTORY_TYPE == QueryHistoryType.ANONYMIZED:
                    snapshot.user_email = ONYX_ANONYMIZED_EMAIL

                writer.writerows(
                    qa_pair.to_json()
                    for qa_pair in QuestionAnswerPairSnapshot.from_chat_session_snapshot(
                        snapshot
                    )
                )

        except Exception:
            logger.exception(f"Failed to export query history with {task_id=}")
            mark_task_as_finished_with_id(
                db_session=db_session,
                task_id=task_id,
                success=False,
            )
            raise

    report_name = construct_query_history_report_name(task_id)
    with get_session_with_current_tenant() as db_session:
        try:
            stream.seek(0)
            get_default_file_store(db_session).save_file(
                file_name=report_name,
                content=stream,
                display_name=report_name,
                file_origin=FileOrigin.QUERY_HISTORY_CSV,
                file_type=FileType.CSV,
                file_metadata={
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "start_time": start_time.isoformat(),
                },
            )

            delete_task_with_id(
                db_session=db_session,
                task_id=task_id,
            )
        except Exception:
            logger.exception(
                f"Failed to save query history export file; {report_name=}"
            )
            mark_task_as_finished_with_id(
                db_session=db_session,
                task_id=task_id,
                success=False,
            )
            raise


celery_app.autodiscover_tasks(
    [
        "ee.sambaai.background.celery.tasks.doc_permission_syncing",
        "ee.sambaai.background.celery.tasks.external_group_syncing",
        "ee.sambaai.background.celery.tasks.cleanup",
    ]
)
