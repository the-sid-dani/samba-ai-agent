import copy
from datetime import timedelta
from typing import Any

from sambaai.configs.app_configs import LLM_MODEL_UPDATE_API_URL
from sambaai.configs.constants import ONYX_CLOUD_CELERY_TASK_PREFIX
from sambaai.configs.constants import SambaAICeleryPriority
from sambaai.configs.constants import SambaAICeleryQueues
from sambaai.configs.constants import SambaAICeleryTask
from shared_configs.configs import MULTI_TENANT

# choosing 15 minutes because it roughly gives us enough time to process many tasks
# we might be able to reduce this greatly if we can run a unified
# loop across all tenants rather than tasks per tenant

# we set expires because it isn't necessary to queue up these tasks
# it's only important that they run relatively regularly
BEAT_EXPIRES_DEFAULT = 15 * 60  # 15 minutes (in seconds)

# hack to slow down task dispatch in the cloud until
# we have a better implementation (backpressure, etc)
# Note that DynamicTenantScheduler can adjust the runtime value for this via Redis
CLOUD_BEAT_MULTIPLIER_DEFAULT = 8.0
CLOUD_DOC_PERMISSION_SYNC_MULTIPLIER_DEFAULT = 1.0

# tasks that run in either self-hosted on cloud
beat_task_templates: list[dict] = []

