from ee.sambaai.db.external_perm import ExternalUserGroup
from ee.sambaai.external_permissions.confluence.constants import ALL_CONF_EMAILS_GROUP_NAME
from sambaai.background.error_logging import emit_background_error
from sambaai.connectors.confluence.sambaai_confluence import (
    get_user_email_from_username__server,
)
from sambaai.connectors.confluence.sambaai_confluence import SambaAIConfluence
from sambaai.connectors.credentials_provider import SambaAIDBCredentialsProvider
from sambaai.db.models import ConnectorCredentialPair
from sambaai.utils.logger import setup_logger

logger = setup_logger()


def _build_group_member_email_map(
    confluence_client: SambaAIConfluence, cc_pair_id: int
) -> dict[str, set[str]]:
    group_member_emails: dict[str, set[str]] = {}
    for user in confluence_client.paginated_cql_user_retrieval():
        logger.debug(f"Processing groups for user: {user}")

        email = user.email
        if not email:
            # This field is only present in Confluence Server
            user_name = user.username
            # If it is present, try to get the email using a Server-specific method
            if user_name:
                email = get_user_email_from_username__server(
                    confluence_client=confluence_client,
                    user_name=user_name,
                )

        if not email:
            # If we still don't have an email, skip this user
            msg = f"user result missing email field: {user}"
            if user.type == "app":
                logger.warning(msg)
            else:
                emit_background_error(msg, cc_pair_id=cc_pair_id)
                logger.error(msg)
            continue

        all_users_groups: set[str] = set()
        for group in confluence_client.paginated_groups_by_user_retrieval(user.user_id):
            # group name uniqueness is enforced by Confluence, so we can use it as a group ID
            group_id = group["name"]
            group_member_emails.setdefault(group_id, set()).add(email)
            all_users_groups.add(group_id)

        if not all_users_groups:
            msg = f"No groups found for user with email: {email}"
            emit_background_error(msg, cc_pair_id=cc_pair_id)
            logger.error(msg)
        else:
            logger.debug(f"Found groups {all_users_groups} for user with email {email}")

    if not group_member_emails:
        msg = "No groups found for any users."
        emit_background_error(msg, cc_pair_id=cc_pair_id)
        logger.error(msg)

    return group_member_emails


def confluence_group_sync(
    tenant_id: str,
    cc_pair: ConnectorCredentialPair,
) -> list[ExternalUserGroup]:
    provider = SambaAIDBCredentialsProvider(tenant_id, "confluence", cc_pair.credential_id)
    is_cloud = cc_pair.connector.connector_specific_config.get("is_cloud", False)
    wiki_base: str = cc_pair.connector.connector_specific_config["wiki_base"]
    url = wiki_base.rstrip("/")

    probe_kwargs = {
        "max_backoff_retries": 6,
        "max_backoff_seconds": 10,
    }

    final_kwargs = {
        "max_backoff_retries": 10,
        "max_backoff_seconds": 60,
    }

    confluence_client = SambaAIConfluence(is_cloud, url, provider)
    confluence_client._probe_connection(**probe_kwargs)
    confluence_client._initialize_connection(**final_kwargs)

    group_member_email_map = _build_group_member_email_map(
        confluence_client=confluence_client,
        cc_pair_id=cc_pair.id,
    )
    sambaai_groups: list[ExternalUserGroup] = []
    all_found_emails = set()
    for group_id, group_member_emails in group_member_email_map.items():
        sambaai_groups.append(
            ExternalUserGroup(
                id=group_id,
                user_emails=list(group_member_emails),
            )
        )
        all_found_emails.update(group_member_emails)

    # This is so that when we find a public confleunce server page, we can
    # give access to all users only in if they have an email in Confluence
    if cc_pair.connector.connector_specific_config.get("is_cloud", False):
        all_found_group = ExternalUserGroup(
            id=ALL_CONF_EMAILS_GROUP_NAME,
            user_emails=list(all_found_emails),
        )
        sambaai_groups.append(all_found_group)

    return sambaai_groups
