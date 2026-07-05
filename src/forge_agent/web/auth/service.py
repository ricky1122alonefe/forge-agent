"""Auth business logic: register, login, tenant bootstrap."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from forge_agent.platform.local_tenant import LocalTenant
from forge_agent.web.auth.config import WebAuthConfig
from forge_agent.web.auth.passwords import hash_password, verify_password
from forge_agent.web.auth.store import AuthStore, UserRecord

_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,31}$")


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    username: str
    tenant_id: str


def _to_auth_user(record: UserRecord) -> AuthUser:
    return AuthUser(user_id=record.user_id, username=record.username, tenant_id=record.tenant_id)


class AuthService:
    def __init__(self, data_root: Path, config: WebAuthConfig) -> None:
        self.data_root = data_root
        self.config = config
        self.store = AuthStore(data_root)

    def validate_username(self, username: str) -> str:
        username = username.strip()
        if not _USERNAME_RE.match(username):
            raise ValueError("用户名需 3-32 位，字母开头，仅含字母/数字/_/-，且会作为租户 ID")
        return username

    def register(self, username: str, password: str) -> tuple[AuthUser, str]:
        username = self.validate_username(username)
        if len(password) < 8:
            raise ValueError("密码至少 8 位")

        salt, password_hash = hash_password(password)
        tenant_id = username
        user = _to_auth_user(
            self.store.create_user(
                username=username,
                tenant_id=tenant_id,
                password_salt=salt,
                password_hash=password_hash,
            )
        )
        tenant = LocalTenant(tenant_id, root_dir=self.data_root)
        tenant.get_shared_path()
        tenant.ensure_project("default")
        session_id = self.store.create_session(
            user.user_id, ttl_hours=self.config.session_ttl_hours
        )
        return user, session_id

    def login(self, username: str, password: str) -> tuple[AuthUser, str]:
        username = username.strip()
        record = self.store.get_user_by_username(username)
        if record is None or not verify_password(
            password, record.password_salt, record.password_hash
        ):
            raise ValueError("用户名或密码错误")
        user = _to_auth_user(record)
        session_id = self.store.create_session(
            user.user_id, ttl_hours=self.config.session_ttl_hours
        )
        return user, session_id

    def logout(self, session_id: str | None) -> None:
        if session_id:
            self.store.delete_session(session_id)

    def get_user_for_session(self, session_id: str | None) -> AuthUser | None:
        if not session_id:
            return None
        record = self.store.get_user_for_session(session_id)
        return _to_auth_user(record) if record else None

    def user_can_access_tenant(self, user: AuthUser | None, tenant_id: str) -> bool:
        if user is None:
            return False
        return user.tenant_id == tenant_id