beat_task_templates.extend(
    [
        {
            "name": "check-for-indexing",
            "task": SambaAICeleryTask.CHECK_FOR_INDEXING,
            "schedule": timedelta(seconds=15),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-for-checkpoint-cleanup",
            "task": SambaAICeleryTask.CHECK_FOR_CHECKPOINT_CLEANUP,
            "schedule": timedelta(hours=1),
            "options": {
                "priority": SambaAICeleryPriority.LOW,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-for-connector-deletion",
            "task": SambaAICeleryTask.CHECK_FOR_CONNECTOR_DELETION,
            "schedule": timedelta(seconds=20),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-for-vespa-sync",
            "task": SambaAICeleryTask.CHECK_FOR_VESPA_SYNC_TASK,
            "schedule": timedelta(seconds=20),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-for-user-file-folder-sync",
            "task": SambaAICeleryTask.CHECK_FOR_USER_FILE_FOLDER_SYNC,
            "schedule": timedelta(
                days=1
            ),  # This should essentially always be triggered manually for user folder updates.
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-for-pruning",
            "task": SambaAICeleryTask.CHECK_FOR_PRUNING,
            "schedule": timedelta(seconds=20),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-for-doc-permissions-sync",
            "task": SambaAICeleryTask.CHECK_FOR_DOC_PERMISSIONS_SYNC,
            "schedule": timedelta(seconds=30),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-for-external-group-sync",
            "task": SambaAICeleryTask.CHECK_FOR_EXTERNAL_GROUP_SYNC,
            "schedule": timedelta(seconds=20),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "monitor-background-processes",
            "task": SambaAICeleryTask.MONITOR_BACKGROUND_PROCESSES,
            "schedule": timedelta(minutes=5),
            "options": {
                "priority": SambaAICeleryPriority.LOW,
                "expires": BEAT_EXPIRES_DEFAULT,
                "queue": SambaAICeleryQueues.MONITORING,
            },
        },
    ]
)

# Only add the LLM model update task if the API URL is configured
if LLM_MODEL_UPDATE_API_URL:
    beat_task_templates.append(
        {
            "name": "check-for-llm-model-update",
            "task": SambaAICeleryTask.CHECK_FOR_LLM_MODEL_UPDATE,
            "schedule": timedelta(hours=1),  # Check every hour
            "options": {
                "priority": SambaAICeleryPriority.LOW,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        }
    )


def make_cloud_generator_task(task: dict[str, Any]) -> dict[str, Any]:
    cloud_task: dict[str, Any] = {}

    # constant options for cloud beat task generators
    task_schedule: timedelta = task["schedule"]
    cloud_task["schedule"] = task_schedule
    cloud_task["options"] = {}
    cloud_task["options"]["priority"] = SambaAICeleryPriority.HIGHEST
    cloud_task["options"]["expires"] = BEAT_EXPIRES_DEFAULT

    # settings dependent on the original task
    cloud_task["name"] = f"{ONYX_CLOUD_CELERY_TASK_PREFIX}_{task['name']}"
    cloud_task["task"] = SambaAICeleryTask.CLOUD_BEAT_TASK_GENERATOR
    cloud_task["kwargs"] = {}
    cloud_task["kwargs"]["task_name"] = task["task"]

    optional_fields = ["queue", "priority", "expires"]
    for field in optional_fields:
        if field in task["options"]:
            cloud_task["kwargs"][field] = task["options"][field]

    return cloud_task


# tasks that only run in the cloud and are system wide
# the name attribute must start with ONYX_CLOUD_CELERY_TASK_PREFIX = "cloud" to be seen
# by the DynamicTenantScheduler as system wide task and not a per tenant task
beat_cloud_tasks: list[dict] = [
    # cloud specific tasks
    {
        "name": f"{ONYX_CLOUD_CELERY_TASK_PREFIX}_monitor-alembic",
        "task": SambaAICeleryTask.CLOUD_MONITOR_ALEMBIC,
        "schedule": timedelta(hours=1),
        "options": {
            "queue": SambaAICeleryQueues.MONITORING,
            "priority": SambaAICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": f"{ONYX_CLOUD_CELERY_TASK_PREFIX}_monitor-celery-queues",
        "task": SambaAICeleryTask.CLOUD_MONITOR_CELERY_QUEUES,
        "schedule": timedelta(seconds=30),
        "options": {
            "queue": SambaAICeleryQueues.MONITORING,
            "priority": SambaAICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": f"{ONYX_CLOUD_CELERY_TASK_PREFIX}_check-available-tenants",
        "task": SambaAICeleryTask.CLOUD_CHECK_AVAILABLE_TENANTS,
        "schedule": timedelta(minutes=10),
        "options": {
            "queue": SambaAICeleryQueues.MONITORING,
            "priority": SambaAICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": f"{ONYX_CLOUD_CELERY_TASK_PREFIX}_monitor-celery-pidbox",
        "task": SambaAICeleryTask.CLOUD_MONITOR_CELERY_PIDBOX,
        "schedule": timedelta(hours=4),
        "options": {
            "queue": SambaAICeleryQueues.MONITORING,
            "priority": SambaAICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
]

# tasks that only run self hosted
tasks_to_schedule: list[dict] = []
if not MULTI_TENANT:
    tasks_to_schedule.extend(
        [
            {
                "name": "monitor-celery-queues",
                "task": SambaAICeleryTask.MONITOR_CELERY_QUEUES,
                "schedule": timedelta(seconds=10),
                "options": {
                    "priority": SambaAICeleryPriority.MEDIUM,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "queue": SambaAICeleryQueues.MONITORING,
                },
            },
            {
                "name": "monitor-process-memory",
                "task": SambaAICeleryTask.MONITOR_PROCESS_MEMORY,
                "schedule": timedelta(minutes=5),
                "options": {
                    "priority": SambaAICeleryPriority.LOW,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "queue": SambaAICeleryQueues.MONITORING,
                },
            },
            {
                "name": "celery-beat-heartbeat",
                "task": SambaAICeleryTask.CELERY_BEAT_HEARTBEAT,
                "schedule": timedelta(minutes=1),
                "options": {
                    "priority": SambaAICeleryPriority.HIGHEST,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "queue": SambaAICeleryQueues.PRIMARY,
                },
            },
        ]
    )

    tasks_to_schedule.extend(beat_task_templates)


def generate_cloud_tasks(
    beat_tasks: list[dict], beat_templates: list[dict], beat_multiplier: float
) -> list[dict[str, Any]]:
    """
    beat_tasks: system wide tasks that can be sent as is
    beat_templates: task templates that will be transformed into per tenant tasks via
    the cloud_beat_task_generator
    beat_multiplier: a multiplier that can be applied on top of the task schedule
    to speed up or slow down the task generation rate. useful in production.

    Returns a list of cloud tasks, which consists of incoming tasks + tasks generated
    from incoming templates.
    """

    if beat_multiplier <= 0:
        raise ValueError("beat_multiplier must be positive!")

    cloud_tasks: list[dict] = []

    # generate our tenant aware cloud tasks from the templates
    for beat_template in beat_templates:
        cloud_task = make_cloud_generator_task(beat_template)
        cloud_tasks.append(cloud_task)

    # factor in the cloud multiplier for the above
    for cloud_task in cloud_tasks:
        cloud_task["schedule"] = cloud_task["schedule"] * beat_multiplier

    # add the fixed cloud/system beat tasks. No multiplier for these.
    cloud_tasks.extend(copy.deepcopy(beat_tasks))
    return cloud_tasks


def get_cloud_tasks_to_schedule(beat_multiplier: float) -> list[dict[str, Any]]:
    return generate_cloud_tasks(beat_cloud_tasks, beat_task_templates, beat_multiplier)


def get_tasks_to_schedule() -> list[dict[str, Any]]:
    return tasks_to_schedule
