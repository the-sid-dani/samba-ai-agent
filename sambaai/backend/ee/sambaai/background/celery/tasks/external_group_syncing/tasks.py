import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import cast
from uuid import uuid4

from celery import Celery
from celery import shared_task
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from pydantic import ValidationError
from redis import Redis
from redis.lock import Lock as RedisLock

from ee.sambaai.background.celery.tasks.external_group_syncing.group_sync_utils import (
    mark_all_relevant_cc_pairs_as_external_group_synced,
)
from ee.sambaai.db.connector_credential_pair import get_all_auto_sync_cc_pairs
from ee.sambaai.db.connector_credential_pair import get_cc_pairs_by_source
from ee.sambaai.db.external_perm import ExternalUserGroup
from ee.sambaai.db.external_perm import replace_user__ext_group_for_cc_pair
from ee.sambaai.external_permissions.sync_params import EXTERNAL_GROUP_SYNC_PERIODS
from ee.sambaai.external_permissions.sync_params import GROUP_PERMISSIONS_FUNC_MAP
from ee.sambaai.external_permissions.sync_params import (
    GROUP_PERMISSIONS_IS_CC_PAIR_AGNOSTIC,
)
from sambaai.background.celery.apps.app_base import task_logger
from sambaai.background.celery.celery_redis import celery_find_task
from sambaai.background.celery.celery_redis import celery_get_unacked_task_ids
from sambaai.background.error_logging import emit_background_error
from sambaai.configs.app_configs import JOB_TIMEOUT
from sambaai.configs.constants import CELERY_EXTERNAL_GROUP_SYNC_LOCK_TIMEOUT
from sambaai.configs.constants import CELERY_GENERIC_BEAT_LOCK_TIMEOUT
from sambaai.configs.constants import CELERY_TASK_WAIT_FOR_FENCE_TIMEOUT
from sambaai.configs.constants import SambaAICeleryPriority
from sambaai.configs.constants import SambaAICeleryQueues
from sambaai.configs.constants import SambaAICeleryTask
from sambaai.configs.constants import SambaAIRedisConstants
from sambaai.configs.constants import SambaAIRedisLocks
from sambaai.configs.constants import SambaAIRedisSignals
from sambaai.connectors.exceptions import ConnectorValidationError
from sambaai.db.connector_credential_pair import get_connector_credential_pair_from_id
from sambaai.db.engine import get_session_with_current_tenant
from sambaai.db.enums import AccessType
from sambaai.db.enums import ConnectorCredentialPairStatus
from sambaai.db.enums import SyncStatus
from sambaai.db.enums import SyncType
from sambaai.db.models import ConnectorCredentialPair
from sambaai.db.sync_record import insert_sync_record
from sambaai.db.sync_record import update_sync_record_status
from sambaai.redis.redis_connector import RedisConnector
from sambaai.redis.redis_connector_ext_group_sync import RedisConnectorExternalGroupSync
from sambaai.redis.redis_connector_ext_group_sync import (
    RedisConnectorExternalGroupSyncPayload,
)
from sambaai.redis.redis_pool import get_redis_client
from sambaai.redis.redis_pool import get_redis_replica_client
from sambaai.server.utils import make_short_id
from sambaai.utils.logger import format_error_for_logging
from sambaai.utils.logger import setup_logger

logger = setup_logger()


EXTERNAL_GROUPS_UPDATE_MAX_RETRIES = 3


# 5 seconds more than RetryDocumentIndex STOP_AFTER+MAX_WAIT
LIGHT_SOFT_TIME_LIMIT = 105
LIGHT_TIME_LIMIT = LIGHT_SOFT_TIME_LIMIT + 15


def _is_external_group_sync_due(cc_pair: ConnectorCredentialPair) -> bool:
    """Returns boolean indicating if external group sync is due."""

    if cc_pair.access_type != AccessType.SYNC:
        task_logger.error(
            f"Recieved non-sync CC Pair {cc_pair.id} for external "
            f"group sync. Actual access type: {cc_pair.access_type}"
        )
        return False

    if cc_pair.status == ConnectorCredentialPairStatus.DELETING:
        task_logger.debug(
            f"Skipping group sync for CC Pair {cc_pair.id} - "
            f"CC Pair is being deleted"
        )
        return False

    # If there is not group sync function for the connector, we don't run the sync
    # This is fine because all sources dont necessarily have a concept of groups
    if not GROUP_PERMISSIONS_FUNC_MAP.get(cc_pair.connector.source):
        task_logger.debug(
            f"Skipping group sync for CC Pair {cc_pair.id} - "
            f"no group sync function for {cc_pair.connector.source}"
        )
        return False

    # If the last sync is None, it has never been run so we run the sync
    last_ext_group_sync = cc_pair.last_time_external_group_sync
    if last_ext_group_sync is None:
        return True

    source_sync_period = EXTERNAL_GROUP_SYNC_PERIODS.get(cc_pair.connector.source)

    # If EXTERNAL_GROUP_SYNC_PERIODS is None, we always run the sync.
    if not source_sync_period:
        return True

    # If the last sync is greater than the full fetch period, we run the sync
    next_sync = last_ext_group_sync + timedelta(seconds=source_sync_period)
    if datetime.now(timezone.utc) >= next_sync:
        return True

    return False


