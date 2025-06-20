import pytest

from sambaai.auth.email_utils import build_user_email_invite
from sambaai.auth.email_utils import send_email
from sambaai.configs.constants import AuthType
from sambaai.configs.constants import ONYX_DEFAULT_APPLICATION_NAME
from sambaai.db.engine import SqlEngine
from sambaai.server.runtime.sambaai_runtime import SambaAIRuntime


@pytest.mark.skip(
    reason="This sends real emails, so only run when you really want to test this!"
)
def test_send_user_email_invite() -> None:
    SqlEngine.init_engine(pool_size=20, max_overflow=5)

    application_name = ONYX_DEFAULT_APPLICATION_NAME

    sambaai_file = SambaAIRuntime.get_emailable_logo()

    subject = f"Invitation to Join {application_name} Organization"

    FROM_EMAIL = "noreply@sambaai.app"
    TO_EMAIL = "support@sambaai.app"
    text_content, html_content = build_user_email_invite(
        FROM_EMAIL, TO_EMAIL, ONYX_DEFAULT_APPLICATION_NAME, AuthType.CLOUD
    )

    send_email(
        TO_EMAIL,
        subject,
        html_content,
        text_content,
        mail_from=FROM_EMAIL,
        inline_png=("logo.png", sambaai_file.data),
    )
