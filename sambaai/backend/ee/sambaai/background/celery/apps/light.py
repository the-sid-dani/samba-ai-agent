from sambaai.background.celery.apps.light import celery_app

celery_app.autodiscover_tasks(
    [
        "ee.sambaai.background.celery.tasks.doc_permission_syncing",
        "ee.sambaai.background.celery.tasks.external_group_syncing",
    ]
)
