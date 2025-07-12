"""
Security and RBAC System for Workflow Orchestration

This module provides comprehensive security features including:
- Role-based access control (RBAC)
- Secrets management
- Audit logging
- Authentication systems
- Permission management
- Security policies

Inspired by: Tracecat, StackStorm, Apache Airflow
"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

try:
    import bcrypt

    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

try:
    import jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

logger = logging.getLogger(__name__)


class Permission(Enum):
    """Workflow permissions"""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"
    SCHEDULE = "schedule"
    TRIGGER = "trigger"
    VIEW_LOGS = "view_logs"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_SECRETS = "manage_secrets"


class ResourceType(Enum):
    """Resource types for RBAC"""

    WORKFLOW = "workflow"
    JOB = "job"
    STAGE = "stage"
    TRIGGER = "trigger"
    SCHEDULE = "schedule"
    SECRET = "secret"
    USER = "user"
    ROLE = "role"
    SYSTEM = "system"


@dataclass
class Role:
    """Role definition for RBAC"""

    name: str
    description: str
    permissions: set[Permission] = field(default_factory=set)
    resources: set[str] = field(default_factory=set)  # Resource patterns
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class User:
    """User definition"""

    username: str
    email: str
    password_hash: str
    roles: set[str] = field(default_factory=set)
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None


@dataclass
class AuditEvent:
    """Audit event record"""

    timestamp: datetime
    user: str
    action: str
    resource: str
    resource_type: ResourceType
    details: dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True


class AuthenticationProvider(ABC):
    """Abstract authentication provider"""

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> Optional[User]:
        """Authenticate user with credentials"""
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> Optional[User]:
        """Validate authentication token"""
        pass


class LocalAuthProvider(AuthenticationProvider):
    """Local authentication provider"""

    def __init__(self, users_file: str = "users.json"):
        self.users_file = Path(users_file)
        self.users: dict[str, User] = {}
        self._load_users()

    def _load_users(self):
        """Load users from file"""
        if self.users_file.exists():
            try:
                with open(self.users_file) as f:
                    data = json.load(f)
                    for user_data in data.get("users", []):
                        user = User(
                            username=user_data["username"],
                            email=user_data["email"],
                            password_hash=user_data["password_hash"],
                            roles=set(user_data.get("roles", [])),
                            is_active=user_data.get("is_active", True),
                            is_superuser=user_data.get("is_superuser", False),
                            created_at=datetime.fromisoformat(
                                user_data["created_at"]
                            ),
                            last_login=(
                                datetime.fromisoformat(user_data["last_login"])
                                if user_data.get("last_login")
                                else None
                            ),
                            failed_login_attempts=user_data.get(
                                "failed_login_attempts", 0
                            ),
                            locked_until=(
                                datetime.fromisoformat(
                                    user_data["locked_until"]
                                )
                                if user_data.get("locked_until")
                                else None
                            ),
                        )
                        self.users[user.username] = user
            except Exception as e:
                logger.error(f"Failed to load users: {e}")

    def _save_users(self):
        """Save users to file"""
        try:
            data = {
                "users": [
                    {
                        "username": user.username,
                        "email": user.email,
                        "password_hash": user.password_hash,
                        "roles": list(user.roles),
                        "is_active": user.is_active,
                        "is_superuser": user.is_superuser,
                        "created_at": user.created_at.isoformat(),
                        "last_login": (
                            user.last_login.isoformat()
                            if user.last_login
                            else None
                        ),
                        "failed_login_attempts": user.failed_login_attempts,
                        "locked_until": (
                            user.locked_until.isoformat()
                            if user.locked_until
                            else None
                        ),
                    }
                    for user in self.users.values()
                ]
            }
            with open(self.users_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt or fallback"""
        if BCRYPT_AVAILABLE:
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(password.encode(), salt).decode()
        else:
            # Fallback to simple hash (not recommended for production)
            return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password hash"""
        if BCRYPT_AVAILABLE:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        else:
            # Fallback verification
            return (
                hashlib.sha256(password.encode()).hexdigest() == password_hash
            )

    async def authenticate(self, credentials: dict[str, Any]) -> Optional[User]:
        """Authenticate user with username/password"""
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return None

        user = self.users.get(username)
        if not user or not user.is_active:
            return None

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            return None

        if self._verify_password(password, user.password_hash):
            # Reset failed attempts
            user.failed_login_attempts = 0
            user.last_login = datetime.utcnow()
            user.locked_until = None
            self._save_users()
            return user
        else:
            # Increment failed attempts
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            self._save_users()
            return None

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate JWT token"""
        if not JWT_AVAILABLE:
            return None

        try:
            payload = jwt.decode(
                token,
                os.getenv("JWT_SECRET", "default-secret"),
                algorithms=["HS256"],
            )
            username = payload.get("username")
            if username and username in self.users:
                return self.users[username]
        except jwt.InvalidTokenError:
            pass
        return None

    def create_user(
        self, username: str, email: str, password: str, roles: list[str] = None
    ) -> User:
        """Create a new user"""
        if username in self.users:
            raise ValueError(f"User {username} already exists")

        password_hash = self._hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            roles=set(roles or []),
        )
        self.users[username] = user
        self._save_users()
        return user


