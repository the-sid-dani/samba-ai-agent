from sqlalchemy.orm import Session

from ee.sambaai.db.external_perm import fetch_external_groups_for_user
from ee.sambaai.db.external_perm import fetch_public_external_group_ids
from ee.sambaai.db.user_group import fetch_user_groups_for_documents
from ee.sambaai.db.user_group import fetch_user_groups_for_user
from ee.sambaai.external_permissions.post_query_censoring import (
    DOC_SOURCE_TO_CHUNK_CENSORING_FUNCTION,
)
from ee.sambaai.external_permissions.sync_params import DOC_PERMISSIONS_FUNC_MAP
from sambaai.access.access import (
    _get_access_for_documents as get_access_for_documents_without_groups,
)
from sambaai.access.access import _get_acl_for_user as get_acl_for_user_without_groups
from sambaai.access.models import DocumentAccess
from sambaai.access.utils import prefix_external_group
from sambaai.access.utils import prefix_user_group
from sambaai.db.document import get_document_sources
from sambaai.db.document import get_documents_by_ids
from sambaai.db.models import User


def _get_access_for_document(
    document_id: str,
    db_session: Session,
) -> DocumentAccess:
    id_to_access = _get_access_for_documents([document_id], db_session)
    if len(id_to_access) == 0:
        return DocumentAccess.build(
            user_emails=[],
            user_groups=[],
            external_user_emails=[],
            external_user_group_ids=[],
            is_public=False,
        )

    return next(iter(id_to_access.values()))


def _get_access_for_documents(
    document_ids: list[str],
    db_session: Session,
) -> dict[str, DocumentAccess]:
    non_ee_access_dict = get_access_for_documents_without_groups(
        document_ids=document_ids,
        db_session=db_session,
    )
    user_group_info: dict[str, list[str]] = {
        document_id: group_names
        for document_id, group_names in fetch_user_groups_for_documents(
            db_session=db_session,
            document_ids=document_ids,
        )
    }
    documents = get_documents_by_ids(
        db_session=db_session,
        document_ids=document_ids,
    )
    doc_id_map = {doc.id: doc for doc in documents}

    # Get all sources in one batch
    doc_id_to_source_map = get_document_sources(
        db_session=db_session,
        document_ids=document_ids,
    )

    all_public_ext_u_group_ids = set(fetch_public_external_group_ids(db_session))

    access_map = {}
    for document_id, non_ee_access in non_ee_access_dict.items():
        document = doc_id_map[document_id]
        source = doc_id_to_source_map.get(document_id)
        is_only_censored = (
            source in DOC_SOURCE_TO_CHUNK_CENSORING_FUNCTION
            and source not in DOC_PERMISSIONS_FUNC_MAP
        )

        ext_u_emails = (
            set(document.external_user_emails)
            if document.external_user_emails
            else set()
        )

        ext_u_groups = (
            set(document.external_user_group_ids)
            if document.external_user_group_ids
            else set()
        )

        # If the document is determined to be "public" externally (through a SYNC connector)
        # then it's given the same access level as if it were marked public within SambaAI
        # If its censored, then it's public anywhere during the search and then permissions are
        # applied after the search
        is_public_anywhere = (
            document.is_public
            or non_ee_access.is_public
            or is_only_censored
            or any(u_group in all_public_ext_u_group_ids for u_group in ext_u_groups)
        )

        # To avoid collisions of group namings between connectors, they need to be prefixed
        access_map[document_id] = DocumentAccess.build(
            user_emails=list(non_ee_access.user_emails),
            user_groups=user_group_info.get(document_id, []),
            is_public=is_public_anywhere,
            external_user_emails=list(ext_u_emails),
            external_user_group_ids=list(ext_u_groups),
        )
    return access_map


def _get_acl_for_user(user: User | None, db_session: Session) -> set[str]:
    """Returns a list of ACL entries that the user has access to. This is meant to be
    used downstream to filter out documents that the user does not have access to. The
    user should have access to a document if at least one entry in the document's ACL
    matches one entry in the returned set.

    NOTE: is imported in sambaai.access.access by `fetch_versioned_implementation`
    DO NOT REMOVE."""
    db_user_groups = fetch_user_groups_for_user(db_session, user.id) if user else []
    prefixed_user_groups = [
        prefix_user_group(db_user_group.name) for db_user_group in db_user_groups
    ]

    db_external_groups = (
        fetch_external_groups_for_user(db_session, user.id) if user else []
    )
    prefixed_external_groups = [
        prefix_external_group(db_external_group.external_user_group_id)
        for db_external_group in db_external_groups
    ]

    user_acl = set(prefixed_user_groups + prefixed_external_groups)
    user_acl.update(get_acl_for_user_without_groups(user, db_session))

    return user_acl