@shared_task(
    name=SambaAICeleryTask.CHECK_FOR_EXTERNAL_GROUP_SYNC,
    ignore_result=True,
    soft_time_limit=JOB_TIMEOUT,
    bind=True,
)
def check_for_external_group_sync(self: Task, *, tenant_id: str) -> bool | None:
    # we need to use celery's redis client to access its redis data
    # (which lives on a different db number)
    r = get_redis_client()
    r_replica = get_redis_replica_client()
    r_celery: Redis = self.app.broker_connection().channel().client  # type: ignore

    lock_beat: RedisLock = r.lock(
        SambaAIRedisLocks.CHECK_CONNECTOR_EXTERNAL_GROUP_SYNC_BEAT_LOCK,
        timeout=CELERY_GENERIC_BEAT_LOCK_TIMEOUT,
    )

    # these tasks should never overlap
    if not lock_beat.acquire(blocking=False):
        task_logger.warning(
            f"Failed to acquire beat lock for external group sync: {tenant_id}"
        )
        return None

    try:
        cc_pair_ids_to_sync: list[int] = []
        with get_session_with_current_tenant() as db_session:
            cc_pairs = get_all_auto_sync_cc_pairs(db_session)

            # We only want to sync one cc_pair per source type in
            # GROUP_PERMISSIONS_IS_CC_PAIR_AGNOSTIC
            for source in GROUP_PERMISSIONS_IS_CC_PAIR_AGNOSTIC:
                # These are ordered by cc_pair id so the first one is the one we want
                cc_pairs_to_dedupe = get_cc_pairs_by_source(
                    db_session,
                    source,
                    access_type=AccessType.SYNC,
                    status=ConnectorCredentialPairStatus.ACTIVE,
                )
                # We only want to sync one cc_pair per source type
                # in GROUP_PERMISSIONS_IS_CC_PAIR_AGNOSTIC so we dedupe here
                for cc_pair_to_remove in cc_pairs_to_dedupe[1:]:
                    cc_pairs = [
                        cc_pair
                        for cc_pair in cc_pairs
                        if cc_pair.id != cc_pair_to_remove.id
                    ]

            for cc_pair in cc_pairs:
                if _is_external_group_sync_due(cc_pair):
                    cc_pair_ids_to_sync.append(cc_pair.id)

        lock_beat.reacquire()
        for cc_pair_id in cc_pair_ids_to_sync:
            payload_id = try_creating_external_group_sync_task(
                self.app, cc_pair_id, r, tenant_id
            )
            if not payload_id:
                continue

            task_logger.info(
                f"External group sync queued: cc_pair={cc_pair_id} id={payload_id}"
            )

        # we want to run this less frequently than the overall task
        lock_beat.reacquire()
        if not r.exists(SambaAIRedisSignals.BLOCK_VALIDATE_EXTERNAL_GROUP_SYNC_FENCES):
            # clear fences that don't have associated celery tasks in progress
            # tasks can be in the queue in redis, in reserved tasks (prefetched by the worker),
            # or be currently executing
            try:
                validate_external_group_sync_fences(
                    tenant_id, self.app, r, r_replica, r_celery, lock_beat
                )
            except Exception:
                task_logger.exception(
                    "Exception while validating external group sync fences"
                )

            r.set(SambaAIRedisSignals.BLOCK_VALIDATE_EXTERNAL_GROUP_SYNC_FENCES, 1, ex=300)
    except SoftTimeLimitExceeded:
        task_logger.info(
            "Soft time limit exceeded, task is being terminated gracefully."
        )
    except Exception as e:
        error_msg = format_error_for_logging(e)
        task_logger.warning(
            f"Unexpected check_for_external_group_sync exception: tenant={tenant_id} {error_msg}"
        )
        task_logger.exception(f"Unexpected exception: tenant={tenant_id}")
    finally:
        if lock_beat.owned():
            lock_beat.release()

    task_logger.info(f"check_for_external_group_sync finished: tenant={tenant_id}")
    return True


