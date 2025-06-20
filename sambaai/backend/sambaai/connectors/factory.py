from typing import Any
from typing import Type

from sqlalchemy.orm import Session

from sambaai.configs.app_configs import INTEGRATION_TESTS_MODE
from sambaai.configs.constants import DocumentSource
from sambaai.configs.llm_configs import get_image_extraction_and_analysis_enabled
from sambaai.connectors.airtable.airtable_connector import AirtableConnector
from sambaai.connectors.asana.connector import AsanaConnector
from sambaai.connectors.axero.connector import AxeroConnector
from sambaai.connectors.blob.connector import BlobStorageConnector
from sambaai.connectors.bookstack.connector import BookstackConnector
from sambaai.connectors.clickup.connector import ClickupConnector
from sambaai.connectors.confluence.connector import ConfluenceConnector
from sambaai.connectors.credentials_provider import SambaAIDBCredentialsProvider
from sambaai.connectors.discord.connector import DiscordConnector
from sambaai.connectors.discourse.connector import DiscourseConnector
from sambaai.connectors.document360.connector import Document360Connector
from sambaai.connectors.dropbox.connector import DropboxConnector
from sambaai.connectors.egnyte.connector import EgnyteConnector
from sambaai.connectors.exceptions import ConnectorValidationError
from sambaai.connectors.file.connector import LocalFileConnector
from sambaai.connectors.fireflies.connector import FirefliesConnector
from sambaai.connectors.freshdesk.connector import FreshdeskConnector
from sambaai.connectors.gitbook.connector import GitbookConnector
from sambaai.connectors.github.connector import GithubConnector
from sambaai.connectors.gitlab.connector import GitlabConnector
from sambaai.connectors.gmail.connector import GmailConnector
from sambaai.connectors.gong.connector import GongConnector
from sambaai.connectors.google_drive.connector import GoogleDriveConnector
from sambaai.connectors.google_site.connector import GoogleSitesConnector
from sambaai.connectors.guru.connector import GuruConnector
from sambaai.connectors.highspot.connector import HighspotConnector
from sambaai.connectors.hubspot.connector import HubSpotConnector
from sambaai.connectors.interfaces import BaseConnector
from sambaai.connectors.interfaces import CheckpointedConnector
from sambaai.connectors.interfaces import CredentialsConnector
from sambaai.connectors.interfaces import EventConnector
from sambaai.connectors.interfaces import LoadConnector
from sambaai.connectors.interfaces import PollConnector
from sambaai.connectors.linear.connector import LinearConnector
from sambaai.connectors.loopio.connector import LoopioConnector
from sambaai.connectors.mediawiki.wiki import MediaWikiConnector
from sambaai.connectors.mock_connector.connector import MockConnector
from sambaai.connectors.models import InputType
from sambaai.connectors.notion.connector import NotionConnector
from sambaai.connectors.sambaai_jira.connector import JiraConnector
from sambaai.connectors.productboard.connector import ProductboardConnector
from sambaai.connectors.salesforce.connector import SalesforceConnector
from sambaai.connectors.sharepoint.connector import SharepointConnector
from sambaai.connectors.slab.connector import SlabConnector
from sambaai.connectors.slack.connector import SlackConnector
from sambaai.connectors.teams.connector import TeamsConnector
from sambaai.connectors.web.connector import WebConnector
from sambaai.connectors.wikipedia.connector import WikipediaConnector
from sambaai.connectors.xenforo.connector import XenforoConnector
from sambaai.connectors.zendesk.connector import ZendeskConnector
from sambaai.connectors.zulip.connector import ZulipConnector
from sambaai.db.connector import fetch_connector_by_id
from sambaai.db.credentials import backend_update_credential_json
from sambaai.db.credentials import fetch_credential_by_id
from sambaai.db.models import Credential
from shared_configs.contextvars import get_current_tenant_id


class ConnectorMissingException(Exception):
    pass


