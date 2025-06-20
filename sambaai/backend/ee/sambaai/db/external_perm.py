from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from sambaai.access.utils import build_ext_group_name_for_sambaai
from sambaai.configs.constants import DocumentSource
from sambaai.db.models import PublicExternalUserGroup
from sambaai.db.models import User
from sambaai.db.models import User__ExternalUserGroupId
from sambaai.db.users import batch_add_ext_perm_user_if_not_exists
from sambaai.db.users import get_user_by_email
from sambaai.utils.logger import setup_logger

logger = setup_logger()


class ExternalUserGroup(BaseModel):
    id: str
    user_emails: list[str]
    # `True` for cases like a Folder in Google Drive that give domain-wide
    # or "Anyone with link" access to all files in the folder.
    # if this is set, `user_emails` don't really matter.
    # When this is `True`, this `ExternalUserGroup` object doesn't really represent
    # an actual "group" in the source.
    gives_anyone_access: bool = False


def delete_user__ext_group_for_user__no_commit(
    db_session: Session,
    user_id: UUID,
) -> None:
    db_session.execute(
        delete(User__ExternalUserGroupId).where(
            User__ExternalUserGroupId.user_id == user_id
        )
    )


def delete_user__ext_group_for_cc_pair__no_commit(
    db_session: Session,
    cc_pair_id: int,
) -> None:
    db_session.execute(
        delete(User__ExternalUserGroupId).where(
            User__ExternalUserGroupId.cc_pair_id == cc_pair_id
        )
    )


def delete_public_external_group_for_cc_pair__no_commit(
    db_session: Session,
    cc_pair_id: int,
) -> None:
    db_session.execute(
        delete(PublicExternalUserGroup).where(
            PublicExternalUserGroup.cc_pair_id == cc_pair_id
        )
    )


def replace_user__ext_group_for_cc_pair(
    db_session: Session,
    cc_pair_id: int,
    group_defs: list[ExternalUserGroup],
    source: DocumentSource,
) -> None:
    """
    This function clears all existing external user group relations for a given cc_pair_id
    and replaces them with the new group definitions and commits the changes.
    """

    # collect all emails from all groups to batch add all users at once for efficiency
    all_group_member_emails = set()
    for external_group in group_defs:
        for user_email in external_group.user_emails:
            all_group_member_emails.add(user_email)

    # batch add users if they don't exist and get their ids
    all_group_members: list[User] = batch_add_ext_perm_user_if_not_exists(
        db_session=db_session,
        # NOTE: this function handles case sensitivity for emails
        emails=list(all_group_member_emails),
    )

    delete_user__ext_group_for_cc_pair__no_commit(
        db_session=db_session,
        cc_pair_id=cc_pair_id,
    )
    delete_public_external_group_for_cc_pair__no_commit(
        db_session=db_session,
        cc_pair_id=cc_pair_id,
    )

    # map emails to ids
    email_id_map = {user.email: user.id for user in all_group_members}

    # use these ids to create new external user group relations relating group_id to user_ids
    new_external_permissions: list[User__ExternalUserGroupId] = []
    new_public_external_groups: list[PublicExternalUserGroup] = []
    for external_group in group_defs:
        external_group_id = build_ext_group_name_for_sambaai(
            ext_group_name=external_group.id,
            source=source,
        )
        for user_email in external_group.user_emails:
            user_id = email_id_map.get(user_email.lower())
            if user_id is None:
                logger.warning(
                    f"User in group {external_group.id}"
                    f" with email {user_email} not found"
                )
                continue
            new_external_permissions.append(
                User__ExternalUserGroupId(
                    user_id=user_id,
                    external_user_group_id=external_group_id,
                    cc_pair_id=cc_pair_id,
                )
            )

        if external_group.gives_anyone_access:
            new_public_external_groups.append(
                PublicExternalUserGroup(
                    external_user_group_id=external_group_id,
                    cc_pair_id=cc_pair_id,
                )
            )

    db_session.add_all(new_external_permissions)
    db_session.add_all(new_public_external_groups)
    db_session.commit()


def fetch_external_groups_for_user(
    db_session: Session,
    user_id: UUID,
) -> Sequence[User__ExternalUserGroupId]:
    return db_session.scalars(
        select(User__ExternalUserGroupId).where(
            User__ExternalUserGroupId.user_id == user_id
        )
    ).all()


def fetch_external_groups_for_user_email_and_group_ids(
    db_session: Session,
    user_email: str,
    group_ids: list[str],
) -> list[User__ExternalUserGroupId]:
    user = get_user_by_email(db_session=db_session, email=user_email)
    if user is None:
        return []
    user_id = user.id
    user_ext_groups = db_session.scalars(
        select(User__ExternalUserGroupId).where(
            User__ExternalUserGroupId.user_id == user_id,
            User__ExternalUserGroupId.external_user_group_id.in_(group_ids),
        )
    ).all()
    return list(user_ext_groups)


def fetch_public_external_group_ids(
    db_session: Session,
) -> list[str]:
    return list(
        db_session.scalars(select(PublicExternalUserGroup.external_user_group_id)).all()
    )
