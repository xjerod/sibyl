"""Active operational runtime adapters for the current relational backend."""

from sibyl.persistence.legacy.admin import recover_legacy_stuck_sources
from sibyl.persistence.legacy.backups import (
    attach_legacy_backup_job,
    create_legacy_backup_record,
    delete_legacy_backup_record,
    get_legacy_backup,
    get_legacy_backup_retention,
    get_legacy_backup_settings,
    list_legacy_backups,
    update_legacy_backup_settings,
)
from sibyl.persistence.legacy.jobs import (
    _job_visible_to_org,
    _resolve_visible_legacy_source_ids,
)
from sibyl.persistence.legacy.settings import (
    is_legacy_setup_mode,
    require_legacy_settings_admin,
)
from sibyl.persistence.legacy.setup import (
    get_legacy_setup_status,
    require_legacy_setup_mode_or_admin,
    require_legacy_setup_mode_or_auth,
)
from sibyl.persistence.legacy.users import (
    confirm_legacy_password_reset,
    list_legacy_oauth_connections,
    remove_legacy_oauth_connection,
    request_legacy_password_reset,
)

__all__ = [
    "_job_visible_to_org",
    "_resolve_visible_legacy_source_ids",
    "attach_legacy_backup_job",
    "confirm_legacy_password_reset",
    "create_legacy_backup_record",
    "delete_legacy_backup_record",
    "get_legacy_backup",
    "get_legacy_backup_retention",
    "get_legacy_backup_settings",
    "get_legacy_setup_status",
    "is_legacy_setup_mode",
    "list_legacy_backups",
    "list_legacy_oauth_connections",
    "recover_legacy_stuck_sources",
    "remove_legacy_oauth_connection",
    "request_legacy_password_reset",
    "require_legacy_settings_admin",
    "require_legacy_setup_mode_or_admin",
    "require_legacy_setup_mode_or_auth",
    "update_legacy_backup_settings",
]
