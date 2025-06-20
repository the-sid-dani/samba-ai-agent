from datetime import timedelta
from typing import Any

from ee.sambaai.configs.app_configs import CHECK_TTL_MANAGEMENT_TASK_FREQUENCY_IN_HOURS
from sambaai.background.celery.tasks.beat_schedule import (
    beat_cloud_tasks as base_beat_system_tasks,
)
from sambaai.background.celery.tasks.beat_schedule import BEAT_EXPIRES_DEFAULT
from sambaai.background.celery.tasks.beat_schedule import (
    beat_task_templates as base_beat_task_templates,
)
from sambaai.background.celery.tasks.beat_schedule import generate_cloud_tasks
from sambaai.background.celery.tasks.beat_schedule import (
    get_tasks_to_schedule as base_get_tasks_to_schedule,
)
from sambaai.configs.constants import SambaAICeleryPriority
from sambaai.configs.constants import SambaAICeleryQueues
from sambaai.configs.constants import SambaAICeleryTask
from shared_configs.configs import MULTI_TENANT

ee_beat_system_tasks: list[dict] = []

ee_beat_task_templates: list[dict] = []
ee_beat_task_templates.extend(
    [
        {
            "name": "autogenerate-usage-report",
            "task": SambaAICeleryTask.AUTOGENERATE_USAGE_REPORT_TASK,
            "schedule": timedelta(days=30),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-ttl-management",
            "task": SambaAICeleryTask.CHECK_TTL_MANAGEMENT_TASK,
            "schedule": timedelta(hours=CHECK_TTL_MANAGEMENT_TASK_FREQUENCY_IN_HOURS),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "export-query-history-cleanup-task",
            "task": SambaAICeleryTask.EXPORT_QUERY_HISTORY_CLEANUP_TASK,
            "schedule": timedelta(hours=1),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
                "queue": SambaAICeleryQueues.CSV_GENERATION,
            },
        },
    ]
)

ee_tasks_to_schedule: list[dict] = []

if not MULTI_TENANT:
    ee_tasks_to_schedule = [
        {
            "name": "autogenerate-usage-report",
            "task": SambaAICeleryTask.AUTOGENERATE_USAGE_REPORT_TASK,
            "schedule": timedelta(days=30),  # TODO: change this to config flag
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "check-ttl-management",
            "task": SambaAICeleryTask.CHECK_TTL_MANAGEMENT_TASK,
            "schedule": timedelta(hours=CHECK_TTL_MANAGEMENT_TASK_FREQUENCY_IN_HOURS),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        },
        {
            "name": "export-query-history-cleanup-task",
            "task": SambaAICeleryTask.EXPORT_QUERY_HISTORY_CLEANUP_TASK,
            "schedule": timedelta(hours=1),
            "options": {
                "priority": SambaAICeleryPriority.MEDIUM,
                "expires": BEAT_EXPIRES_DEFAULT,
                "queue": SambaAICeleryQueues.CSV_GENERATION,
            },
        },
    ]


def get_cloud_tasks_to_schedule(beat_multiplier: float) -> list[dict[str, Any]]:
    beat_system_tasks = ee_beat_system_tasks + base_beat_system_tasks
    beat_task_templates = ee_beat_task_templates + base_beat_task_templates
    cloud_tasks = generate_cloud_tasks(
        beat_system_tasks, beat_task_templates, beat_multiplier
    )
    return cloud_tasks


def get_tasks_to_schedule() -> list[dict[str, Any]]:
    return ee_tasks_to_schedule + base_get_tasks_to_schedule()
