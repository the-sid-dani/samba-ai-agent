from typing import cast

from ee.sambaai.configs.app_configs import GATED_TENANTS_KEY
from sambaai.configs.constants import ONYX_CLOUD_TENANT_ID
from sambaai.redis.redis_pool import get_redis_client
from sambaai.redis.redis_pool import get_redis_replica_client
from sambaai.server.settings.models import ApplicationStatus
from sambaai.server.settings.store import load_settings
from sambaai.server.settings.store import store_settings
from sambaai.utils.logger import setup_logger
from shared_configs.contextvars import CURRENT_TENANT_ID_CONTEXTVAR

logger = setup_logger()


def update_tenant_gating(tenant_id: str, status: ApplicationStatus) -> None:
    redis_client = get_redis_client(tenant_id=ONYX_CLOUD_TENANT_ID)

    # Store the full status
    status_key = f"tenant:{tenant_id}:status"
    redis_client.set(status_key, status.value)

    # Maintain the GATED_ACCESS set
    if status == ApplicationStatus.GATED_ACCESS:
        redis_client.sadd(GATED_TENANTS_KEY, tenant_id)
    else:
        redis_client.srem(GATED_TENANTS_KEY, tenant_id)


def store_product_gating(tenant_id: str, application_status: ApplicationStatus) -> None:
    try:
        token = CURRENT_TENANT_ID_CONTEXTVAR.set(tenant_id)

        settings = load_settings()
        settings.application_status = application_status
        store_settings(settings)

        # Store gated tenant information in Redis
        update_tenant_gating(tenant_id, application_status)

        if token is not None:
            CURRENT_TENANT_ID_CONTEXTVAR.reset(token)

    except Exception:
        logger.exception("Failed to gate product")
        raise


def get_gated_tenants() -> set[str]:
    redis_client = get_redis_replica_client(tenant_id=ONYX_CLOUD_TENANT_ID)
    gated_tenants_bytes = cast(set[bytes], redis_client.smembers(GATED_TENANTS_KEY))
    return {tenant_id.decode("utf-8") for tenant_id in gated_tenants_bytes}
