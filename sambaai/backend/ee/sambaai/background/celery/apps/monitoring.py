from sambaai.background.celery.apps.monitoring import celery_app

celery_app.autodiscover_tasks(
    [
        "ee.sambaai.background.celery.tasks.tenant_provisioning",
    ]
)