def identify_connector_class(
    source: DocumentSource,
    input_type: InputType | None = None,
) -> Type[BaseConnector]:
    connector_map = {
        DocumentSource.WEB: WebConnector,
        DocumentSource.FILE: LocalFileConnector,
        DocumentSource.SLACK: {
            InputType.POLL: SlackConnector,
            InputType.SLIM_RETRIEVAL: SlackConnector,
        },
        DocumentSource.GITHUB: GithubConnector,
        DocumentSource.GMAIL: GmailConnector,
        DocumentSource.GITLAB: GitlabConnector,
        DocumentSource.GITBOOK: GitbookConnector,
        DocumentSource.GOOGLE_DRIVE: GoogleDriveConnector,
        DocumentSource.BOOKSTACK: BookstackConnector,
        DocumentSource.CONFLUENCE: ConfluenceConnector,
        DocumentSource.JIRA: JiraConnector,
        DocumentSource.PRODUCTBOARD: ProductboardConnector,
        DocumentSource.SLAB: SlabConnector,
        DocumentSource.NOTION: NotionConnector,
        DocumentSource.ZULIP: ZulipConnector,
        DocumentSource.GURU: GuruConnector,
        DocumentSource.LINEAR: LinearConnector,
        DocumentSource.HUBSPOT: HubSpotConnector,
        DocumentSource.DOCUMENT360: Document360Connector,
        DocumentSource.GONG: GongConnector,
        DocumentSource.GOOGLE_SITES: GoogleSitesConnector,
        DocumentSource.ZENDESK: ZendeskConnector,
        DocumentSource.LOOPIO: LoopioConnector,
        DocumentSource.DROPBOX: DropboxConnector,
        DocumentSource.SHAREPOINT: SharepointConnector,
        DocumentSource.TEAMS: TeamsConnector,
        DocumentSource.SALESFORCE: SalesforceConnector,
        DocumentSource.DISCOURSE: DiscourseConnector,
        DocumentSource.AXERO: AxeroConnector,
        DocumentSource.CLICKUP: ClickupConnector,
        DocumentSource.MEDIAWIKI: MediaWikiConnector,
        DocumentSource.WIKIPEDIA: WikipediaConnector,
        DocumentSource.ASANA: AsanaConnector,
        DocumentSource.S3: BlobStorageConnector,
        DocumentSource.R2: BlobStorageConnector,
        DocumentSource.GOOGLE_CLOUD_STORAGE: BlobStorageConnector,
        DocumentSource.OCI_STORAGE: BlobStorageConnector,
        DocumentSource.XENFORO: XenforoConnector,
        DocumentSource.DISCORD: DiscordConnector,
        DocumentSource.FRESHDESK: FreshdeskConnector,
        DocumentSource.FIREFLIES: FirefliesConnector,
        DocumentSource.EGNYTE: EgnyteConnector,
        DocumentSource.AIRTABLE: AirtableConnector,
        DocumentSource.HIGHSPOT: HighspotConnector,
        # just for integration tests
        DocumentSource.MOCK_CONNECTOR: MockConnector,
    }
    connector_by_source = connector_map.get(source, {})

    if isinstance(connector_by_source, dict):
        if input_type is None:
            # If not specified, default to most exhaustive update
            connector = connector_by_source.get(InputType.LOAD_STATE)
        else:
            connector = connector_by_source.get(input_type)
    else:
        connector = connector_by_source
    if connector is None:
        raise ConnectorMissingException(f"Connector not found for source={source}")

    if any(
        [
            (
                input_type == InputType.LOAD_STATE
                and not issubclass(connector, LoadConnector)
            ),
            (
                input_type == InputType.POLL
                # either poll or checkpoint works for this, in the future
                # all connectors should be checkpoint connectors
                and (
                    not issubclass(connector, PollConnector)
                    and not issubclass(connector, CheckpointedConnector)
                )
            ),
            (
                input_type == InputType.EVENT
                and not issubclass(connector, EventConnector)
            ),
        ]
    ):
        raise ConnectorMissingException(
            f"Connector for source={source} does not accept input_type={input_type}"
        )
    return connector


def instantiate_connector(
    db_session: Session,
    source: DocumentSource,
    input_type: InputType,
    connector_specific_config: dict[str, Any],
    credential: Credential,
) -> BaseConnector:
    connector_class = identify_connector_class(source, input_type)

    connector = connector_class(**connector_specific_config)

    if isinstance(connector, CredentialsConnector):
        provider = SambaAIDBCredentialsProvider(
            get_current_tenant_id(), str(source), credential.id
        )
        connector.set_credentials_provider(provider)
    else:
        new_credentials = connector.load_credentials(credential.credential_json)

        if new_credentials is not None:
            backend_update_credential_json(credential, new_credentials, db_session)

    connector.set_allow_images(get_image_extraction_and_analysis_enabled())

    return connector


def validate_ccpair_for_user(
    connector_id: int,
    credential_id: int,
    db_session: Session,
    enforce_creation: bool = True,
) -> bool:
    if INTEGRATION_TESTS_MODE:
        return True

    # Validate the connector settings
    connector = fetch_connector_by_id(connector_id, db_session)
    credential = fetch_credential_by_id(
        credential_id,
        db_session,
    )

    if not connector:
        raise ValueError("Connector not found")

    if (
        connector.source == DocumentSource.INGESTION_API
        or connector.source == DocumentSource.MOCK_CONNECTOR
    ):
        return True

    if not credential:
        raise ValueError("Credential not found")

    try:
        runnable_connector = instantiate_connector(
            db_session=db_session,
            source=connector.source,
            input_type=connector.input_type,
            connector_specific_config=connector.connector_specific_config,
            credential=credential,
        )
    except ConnectorValidationError as e:
        raise e
    except Exception as e:
        if enforce_creation:
            raise ConnectorValidationError(str(e))
        else:
            return False

    runnable_connector.validate_connector_settings()
    return True