class SecretsManager:
    """Secrets management system"""

    def __init__(self, master_key: Optional[str] = None):
        if not CRYPTOGRAPHY_AVAILABLE:
            logger.warning("Cryptography not available, using basic encryption")
            self.fernet = None
        else:
            if master_key:
                key = self._derive_key(master_key)
            else:
                key = Fernet.generate_key()
            self.fernet = Fernet(key)

        self.secrets: dict[str, dict[str, Any]] = {}
        self.secrets_file = Path("secrets.json")
        self._load_secrets()

    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password"""
        salt = b"workflow_salt"  # In production, use random salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password.encode())

    def _encrypt(self, data: str) -> str:
        """Encrypt data"""
        if self.fernet:
            return self.fernet.encrypt(data.encode()).decode()
        else:
            # Basic encryption (not secure)
            return data

    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt data"""
        if self.fernet:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        else:
            # Basic decryption
            return encrypted_data

    def _load_secrets(self):
        """Load secrets from file"""
        if self.secrets_file.exists():
            try:
                with open(self.secrets_file) as f:
                    data = json.load(f)
                    for secret_id, secret_data in data.items():
                        self.secrets[secret_id] = {
                            "name": secret_data["name"],
                            "description": secret_data.get("description", ""),
                            "encrypted_value": secret_data["encrypted_value"],
                            "created_at": secret_data["created_at"],
                            "updated_at": secret_data["updated_at"],
                            "tags": secret_data.get("tags", []),
                        }
            except Exception as e:
                logger.error(f"Failed to load secrets: {e}")

    def _save_secrets(self):
        """Save secrets to file"""
        try:
            with open(self.secrets_file, "w") as f:
                json.dump(self.secrets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")

    def store_secret(
        self,
        name: str,
        value: str,
        description: str = "",
        tags: list[str] = None,
    ) -> str:
        """Store a secret"""
        secret_id = f"secret_{int(time.time())}_{secrets.token_hex(4)}"
        encrypted_value = self._encrypt(value)

        self.secrets[secret_id] = {
            "name": name,
            "description": description,
            "encrypted_value": encrypted_value,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "tags": tags or [],
        }

        self._save_secrets()
        return secret_id

    def get_secret(self, secret_id: str) -> Optional[str]:
        """Retrieve a secret"""
        if secret_id not in self.secrets:
            return None

        encrypted_value = self.secrets[secret_id]["encrypted_value"]
        return self._decrypt(encrypted_value)

    def list_secrets(self) -> list[dict[str, Any]]:
        """List all secrets (without values)"""
        return [
            {
                "id": secret_id,
                "name": secret_data["name"],
                "description": secret_data["description"],
                "created_at": secret_data["created_at"],
                "updated_at": secret_data["updated_at"],
                "tags": secret_data["tags"],
            }
            for secret_id, secret_data in self.secrets.items()
        ]

    def delete_secret(self, secret_id: str) -> bool:
        """Delete a secret"""
        if secret_id in self.secrets:
            del self.secrets[secret_id]
            self._save_secrets()
            return True
        return False


class RBACManager:
    """Role-based access control manager"""

    def __init__(self):
        self.roles: dict[str, Role] = {}
        self.default_roles = self._create_default_roles()
        self.roles.update(self.default_roles)

    def _create_default_roles(self) -> dict[str, Role]:
        """Create default roles"""
        return {
            "admin": Role(
                name="admin",
                description="Full system access",
                permissions={perm for perm in Permission},
                resources={"*"},
            ),
            "user": Role(
                name="user",
                description="Basic user access",
                permissions={
                    Permission.READ,
                    Permission.EXECUTE,
                    Permission.SCHEDULE,
                    Permission.TRIGGER,
                    Permission.VIEW_LOGS,
                },
                resources={"workflow:*", "job:*", "stage:*"},
            ),
            "viewer": Role(
                name="viewer",
                description="Read-only access",
                permissions={Permission.READ, Permission.VIEW_LOGS},
                resources={"workflow:*", "job:*", "stage:*"},
            ),
            "operator": Role(
                name="operator",
                description="Workflow operator",
                permissions={
                    Permission.READ,
                    Permission.EXECUTE,
                    Permission.SCHEDULE,
                    Permission.TRIGGER,
                    Permission.VIEW_LOGS,
                },
                resources={
                    "workflow:*",
                    "job:*",
                    "stage:*",
                    "trigger:*",
                    "schedule:*",
                },
            ),
        }

    def create_role(
        self,
        name: str,
        description: str,
        permissions: list[Permission],
        resources: list[str],
    ) -> Role:
        """Create a new role"""
        if name in self.roles:
            raise ValueError(f"Role {name} already exists")

        role = Role(
            name=name,
            description=description,
            permissions=set(permissions),
            resources=set(resources),
        )
        self.roles[name] = role
        return role

    def get_role(self, name: str) -> Optional[Role]:
        """Get role by name"""
        return self.roles.get(name)

    def list_roles(self) -> list[Role]:
        """List all roles"""
        return list(self.roles.values())

    def check_permission(
        self, user: User, permission: Permission, resource: str
    ) -> bool:
        """Check if user has permission for resource"""
        if user.is_superuser:
            return True

        for role_name in user.roles:
            role = self.roles.get(role_name)
            if not role:
                continue

            if permission not in role.permissions:
                continue

            # Check resource pattern matching
            for pattern in role.resources:
                if self._match_resource_pattern(resource, pattern):
                    return True

        return False

    def _match_resource_pattern(self, resource: str, pattern: str) -> bool:
        """Match resource against pattern"""
        if pattern == "*":
            return True

        if pattern.endswith(":*"):
            prefix = pattern[:-2]
            return resource.startswith(prefix)

        return resource == pattern


class AuditLogger:
    """Audit logging system"""

    def __init__(self, log_file: str = "audit.log"):
        self.log_file = Path(log_file)
        self.events: list[AuditEvent] = []
        self.max_events = 10000  # Keep last 10k events in memory

    def log_event(
        self,
        user: str,
        action: str,
        resource: str,
        resource_type: ResourceType,
        details: dict[str, Any],
        ip_address: str = None,
        user_agent: str = None,
        success: bool = True,
    ):
        """Log an audit event"""
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            user=user,
            action=action,
            resource=resource,
            resource_type=resource_type,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
        )

        self.events.append(event)

        # Keep only recent events in memory
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]

        # Write to file
        self._write_event(event)

    def _write_event(self, event: AuditEvent):
        """Write event to log file"""
        try:
            log_entry = {
                "timestamp": event.timestamp.isoformat(),
                "user": event.user,
                "action": event.action,
                "resource": event.resource,
                "resource_type": event.resource_type.value,
                "details": event.details,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "success": event.success,
            }

            with open(self.log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")

    def get_events(
        self,
        user: str = None,
        action: str = None,
        resource: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> list[AuditEvent]:
        """Get filtered audit events"""
        events = self.events

        if user:
            events = [e for e in events if e.user == user]
        if action:
            events = [e for e in events if e.action == action]
        if resource:
            events = [e for e in events if e.resource == resource]
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        return events


class SecurityManager:
    """Main security manager"""

    def __init__(self, auth_provider: AuthenticationProvider = None):
        self.auth_provider = auth_provider or LocalAuthProvider()
        self.rbac_manager = RBACManager()
        self.secrets_manager = SecretsManager()
        self.audit_logger = AuditLogger()
        self.current_user: Optional[User] = None

    async def authenticate(self, credentials: dict[str, Any]) -> Optional[str]:
        """Authenticate user and return token"""
        user = await self.auth_provider.authenticate(credentials)
        if not user:
            self.audit_logger.log_event(
                user=credentials.get("username", "unknown"),
                action="login",
                resource="system",
                resource_type=ResourceType.SYSTEM,
                details={"method": "password"},
                success=False,
            )
            return None

        self.audit_logger.log_event(
            user=user.username,
            action="login",
            resource="system",
            resource_type=ResourceType.SYSTEM,
            details={"method": "password"},
            success=True,
        )

        if JWT_AVAILABLE:
            payload = {
                "username": user.username,
                "roles": list(user.roles),
                "exp": datetime.utcnow() + timedelta(hours=24),
            }
            return jwt.encode(
                payload,
                os.getenv("JWT_SECRET", "default-secret"),
                algorithm="HS256",
            )
        else:
            # Fallback to simple token
            return f"token_{user.username}_{int(time.time())}"

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate token and set current user"""
        user = await self.auth_provider.validate_token(token)
        if user:
            self.current_user = user
        return user

    def check_permission(self, permission: Permission, resource: str) -> bool:
        """Check if current user has permission"""
        if not self.current_user:
            return False

        return self.rbac_manager.check_permission(
            self.current_user, permission, resource
        )

    def require_permission(self, permission: Permission, resource: str):
        """Decorator to require permission"""

        def decorator(func):
            def wrapper(*args, **kwargs):
                if not self.check_permission(permission, resource):
                    raise PermissionError(
                        f"Permission {permission.value} required for {resource}"
                    )
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def log_action(
        self,
        action: str,
        resource: str,
        resource_type: ResourceType,
        details: dict[str, Any] = None,
    ):
        """Log security action"""
        if self.current_user:
            self.audit_logger.log_event(
                user=self.current_user.username,
                action=action,
                resource=resource,
                resource_type=resource_type,
                details=details or {},
            )


# Global security manager instance
security_manager = SecurityManager()


# Security decorators for easy use
def require_auth(func):
    """Decorator to require authentication"""

    def wrapper(*args, **kwargs):
        if not security_manager.current_user:
            raise PermissionError("Authentication required")
        return func(*args, **kwargs)

    return wrapper


def require_permission(permission: Permission, resource: str):
    """Decorator to require specific permission"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not security_manager.check_permission(permission, resource):
                raise PermissionError(
                    f"Permission {permission.value} required for {resource}"
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_action(action: str, resource: str, resource_type: ResourceType):
    """Decorator to log actions"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            security_manager.log_action(
                action, resource, resource_type, {"result": "success"}
            )
            return result

        return decorator

    return decorator


# Example usage functions
async def create_initial_admin():
    """Create initial admin user"""
    if isinstance(security_manager.auth_provider, LocalAuthProvider):
        try:
            admin_user = security_manager.auth_provider.create_user(
                username="admin",
                email="admin@example.com",
                password="admin123",
                roles=["admin"],
            )
            logger.info(f"Created admin user: {admin_user.username}")
            return admin_user
        except ValueError:
            logger.info("Admin user already exists")


async def setup_security():
    """Setup security system"""
    await create_initial_admin()
    logger.info("Security system initialized")


# Initialize security system
if __name__ == "__main__":
    asyncio.run(setup_security())