def try_creating_external_group_sync_task(
    app: Celery,
    cc_pair_id: int,
    r: Redis,
    tenant_id: str,
) -> str | None:
    """Returns an int if syncing is needed. The int represents the number of sync tasks generated.
    Returns None if no syncing is required."""
    payload_id: str | None = None

    redis_connector = RedisConnector(tenant_id, cc_pair_id)

    try:
        # Dont kick off a new sync if the previous one is still running
        if redis_connector.external_group_sync.fenced:
            logger.warning(
                f"Skipping external group sync for CC Pair {cc_pair_id} - already running."
            )
            return None

        redis_connector.external_group_sync.generator_clear()
        redis_connector.external_group_sync.taskset_clear()

        # create before setting fence to avoid race condition where the monitoring
        # task updates the sync record before it is created
        try:
            with get_session_with_current_tenant() as db_session:
                insert_sync_record(
                    db_session=db_session,
                    entity_id=cc_pair_id,
                    sync_type=SyncType.EXTERNAL_GROUP,
                )
        except Exception:
            task_logger.exception("insert_sync_record exceptioned.")

        # Signal active before creating fence
        redis_connector.external_group_sync.set_active()

        payload = RedisConnectorExternalGroupSyncPayload(
            id=make_short_id(),
            submitted=datetime.now(timezone.utc),
            started=None,
            celery_task_id=None,
        )
        redis_connector.external_group_sync.set_fence(payload)

        custom_task_id = f"{redis_connector.external_group_sync.taskset_key}_{uuid4()}"

        result = app.send_task(
            SambaAICeleryTask.CONNECTOR_EXTERNAL_GROUP_SYNC_GENERATOR_TASK,
            kwargs=dict(
                cc_pair_id=cc_pair_id,
                tenant_id=tenant_id,
            ),
            queue=SambaAICeleryQueues.CONNECTOR_EXTERNAL_GROUP_SYNC,
            task_id=custom_task_id,
            priority=SambaAICeleryPriority.MEDIUM,
        )

        payload.celery_task_id = result.id
        redis_connector.external_group_sync.set_fence(payload)

        payload_id = payload.id
    except Exception as e:
        error_msg = format_error_for_logging(e)
        task_logger.warning(
            f"Unexpected try_creating_external_group_sync_task exception: cc_pair={cc_pair_id} {error_msg}"
        )
        task_logger.exception(
            f"Unexpected exception while trying to create external group sync task: cc_pair={cc_pair_id}"
        )
        return None

    task_logger.info(
        f"try_creating_external_group_sync_task finished: cc_pair={cc_pair_id} payload_id={payload_id}"
    )
    return payload_id


