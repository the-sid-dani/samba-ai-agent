from typing import cast

from sambaai.configs.constants import KV_PENDING_USERS_KEY
from sambaai.configs.constants import KV_USER_STORE_KEY
from sambaai.key_value_store.factory import get_kv_store
from sambaai.key_value_store.interface import KvKeyNotFoundError
from sambaai.utils.special_types import JSON_ro


def get_invited_users() -> list[str]:
    try:
        store = get_kv_store()
        return cast(list, store.load(KV_USER_STORE_KEY))
    except KvKeyNotFoundError:
        return list()


def write_invited_users(emails: list[str]) -> int:
    store = get_kv_store()
    store.store(KV_USER_STORE_KEY, cast(JSON_ro, emails))
    return len(emails)


def get_pending_users() -> list[str]:
    try:
        store = get_kv_store()
        return cast(list, store.load(KV_PENDING_USERS_KEY))
    except KvKeyNotFoundError:
        return list()


def write_pending_users(emails: list[str]) -> int:
    store = get_kv_store()
    store.store(KV_PENDING_USERS_KEY, cast(JSON_ro, emails))
    return len(emails)
