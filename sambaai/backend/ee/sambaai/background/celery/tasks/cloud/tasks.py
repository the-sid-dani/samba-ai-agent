import time

from celery import shared_task
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from redis.lock import Lock as RedisLock

from ee.sambaai.server.tenants.product_gating import get_gated_tenants
from sambaai.background.celery.apps.app_base import task_logger
from sambaai.background.celery.tasks.beat_schedule import BEAT_EXPIRES_DEFAULT
from sambaai.configs.constants import CELERY_GENERIC_BEAT_LOCK_TIMEOUT
from sambaai.configs.constants import ONYX_CLOUD_TENANT_ID
from sambaai.configs.constants import SambaAICeleryPriority
from sambaai.configs.constants import SambaAICeleryTask
from sambaai.configs.constants import SambaAIRedisLocks
from sambaai.db.engine import get_all_tenant_ids
from sambaai.redis.redis_pool import get_redis_client
from sambaai.redis.redis_pool import redis_lock_dump
from shared_configs.configs import IGNORED_SYNCING_TENANT_LIST


@shared_task(
    name=SambaAICeleryTask.CLOUD_BEAT_TASK_GENERATOR,
    ignore_result=True,
    trail=False,
    bind=True,
)
def cloud_beat_task_generator(
    self: Task,
    task_name: str,
    queue: str = SambaAICeleryTask.DEFAULT,
    priority: int = SambaAICeleryPriority.MEDIUM,
    expires: int = BEAT_EXPIRES_DEFAULT,
) -> bool | None:
    """a lightweight task used to kick off individual beat tasks per tenant."""
    time_start = time.monotonic()

    redis_client = get_redis_client(tenant_id=ONYX_CLOUD_TENANT_ID)

    lock_beat: RedisLock = redis_client.lock(
        f"{SambaAIRedisLocks.CLOUD_BEAT_TASK_GENERATOR_LOCK}:{task_name}",
        timeout=CELERY_GENERIC_BEAT_LOCK_TIMEOUT,
    )

    # these tasks should never overlap
    if not lock_beat.acquire(blocking=False):
        return None

    last_lock_time = time.monotonic()
    tenant_ids: list[str] = []
    num_processed_tenants = 0

    try:
        tenant_ids = get_all_tenant_ids()
        gated_tenants = get_gated_tenants()
        for tenant_id in tenant_ids:
            if tenant_id in gated_tenants:
                continue

            current_time = time.monotonic()
            if current_time - last_lock_time >= (CELERY_GENERIC_BEAT_LOCK_TIMEOUT / 4):
                lock_beat.reacquire()
                last_lock_time = current_time

            # needed in the cloud
            if IGNORED_SYNCING_TENANT_LIST and tenant_id in IGNORED_SYNCING_TENANT_LIST:
                continue

            self.app.send_task(
                task_name,
                kwargs=dict(
                    tenant_id=tenant_id,
                ),
                queue=queue,
                priority=priority,
                expires=expires,
                ignore_result=True,
            )

            num_processed_tenants += 1
    except SoftTimeLimitExceeded:
        task_logger.info(
            "Soft time limit exceeded, task is being terminated gracefully."
        )
    except Exception:
        task_logger.exception("Unexpected exception during cloud_beat_task_generator")
    finally:
        if not lock_beat.owned():
            task_logger.error(
                "cloud_beat_task_generator - Lock not owned on completion"
            )
            redis_lock_dump(lock_beat, redis_client)
        else:
            lock_beat.release()

    time_elapsed = time.monotonic() - time_start
    task_logger.info(
        f"cloud_beat_task_generator finished: "
        f"task={task_name} "
        f"num_processed_tenants={num_processed_tenants} "
        f"num_tenants={len(tenant_ids)} "
        f"elapsed={time_elapsed:.2f}"
    )
    return True