@shared_task(
    name=SambaAICeleryTask.CONNECTOR_EXTERNAL_GROUP_SYNC_GENERATOR_TASK,
    acks_late=False,
    soft_time_limit=JOB_TIMEOUT,
    track_started=True,
    trail=False,
    bind=True,
)
def connector_external_group_sync_generator_task(
    self: Task,
    cc_pair_id: int,
    tenant_id: str,
) -> None:
    """
    External group sync task for a given connector credential pair
    This task assumes that the task has already been properly fenced
    """

    redis_connector = RedisConnector(tenant_id, cc_pair_id)

    r = get_redis_client()

    # this wait is needed to avoid a race condition where
    # the primary worker sends the task and it is immediately executed
    # before the primary worker can finalize the fence
    start = time.monotonic()
    while True:
        if time.monotonic() - start > CELERY_TASK_WAIT_FOR_FENCE_TIMEOUT:
            msg = (
                f"connector_external_group_sync_generator_task - timed out waiting for fence to be ready: "
                f"fence={redis_connector.external_group_sync.fence_key}"
            )
            emit_background_error(msg, cc_pair_id=cc_pair_id)
            raise ValueError(msg)

        if not redis_connector.external_group_sync.fenced:  # The fence must exist
            msg = (
                f"connector_external_group_sync_generator_task - fence not found: "
                f"fence={redis_connector.external_group_sync.fence_key}"
            )
            emit_background_error(msg, cc_pair_id=cc_pair_id)
            raise ValueError(msg)

        payload = redis_connector.external_group_sync.payload  # The payload must exist
        if not payload:
            msg = "connector_external_group_sync_generator_task: payload invalid or not found"
            emit_background_error(msg, cc_pair_id=cc_pair_id)
            raise ValueError(msg)

        if payload.celery_task_id is None:
            logger.info(
                f"connector_external_group_sync_generator_task - Waiting for fence: "
                f"fence={redis_connector.external_group_sync.fence_key}"
            )
            time.sleep(1)
            continue

        logger.info(
            f"connector_external_group_sync_generator_task - Fence found, continuing...: "
            f"fence={redis_connector.external_group_sync.fence_key} "
            f"payload_id={payload.id}"
        )
        break

    lock: RedisLock = r.lock(
        SambaAIRedisLocks.CONNECTOR_EXTERNAL_GROUP_SYNC_LOCK_PREFIX
        + f"_{redis_connector.id}",
        timeout=CELERY_EXTERNAL_GROUP_SYNC_LOCK_TIMEOUT,
    )

    acquired = lock.acquire(blocking=False)
    if not acquired:
        msg = f"External group sync task already running, exiting...: cc_pair={cc_pair_id}"
        emit_background_error(msg, cc_pair_id=cc_pair_id)
        task_logger.error(msg)
        return None

    try:
        payload.started = datetime.now(timezone.utc)
        redis_connector.external_group_sync.set_fence(payload)

        with get_session_with_current_tenant() as db_session:
            cc_pair = get_connector_credential_pair_from_id(
                db_session=db_session,
                cc_pair_id=cc_pair_id,
                eager_load_credential=True,
            )
            if cc_pair is None:
                raise ValueError(
                    f"No connector credential pair found for id: {cc_pair_id}"
                )

            source_type = cc_pair.connector.source

            ext_group_sync_func = GROUP_PERMISSIONS_FUNC_MAP.get(source_type)
            if ext_group_sync_func is None:
                msg = f"No external group sync func found for {source_type} for cc_pair: {cc_pair_id}"
                emit_background_error(msg, cc_pair_id=cc_pair_id)
                raise ValueError(msg)

            logger.info(
                f"Syncing external groups for {source_type} for cc_pair: {cc_pair_id}"
            )
            external_user_groups: list[ExternalUserGroup] = []
            try:
                external_user_groups = ext_group_sync_func(tenant_id, cc_pair)
            except ConnectorValidationError as e:
                # TODO: add some notification to the admins here
                logger.exception(
                    f"Error syncing external groups for {source_type} for cc_pair: {cc_pair_id} {e}"
                )
                raise e

            logger.info(
                f"Syncing {len(external_user_groups)} external user groups for {source_type}"
            )
            logger.debug(f"New external user groups: {external_user_groups}")

            replace_user__ext_group_for_cc_pair(
                db_session=db_session,
                cc_pair_id=cc_pair.id,
                group_defs=external_user_groups,
                source=cc_pair.connector.source,
            )
            logger.info(
                f"Synced {len(external_user_groups)} external user groups for {source_type}"
            )

            mark_all_relevant_cc_pairs_as_external_group_synced(db_session, cc_pair)

            update_sync_record_status(
                db_session=db_session,
                entity_id=cc_pair_id,
                sync_type=SyncType.EXTERNAL_GROUP,
                sync_status=SyncStatus.SUCCESS,
            )
    except Exception as e:
        error_msg = format_error_for_logging(e)
        task_logger.warning(
            f"External group sync exceptioned: cc_pair={cc_pair_id} payload_id={payload.id} {error_msg}"
        )
        task_logger.exception(
            f"External group sync exceptioned: cc_pair={cc_pair_id} payload_id={payload.id}"
        )

        msg = f"External group sync exceptioned: cc_pair={cc_pair_id} payload_id={payload.id}"
        task_logger.exception(msg)
        emit_background_error(msg + f"\n\n{e}", cc_pair_id=cc_pair_id)

        with get_session_with_current_tenant() as db_session:
            update_sync_record_status(
                db_session=db_session,
                entity_id=cc_pair_id,
                sync_type=SyncType.EXTERNAL_GROUP,
                sync_status=SyncStatus.FAILED,
            )

        redis_connector.external_group_sync.generator_clear()
        redis_connector.external_group_sync.taskset_clear()
        raise e
    finally:
        # we always want to clear the fence after the task is done or failed so it doesn't get stuck
        redis_connector.external_group_sync.set_fence(None)
        if lock.owned():
            lock.release()

    task_logger.info(
        f"External group sync finished: cc_pair={cc_pair_id} payload_id={payload.id}"
    )


