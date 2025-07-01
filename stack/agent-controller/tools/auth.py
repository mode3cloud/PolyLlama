"""
Tool authorization and access control system.

This module provides authentication and authorization mechanisms
for tool execution, including role-based access control and
audit logging.
"""

from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets
from abc import ABC, abstractmethod
import asyncio
import logging

from .base import Tool, ToolResult, ToolError, ToolStatus


logger = logging.getLogger(__name__)


class Permission(Enum):
    """Tool permissions."""
    READ = "read"
    EXECUTE = "execute"
    ADMIN = "admin"


class Role(Enum):
    """User roles."""
    GUEST = "guest"
    USER = "user"
    DEVELOPER = "developer"
    ADMIN = "admin"


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass


class User:
    """Represents a user in the system."""
    
    def __init__(
        self,
        user_id: str,
        username: str,
        roles: List[Role],
        permissions: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize user.
        
        Args:
            user_id: Unique user identifier
            username: Human-readable username
            roles: List of user roles
            permissions: Explicit permissions (optional)
            metadata: Additional user metadata
        """
        self.user_id = user_id
        self.username = username
        self.roles = roles
        self.permissions = permissions or set()
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.last_active = datetime.now()
    
    def has_role(self, role: Role) -> bool:
        """Check if user has a specific role."""
        return role in self.roles
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_active = datetime.now()


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""
    
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> Optional[User]:
        """
        Authenticate user with provided credentials.
        
        Args:
            credentials: Authentication credentials
            
        Returns:
            User object if authentication succeeds, None otherwise
        """
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validate authentication token and return user.
        
        Args:
            token: Authentication token
            
        Returns:
            User object if token is valid, None otherwise
        """
        pass


class SimpleAuthProvider(AuthProvider):
    """Simple authentication provider for development/testing."""
    
    def __init__(self):
        """Initialize simple auth provider."""
        self.users: Dict[str, User] = {}
        self.tokens: Dict[str, str] = {}  # token -> user_id
        self.api_keys: Dict[str, str] = {}  # api_key -> user_id
        
        # Create default admin user
        admin_user = User(
            user_id="admin",
            username="admin",
            roles=[Role.ADMIN],
            permissions={"*"}  # All permissions
        )
        self.users["admin"] = admin_user
        
        # Create default API key for admin
        admin_key = "polyllama-admin-key-" + secrets.token_urlsafe(32)
        self.api_keys[admin_key] = "admin"
        logger.info(f"Created admin API key: {admin_key}")
    
    async def authenticate(self, credentials: Dict[str, Any]) -> Optional[User]:
        """Authenticate with username/password or API key."""
        if "api_key" in credentials:
            user_id = self.api_keys.get(credentials["api_key"])
            if user_id and user_id in self.users:
                user = self.users[user_id]
                user.update_activity()
                return user
        
        elif "username" in credentials and "password" in credentials:
            # Simple password check (in production, use proper hashing)
            username = credentials["username"]
            password = credentials["password"]
            
            for user in self.users.values():
                if user.username == username:
                    # In production, verify hashed password
                    if username == "admin" and password == "admin":
                        user.update_activity()
                        return user
        
        return None
    
    async def validate_token(self, token: str) -> Optional[User]:
        """Validate JWT token (simplified implementation)."""
        user_id = self.tokens.get(token)
        if user_id and user_id in self.users:
            user = self.users[user_id]
            user.update_activity()
            return user
        return None
    
    def create_user(
        self,
        username: str,
        roles: List[Role],
        permissions: Optional[Set[str]] = None
    ) -> User:
        """Create a new user."""
        user_id = hashlib.sha256(username.encode()).hexdigest()[:16]
        user = User(
            user_id=user_id,
            username=username,
            roles=roles,
            permissions=permissions
        )
        self.users[user_id] = user
        return user
    
    def create_api_key(self, user_id: str) -> str:
        """Create API key for user."""
        if user_id not in self.users:
            raise ValueError(f"User {user_id} not found")
        
        api_key = f"polyllama-{user_id}-" + secrets.token_urlsafe(32)
        self.api_keys[api_key] = user_id
        return api_key


class AccessControlList:
    """Manages access control for tools."""
    
    def __init__(self):
        """Initialize access control list."""
        self.tool_permissions: Dict[str, Dict[Role, Set[Permission]]] = {}
        self.user_overrides: Dict[str, Dict[str, Set[Permission]]] = {}  # user_id -> tool_name -> permissions
        self.default_permissions: Dict[Role, Set[Permission]] = {
            Role.GUEST: {Permission.READ},
            Role.USER: {Permission.READ, Permission.EXECUTE},
            Role.DEVELOPER: {Permission.READ, Permission.EXECUTE},
            Role.ADMIN: {Permission.READ, Permission.EXECUTE, Permission.ADMIN}
        }
    
    def set_tool_permissions(
        self,
        tool_name: str,
        role_permissions: Dict[Role, Set[Permission]]
    ) -> None:
        """
        Set permissions for a specific tool.
        
        Args:
            tool_name: Name of the tool
            role_permissions: Mapping of roles to permissions
        """
        self.tool_permissions[tool_name] = role_permissions
    
    def set_user_override(
        self,
        user_id: str,
        tool_name: str,
        permissions: Set[Permission]
    ) -> None:
        """
        Set permission override for a specific user on a tool.
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            permissions: Permissions to grant
        """
        if user_id not in self.user_overrides:
            self.user_overrides[user_id] = {}
        self.user_overrides[user_id][tool_name] = permissions
    
    def check_permission(
        self,
        user: User,
        tool_name: str,
        permission: Permission
    ) -> bool:
        """
        Check if user has permission for tool action.
        
        Args:
            user: User object
            tool_name: Tool name
            permission: Required permission
            
        Returns:
            True if user has permission, False otherwise
        """
        # Admin users have all permissions
        if user.has_role(Role.ADMIN) and "*" in user.permissions:
            return True
        
        # Check user-specific overrides
        if user.user_id in self.user_overrides:
            user_tool_perms = self.user_overrides[user.user_id].get(tool_name)
            if user_tool_perms and permission in user_tool_perms:
                return True
        
        # Check tool-specific permissions
        if tool_name in self.tool_permissions:
            tool_perms = self.tool_permissions[tool_name]
            for role in user.roles:
                if role in tool_perms and permission in tool_perms[role]:
                    return True
        
        # Check default permissions
        for role in user.roles:
            if role in self.default_permissions and permission in self.default_permissions[role]:
                return True
        
        return False
    
    def get_user_permissions(self, user: User, tool_name: str) -> Set[Permission]:
        """Get all permissions user has for a tool."""
        permissions = set()
        
        # Admin users have all permissions
        if user.has_role(Role.ADMIN) and "*" in user.permissions:
            return {Permission.READ, Permission.EXECUTE, Permission.ADMIN}
        
        # User-specific overrides
        if user.user_id in self.user_overrides:
            user_tool_perms = self.user_overrides[user.user_id].get(tool_name)
            if user_tool_perms:
                permissions.update(user_tool_perms)
        
        # Tool-specific permissions
        if tool_name in self.tool_permissions:
            tool_perms = self.tool_permissions[tool_name]
            for role in user.roles:
                if role in tool_perms:
                    permissions.update(tool_perms[role])
        
        # Default permissions
        for role in user.roles:
            if role in self.default_permissions:
                permissions.update(self.default_permissions[role])
        
        return permissions


class AuditLogger:
    """Logs tool access and execution for security auditing."""
    
    def __init__(self, max_entries: int = 10000):
        """
        Initialize audit logger.
        
        Args:
            max_entries: Maximum number of audit entries to keep
        """
        self.max_entries = max_entries
        self.entries: List[Dict[str, Any]] = []
        self.lock = asyncio.Lock()
    
    async def log_access(
        self,
        user: User,
        tool_name: str,
        action: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a tool access event.
        
        Args:
            user: User who performed the action
            tool_name: Tool that was accessed
            action: Action performed (execute, read_schema, etc.)
            success: Whether the action succeeded
            details: Additional details about the action
        """
        async with self.lock:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user.user_id,
                "username": user.username,
                "user_roles": [r.value for r in user.roles],
                "tool_name": tool_name,
                "action": action,
                "success": success,
                "details": details or {}
            }
            
            self.entries.append(entry)
            
            # Trim old entries if necessary
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries:]
    
    async def get_audit_log(
        self,
        user_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit log entries with optional filtering.
        
        Args:
            user_id: Filter by user ID
            tool_name: Filter by tool name
            since: Filter by timestamp (entries since this time)
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        async with self.lock:
            filtered_entries = []
            
            for entry in reversed(self.entries):  # Most recent first
                # Apply filters
                if user_id and entry["user_id"] != user_id:
                    continue
                if tool_name and entry["tool_name"] != tool_name:
                    continue
                if since:
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if entry_time < since:
                        continue
                
                filtered_entries.append(entry)
                
                if len(filtered_entries) >= limit:
                    break
            
            return filtered_entries


class AuthorizedToolWrapper:
    """Wraps tools with authorization checks."""
    
    def __init__(
        self,
        tool: Tool,
        auth_provider: AuthProvider,
        acl: AccessControlList,
        audit_logger: AuditLogger
    ):
        """
        Initialize authorized tool wrapper.
        
        Args:
            tool: Tool to wrap
            auth_provider: Authentication provider
            acl: Access control list
            audit_logger: Audit logger
        """
        self.tool = tool
        self.auth_provider = auth_provider
        self.acl = acl
        self.audit_logger = audit_logger
    
    async def execute(
        self,
        args: Dict[str, Any],
        auth_context: Dict[str, Any]
    ) -> ToolResult:
        """
        Execute tool with authorization checks.
        
        Args:
            args: Tool arguments
            auth_context: Authentication context (token, api_key, etc.)
            
        Returns:
            Tool execution result
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If authorization fails
        """
        # Authenticate user
        user = await self._authenticate(auth_context)
        if not user:
            await self.audit_logger.log_access(
                User("anonymous", "anonymous", [Role.GUEST]),
                self.tool.name,
                "execute",
                False,
                {"error": "authentication_failed"}
            )
            raise AuthenticationError("Authentication failed")
        
        # Check authorization
        if not self.acl.check_permission(user, self.tool.name, Permission.EXECUTE):
            await self.audit_logger.log_access(
                user,
                self.tool.name,
                "execute",
                False,
                {"error": "authorization_failed"}
            )
            raise AuthorizationError(f"User {user.username} not authorized to execute {self.tool.name}")
        
        # Execute tool
        try:
            result = await self.tool.execute_with_timeout(args)
            
            # Log successful execution
            await self.audit_logger.log_access(
                user,
                self.tool.name,
                "execute",
                True,
                {
                    "execution_time": result.execution_time,
                    "status": result.status.value
                }
            )
            
            return result
            
        except Exception as e:
            # Log failed execution
            await self.audit_logger.log_access(
                user,
                self.tool.name,
                "execute",
                False,
                {"error": str(e)}
            )
            raise
    
    async def get_schema(self, auth_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get tool schema with authorization check.
        
        Args:
            auth_context: Authentication context
            
        Returns:
            Tool schema
        """
        user = await self._authenticate(auth_context)
        if not user:
            raise AuthenticationError("Authentication required to view tool schema")
        
        if not self.acl.check_permission(user, self.tool.name, Permission.READ):
            raise AuthorizationError(f"User {user.username} not authorized to read {self.tool.name} schema")
        
        await self.audit_logger.log_access(user, self.tool.name, "read_schema", True)
        return self.tool.get_schema()
    
    async def _authenticate(self, auth_context: Dict[str, Any]) -> Optional[User]:
        """Authenticate user from context."""
        if "token" in auth_context:
            return await self.auth_provider.validate_token(auth_context["token"])
        elif "api_key" in auth_context:
            return await self.auth_provider.authenticate({"api_key": auth_context["api_key"]})
        elif "username" in auth_context and "password" in auth_context:
            return await self.auth_provider.authenticate({
                "username": auth_context["username"],
                "password": auth_context["password"]
            })
        return None


class AuthManager:
    """Central authentication and authorization manager."""
    
    def __init__(self, auth_provider: Optional[AuthProvider] = None):
        """
        Initialize auth manager.
        
        Args:
            auth_provider: Authentication provider (creates default if None)
        """
        self.auth_provider = auth_provider or SimpleAuthProvider()
        self.acl = AccessControlList()
        self.audit_logger = AuditLogger()
        self.wrapped_tools: Dict[str, AuthorizedToolWrapper] = {}
    
    def wrap_tool(self, tool: Tool) -> AuthorizedToolWrapper:
        """
        Wrap a tool with authorization.
        
        Args:
            tool: Tool to wrap
            
        Returns:
            Authorized tool wrapper
        """
        wrapper = AuthorizedToolWrapper(
            tool,
            self.auth_provider,
            self.acl,
            self.audit_logger
        )
        self.wrapped_tools[tool.name] = wrapper
        return wrapper
    
    def set_tool_permissions(
        self,
        tool_name: str,
        role_permissions: Dict[Role, Set[Permission]]
    ) -> None:
        """Set permissions for a tool."""
        self.acl.set_tool_permissions(tool_name, role_permissions)
    
    def create_user(
        self,
        username: str,
        roles: List[Role],
        permissions: Optional[Set[str]] = None
    ) -> User:
        """Create a new user."""
        if isinstance(self.auth_provider, SimpleAuthProvider):
            return self.auth_provider.create_user(username, roles, permissions)
        else:
            raise NotImplementedError("User creation not supported by this auth provider")
    
    async def get_audit_log(self, **kwargs) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        return await self.audit_logger.get_audit_log(**kwargs)


# Global auth manager instance
_global_auth_manager = AuthManager()


def get_global_auth_manager() -> AuthManager:
    """Get the global auth manager instance."""
    return _global_auth_manager