def validate_external_group_sync_fences(
    tenant_id: str,
    celery_app: Celery,
    r: Redis,
    r_replica: Redis,
    r_celery: Redis,
    lock_beat: RedisLock,
) -> None:
    reserved_tasks = celery_get_unacked_task_ids(
        SambaAICeleryQueues.CONNECTOR_EXTERNAL_GROUP_SYNC, r_celery
    )

    # validate all existing external group sync tasks
    lock_beat.reacquire()
    keys = cast(set[Any], r_replica.smembers(SambaAIRedisConstants.ACTIVE_FENCES))
    for key in keys:
        key_bytes = cast(bytes, key)
        key_str = key_bytes.decode("utf-8")
        if not key_str.startswith(RedisConnectorExternalGroupSync.FENCE_PREFIX):
            continue

        validate_external_group_sync_fence(
            tenant_id,
            key_bytes,
            reserved_tasks,
            r_celery,
        )

        lock_beat.reacquire()
    return


def validate_external_group_sync_fence(
    tenant_id: str,
    key_bytes: bytes,
    reserved_tasks: set[str],
    r_celery: Redis,
) -> None:
    """Checks for the error condition where an indexing fence is set but the associated celery tasks don't exist.
    This can happen if the indexing worker hard crashes or is terminated.
    Being in this bad state means the fence will never clear without help, so this function
    gives the help.

    How this works:
    1. This function renews the active signal with a 5 minute TTL under the following conditions
    1.2. When the task is seen in the redis queue
    1.3. When the task is seen in the reserved / prefetched list

    2. Externally, the active signal is renewed when:
    2.1. The fence is created
    2.2. The indexing watchdog checks the spawned task.

    3. The TTL allows us to get through the transitions on fence startup
    and when the task starts executing.

    More TTL clarification: it is seemingly impossible to exactly query Celery for
    whether a task is in the queue or currently executing.
    1. An unknown task id is always returned as state PENDING.
    2. Redis can be inspected for the task id, but the task id is gone between the time a worker receives the task
    and the time it actually starts on the worker.
    """
    # if the fence doesn't exist, there's nothing to do
    fence_key = key_bytes.decode("utf-8")
    cc_pair_id_str = RedisConnector.get_id_from_fence_key(fence_key)
    if cc_pair_id_str is None:
        msg = (
            f"validate_external_group_sync_fence - could not parse id from {fence_key}"
        )
        emit_background_error(msg)
        task_logger.error(msg)
        return

    cc_pair_id = int(cc_pair_id_str)

    # parse out metadata and initialize the helper class with it
    redis_connector = RedisConnector(tenant_id, int(cc_pair_id))

    # check to see if the fence/payload exists
    if not redis_connector.external_group_sync.fenced:
        return

    try:
        payload = redis_connector.external_group_sync.payload
    except ValidationError:
        msg = (
            "validate_external_group_sync_fence - "
            "Resetting fence because fence schema is out of date: "
            f"cc_pair={cc_pair_id} "
            f"fence={fence_key}"
        )
        task_logger.exception(msg)
        emit_background_error(msg, cc_pair_id=cc_pair_id)

        redis_connector.external_group_sync.reset()
        return

    if not payload:
        return

    if not payload.celery_task_id:
        return

    # OK, there's actually something for us to validate
    found = celery_find_task(
        payload.celery_task_id, SambaAICeleryQueues.CONNECTOR_EXTERNAL_GROUP_SYNC, r_celery
    )
    if found:
        # the celery task exists in the redis queue
        # redis_connector_index.set_active()
        return

    if payload.celery_task_id in reserved_tasks:
        # the celery task was prefetched and is reserved within the indexing worker
        # redis_connector_index.set_active()
        return

    # we may want to enable this check if using the active task list somehow isn't good enough
    # if redis_connector_index.generator_locked():
    #     logger.info(f"{payload.celery_task_id} is currently executing.")

    # if we get here, we didn't find any direct indication that the associated celery tasks exist,
    # but they still might be there due to gaps in our ability to check states during transitions
    # Checking the active signal safeguards us against these transition periods
    # (which has a duration that allows us to bridge those gaps)
    # if redis_connector_index.active():
    # return

    # celery tasks don't exist and the active signal has expired, possibly due to a crash. Clean it up.
    emit_background_error(
        message=(
            "validate_external_group_sync_fence - "
            "Resetting fence because no associated celery tasks were found: "
            f"cc_pair={cc_pair_id} "
            f"fence={fence_key} "
            f"payload_id={payload.id}"
        ),
        cc_pair_id=cc_pair_id,
    )

    redis_connector.external_group_sync.reset()
    return
