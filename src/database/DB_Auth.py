from typing import TypeVar

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declared_attr, relationship

from database.AbstractDatabaseEntity import (
    BaseMixin,
    ImageMixin,
    ParentMixin,
    UpdateMixin,
)
from database.Base import Base
from database.StaticPermissions import can_manage_permissions
from lib.Environment import env

T = TypeVar("T")


class User(Base, BaseMixin, UpdateMixin, ImageMixin):
    """
    Check if a user has read access to a user record.

    IMPORTANT: User records have special access rules:
    1. Users can always see themselves
    2. Users can see other users in teams they have access to
    3. ROOT_ID and SYSTEM_ID can see all users
    4. Records created by ROOT_ID can only be accessed by ROOT_ID

    This behavior differs from other entities where explicit permissions
    are required to see records created by other users.

    Args:
        user_id: The ID of the user requesting access
        record: The User record to check
        db: Database session
        minimum_role: Minimum role required (if applicable)
        referred: Whether this check is part of a referred access check

    Returns:
        bool: True if access is granted, False otherwise
    """

    __tablename__ = "users"
    __table_args__ = {
        "comment": "Core user accounts for authentication and identity management"
    }

    email = Column(
        String,
        unique=True,
        comment="User's email address used for login and communications",
    )
    username = Column(
        String,
        unique=True,
        nullable=True,
        comment="Optional username that can be used for login instead of email",
    )
    display_name = Column(
        String,
        nullable=True,
        comment="User's preferred display name shown in the interface",
    )
    first_name = Column(
        String, default="", nullable=True, comment="User's first/given name"
    )
    last_name = Column(
        String, default="", nullable=True, comment="User's last/family name"
    )
    mfa_count = Column(
        Integer, default=1, comment="Number of MFA methods required for authentication"
    )
    active = Column(
        Boolean,
        default=True,
        comment="Whether this user account is active and allowed to log in",
    )
    # TODO #44 Get the base domain from APP_URI (no https, paths or subdomains).
    import re

    url = re.sub(r"^\w+://", "", env("APP_URI")) if env("APP_URI") else ""
    hostname = url.split("/")[0] if url else ""
    match = (
        re.search(r"([^.]+\.(?:com|org|net|gov|edu|co\.\w{2}|[a-z]{2,}))$", hostname)
        if hostname
        else None
    )
    match = match.group(1) if match else hostname

    seed_list = [
        {
            "id": env("ROOT_ID"),
            "email": f"root@{match}",
        },
        {
            "id": env("SYSTEM_ID"),
            "email": f"system@{match}",
        },
        {
            "id": env("TEMPLATE_ID"),
            "email": f"template@{match}",
        },
    ]

    @classmethod
    def user_has_read_access(
        cls, user_id, record, db, minimum_role=None, referred=False
    ):
        """
        Check if a user has read access to a user record.

        Args:
            user_id: The ID of the user requesting access
            record: The User record ID or object to check
            db: Database session
            minimum_role: Minimum role required (if applicable)
            referred: Whether this check is part of a referred access check

        Returns:
            bool: True if access is granted, False otherwise
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            check_permission,
            is_root_id,
            is_system_user_id,
            is_template_id,
        )

        # Get the record if an ID was passed
        if isinstance(record, str):
            record_obj = db.query(cls).filter(cls.id == record).first()
            if record_obj is None:
                return False
        else:
            record_obj = record

        # ROOT_ID can access everything
        if is_root_id(user_id):
            return True

        # Check for deleted records - only ROOT_ID can see them
        if hasattr(record_obj, "deleted_at") and record_obj.deleted_at is not None:
            return False

        # Users can see their own records
        if user_id == record_obj.id:
            return True

        # Check for records created by ROOT_ID - only ROOT_ID can access them
        # if hasattr(
        #     record_obj, "created_by_user_id"
        # ) and record_obj.created_by_user_id == env("ROOT_ID"):
        #     return is_root_id(user_id)  # Only ROOT_ID can see these

        # Check for records created by SYSTEM_ID
        if hasattr(
            record_obj, "created_by_user_id"
        ) and record_obj.created_by_user_id == env("SYSTEM_ID"):
            # For view operations, regular users can view
            if minimum_role is None or minimum_role == "user":
                return True
            # For admin operations, only ROOT_ID and SYSTEM_ID
            return is_root_id(user_id) or is_system_user_id(user_id)

        # Check for records created by TEMPLATE_ID
        if hasattr(
            record_obj, "created_by_user_id"
        ) and record_obj.created_by_user_id == env("TEMPLATE_ID"):
            # For view/copy/execute/share operations, all users can access
            if minimum_role is None or minimum_role == "user":
                return True
            # For edit/delete, only ROOT_ID and SYSTEM_ID can modify
            return is_root_id(user_id) or is_system_user_id(user_id)

        # For direct record-level access checks, use standard permission system
        if not referred:
            # Check if created by this user
            if (
                hasattr(record_obj, "created_by_user_id")
                and record_obj.created_by_user_id == user_id
            ):
                return True

            # Use standard permission system
            result, _ = check_permission(
                user_id,
                cls,
                record_obj.id,
                db,
                PermissionType.VIEW if minimum_role is None else None,
                minimum_role=minimum_role,
            )
            return result == PermissionResult.GRANTED

        return False

    @classmethod
    def user_has_admin_access(cls, user_id, id, db):
        """
        Check if user has admin access to a specific record.
        Admin access requires EDIT permission.

        Args:
            user_id: The ID of the user requesting access
            id: The ID of the record to check
            db: Database session

        Returns:
            bool: True if admin access is granted, False otherwise
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            check_permission,
            is_root_id,
            is_system_user_id,
        )

        # Root has admin access to everything
        if is_root_id(user_id):
            return True

        # Get the record to check creator and deletion rules
        record = None
        if isinstance(id, str):
            record = db.query(cls).filter(cls.id == id).first()
            if record is None:
                return False

        # Check if the record was created by ROOT_ID - only ROOT_ID can access
        if hasattr(record, "created_by_user_id") and record.created_by_user_id == env(
            "ROOT_ID"
        ):
            return is_root_id(user_id)  # Only ROOT_ID can access

        # Check if the record was created by TEMPLATE_ID - only system users can modify
        if hasattr(record, "created_by_user_id") and record.created_by_user_id == env(
            "TEMPLATE_ID"
        ):
            return is_root_id(user_id) or is_system_user_id(user_id)

        # For User model, only allow admin access to your own record
        if id == user_id:
            return True

        # Otherwise use permission system
        result, _ = check_permission(user_id, cls, id, db, PermissionType.EDIT)
        return result == PermissionResult.GRANTED

    @classmethod
    def user_has_all_access(cls, user_id, id, db):
        """
        Override user_has_all_access for User model to enforce specific rules for
        DELETE and SHARE permissions.

        Args:
            user_id: ID of the requesting user
            id: ID of the User record
            db: Database session

        Returns:
            bool: True if user has all access, False otherwise
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            check_permission,
            is_root_id,
        )

        # ROOT_ID has all access
        if is_root_id(user_id):
            return True

        # Get the record
        user_record = None
        if isinstance(id, str):
            user_record = db.query(cls).filter(cls.id == id).first()
            if user_record is None:
                return False

        # Special checks for ROOT_ID created records
        if hasattr(
            user_record, "created_by_user_id"
        ) and user_record.created_by_user_id == env("ROOT_ID"):
            return is_root_id(user_id)

        # Check explicit permissions
        result, _ = check_permission(user_id, cls, id, db, PermissionType.SHARE)
        return result == PermissionResult.GRANTED


class UserRefMixin:
    @declared_attr
    def user_id(cls):
        return cls.create_foreign_key(User, nullable=False)

    @declared_attr
    def user(cls):
        return relationship(
            User.__name__,
            backref=cls.__tablename__,
        )


class _UserOptional(UserRefMixin):
    @declared_attr
    def user_id(cls):
        return cls.create_foreign_key(User)  # nullable=True by default


UserRefMixin.Optional = _UserOptional

# User.merges_initiated = relationship(
#     UserMerge.__name__,
#     foreign_keys=[UserMerge.initiating_user_id],
#     backref="initiating_user",
# )

# User.merges_targetted = relationship(
#     UserMerge.__name__,
#     foreign_keys=[UserMerge.target_user_id],
#     backref="target_user",
# )


class UserCredential(Base, BaseMixin, UpdateMixin, UserRefMixin.Optional):
    __tablename__ = "user_credentials"
    __table_args__ = {
        "comment": "Stores user password hashes and tracks password change history"
    }

    password_hash = Column(
        String, nullable=True, comment="Bcrypt hash of the user's password"
    )
    password_salt = Column(
        String, nullable=True, comment="Salt used for password hashing"
    )
    password_changed = Column(
        DateTime,
        nullable=True,
        comment="When this password was changed; null indicates current password",
    )


class UserRecoveryQuestion(Base, BaseMixin, UpdateMixin, UserRefMixin.Optional):
    __tablename__ = "user_recovery_questions"
    __table_args__ = {
        "comment": "Security questions for account recovery when a user forgets their password"
    }

    question = Column(String, nullable=False, comment="Security question text")
    answer = Column(
        String, nullable=False, comment="Hashed answer to the security question"
    )


class Team(Base, BaseMixin, UpdateMixin, ParentMixin, ImageMixin):
    __tablename__ = "teams"
    __table_args__ = {
        "comment": "Teams to which users can belong",
    }
    name = Column(
        String,
        nullable=False,
        comment="Human-readable team name",
    )
    description = Column(
        String,
        nullable=True,
        comment="Description of the team's purpose",
    )
    encryption_key = Column(
        String,
        nullable=False,
        default="",
        comment="Encryption key for team resources",
    )
    seed_list = [
        {
            "id": "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF",
            "name": "System",
            "parent_id": None,
            "encryption_key": "",
        }
    ]

    @classmethod
    def user_has_read_access(cls, user_id, id, db, referred=False):
        """
        Check if user has read access to a team.
        Read access requires VIEW permission.

        Args:
            user_id: The ID of the user to check
            id: The team ID to check
            db: Database session
            referred: Whether this is a referred check

        Returns:
            bool: True if read access is granted, False otherwise
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            check_permission,
            is_root_id,
            is_system_user_id,
        )

        # ROOT_ID has read access to everything
        if is_root_id(user_id):
            return True

        # SYSTEM_ID has read access to all teams
        if is_system_user_id(user_id):
            return True

        # Get the team to check creator and deletion rules
        team = None
        if isinstance(id, str):
            team = db.query(cls).filter(cls.id == id).first()
            if not team:
                return False

            # Check if record is deleted - only ROOT_ID can see
            if hasattr(team, "deleted_at") and team.deleted_at is not None:
                return False

            # Teams created by ROOT_ID can only be viewed by ROOT_ID
            if team.created_by_user_id == env("ROOT_ID"):
                return False

            # Teams created by TEMPLATE_ID can be viewed by everyone
            if team.created_by_user_id == env("TEMPLATE_ID"):
                return True

        # For non-referred checks, check read permissions
        if not referred:
            result, _ = check_permission(user_id, cls, id, db, PermissionType.VIEW)
            return result == PermissionResult.GRANTED

        return False


class TeamRefMixin:
    @declared_attr
    def team_id(cls):
        # By default the foreign key is required (nullable=False)
        return cls.create_foreign_key(Team, nullable=False)

    @declared_attr
    def team(cls):
        return relationship(
            Team.__name__,
            backref=cls.__tablename__,
        )


class _TeamOptional(TeamRefMixin):
    @declared_attr
    def team_id(cls):
        return cls.create_foreign_key(Team)


TeamRefMixin.Optional = _TeamOptional


class TeamMetadata(Base, BaseMixin, UpdateMixin, TeamRefMixin):
    __tablename__ = "team_metadata"
    __table_args__ = {"comment": "Key-value pairs storing custom metadata for teams"}

    key = Column(String, nullable=False, comment="Metadata key name")
    value = Column(String, nullable=True, comment="Metadata value")


class Role(Base, BaseMixin, UpdateMixin, TeamRefMixin.Optional, ParentMixin):
    __tablename__ = "roles"
    __table_args__ = {
        "comment": "Permission roles that define what actions users can perform"
    }
    name = Column(String, nullable=False, comment="Unique role identifier/code")
    friendly_name = Column(
        String, nullable=True, comment="Human-readable display name for the role"
    )
    mfa_count = Column(
        Integer,
        default=1,
        comment="Minimum number of MFA verifications required for this role",
    )
    password_change_frequency_days = Column(
        Integer,
        default=365,
        comment="How often users with this role must change their password",
    )
    expires_at = Column(
        DateTime, nullable=True, comment="The expiration time of the role"
    )
    seed_id = "TEMPLATE_ID"
    seed_list = [
        {
            "id": env("USER_ROLE_ID"),
            "name": "user",
            "friendly_name": "User",
            "parent_id": None,
        },
        {
            "id": env("ADMIN_ROLE_ID"),
            "name": "admin",
            "friendly_name": "Admin",
            "parent_id": env("USER_ROLE_ID"),
        },
        {
            "id": env("SUPERADMIN_ROLE_ID"),
            "name": "superadmin",
            "friendly_name": "Superadmin",
            "parent_id": env("ADMIN_ROLE_ID"),
        },
    ]


class RoleRefMixin:
    @declared_attr
    def role_id(cls):
        # By default the foreign key is required (nullable=False)
        return cls.create_foreign_key(Role, nullable=False)

    @declared_attr
    def role(cls):
        return relationship(
            Role.__name__,
            backref=cls.__tablename__,
        )


class _RoleOptional(RoleRefMixin):
    @declared_attr
    def role_id(cls):
        return cls.create_foreign_key(Role)  # nullable=True by default


RoleRefMixin.Optional = _RoleOptional


class Permission(
    Base,
    BaseMixin,
    UpdateMixin,
    UserRefMixin.Optional,
    TeamRefMixin.Optional,
    RoleRefMixin.Optional,
):
    __tablename__ = "permissions"
    __table_args__ = {
        "comment": "Fine-grained permissions for specific resources and actions"
    }

    # To apply SHARE permissions on the target resource for permission management
    create_permission_reference = "resource"

    resource_type = Column(
        String, nullable=False, comment="Type of resource being granted permissions for"
    )
    resource_id = Column(String, nullable=False, comment="ID of the specific resource")
    expires_at = Column(
        DateTime, nullable=True, comment="The expiration time of the permission"
    )
    can_view = Column(Boolean, default=False, comment="Permission to view the resource")
    can_execute = Column(
        Boolean, default=False, comment="Permission to execute or run the resource"
    )
    can_copy = Column(
        Boolean, default=False, comment="Permission to duplicate the resource"
    )
    can_edit = Column(
        Boolean, default=False, comment="Permission to modify the resource"
    )
    can_delete = Column(
        Boolean, default=False, comment="Permission to delete the resource"
    )
    can_share = Column(
        Boolean, default=False, comment="Permission to share the resource with others"
    )

    @classmethod
    def user_can_create(cls, user_id, db, **kwargs):
        """
        Check if a user can create a permission record.
        Users need SHARE permission on the resource they're creating a permission for.
        """
        from database.StaticPermissions import (
            can_manage_permissions,
            is_root_id,
            is_system_user_id,
        )

        # Root and system users can create permissions
        if is_root_id(user_id) or is_system_user_id(user_id):
            return True

        # Check if user can manage permissions for this resource
        resource_type = kwargs.get("resource_type")
        resource_id = kwargs.get("resource_id")

        if not resource_type or not resource_id:
            return False

        # Check if the user has permission to manage permissions on this resource
        can_manage, _ = can_manage_permissions(user_id, resource_type, resource_id, db)
        return can_manage

    @classmethod
    def user_has_admin_access(cls, user_id, id, db):
        """
        Overrides the default admin access check for Permission records.
        Allow users with explicit permission to edit this record or with SHARE access to the target resource.
        """
        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            check_permission,
            is_root_id,
            is_system_user_id,
        )

        # Root and system users always have admin access
        if is_root_id(user_id) or is_system_user_id(user_id):
            return True

        # First check standard permission on this record
        result, _ = check_permission(user_id, cls, id, db, PermissionType.EDIT)
        if result == PermissionResult.GRANTED:
            return True

        # If that fails, check if the user can manage permissions for the target resource
        permission = db.query(cls).filter(cls.id == id).first()
        if permission:
            can_manage, _ = can_manage_permissions(
                user_id, permission.resource_type, permission.resource_id, db
            )
            return can_manage

        return False

    @classmethod
    def update(
        cls,
        requester_id,
        db,
        new_properties,
        return_type="db",
        filters=[],
        fields=[],
        override_dto=None,
        check_permissions=True,
        **kwargs,
    ):
        """
        Override the default update method to allow users with SHARE permission
        on the target resource to update permission records, even if created by SYSTEM_ID.
        """
        from fastapi import HTTPException
        from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

        from database.StaticPermissions import (
            PermissionResult,
            PermissionType,
            is_root_id,
            is_system_user_id,
        )

        # Build query to find the entity without permission filters first
        query = db.query(cls)
        for filter_condition in filters:
            query = query.filter(filter_condition)
        for key, value in kwargs.items():
            query = query.filter(getattr(cls, key) == value)

        try:
            entity = query.one()
        except NoResultFound:
            raise HTTPException(status_code=404, detail=f"{cls.__name__} not found")
        except MultipleResultsFound:
            raise HTTPException(
                status_code=500, detail=f"Multiple {cls.__name__} found"
            )

        # Check if user has admin access to this permission record
        if not cls.user_has_admin_access(requester_id, entity.id, db):
            raise HTTPException(
                status_code=403, detail=f"Not authorized to update this {cls.__name__}"
            )

        # Now use the standard update logic but without the system user checks
        from database.AbstractDatabaseEntity import db_to_return_type, validate_fields
        from lib.Environment import env

        # Validate fields parameter
        validate_fields(cls, fields)

        # Ensure created_by_user_id and id cannot be modified
        updated = dict(new_properties)
        if "created_by_user_id" in updated:
            del updated["created_by_user_id"]
        if "id" in updated:
            del updated["id"]

        # Set updated_by_user_id
        if hasattr(cls, "updated_by_user_id"):
            updated["updated_by_user_id"] = requester_id

        # Apply updates
        for key, value in updated.items():
            setattr(entity, key, value)

        # Commit changes
        db.commit()
        db.refresh(entity)

        # Convert to requested return type
        return db_to_return_type(entity, return_type, override_dto, fields)

    @classmethod
    def create(
        cls, requester_id, db, return_type="db", fields=[], override_dto=None, **kwargs
    ):
        """
        Override the default create method to allow users with SHARE permission
        on the target resource to create permission records.
        """
        from fastapi import HTTPException
        from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

        # Validate fields parameter
        from database.AbstractDatabaseEntity import validate_fields
        from database.StaticPermissions import is_root_id, is_system_user_id

        validate_fields(cls, fields)

        # If user is ROOT_ID or SYSTEM_ID, they can create permissions
        if is_root_id(requester_id) or is_system_user_id(requester_id):
            # Use standard create path for system users
            return super().create(
                requester_id, db, return_type, fields, override_dto, **kwargs
            )

        # Otherwise, check if they can manage permissions for the target resource
        resource_type = kwargs.get("resource_type")
        resource_id = kwargs.get("resource_id")

        if not resource_type or not resource_id:
            raise HTTPException(
                status_code=400,
                detail="Missing resource_type or resource_id for permission",
            )

        # Create a copy of kwargs without user_id to avoid conflict
        check_kwargs = kwargs.copy()
        if "user_id" in check_kwargs:
            check_kwargs.pop("user_id")

        # Check if user can manage permissions for this resource
        if not cls.user_can_create(requester_id, db, **check_kwargs):
            raise HTTPException(
                status_code=403,
                detail=f"Not authorized to create permissions for {resource_type} {resource_id}",
            )

        # If they can create, proceed with creation
        # Generate a UUID if not provided
        data = dict(kwargs)
        if "id" not in data:
            import uuid

            data["id"] = str(uuid.uuid4())

        # Add created_by_user_id if the entity has this column
        data["created_by_user_id"] = requester_id

        # Create the entity
        entity = cls(**data)
        db.add(entity)
        db.commit()
        db.refresh(entity)

        # Convert to requested return type
        from database.AbstractDatabaseEntity import db_to_return_type

        return db_to_return_type(entity, return_type, override_dto, fields)


class UserTeam(Base, BaseMixin, UpdateMixin, UserRefMixin, TeamRefMixin, RoleRefMixin):
    __tablename__ = "user_teams"
    __table_args__ = {
        "comment": "Junction table linking users to teams with assigned roles"
    }

    enabled = Column(
        Boolean, default=True, comment="Whether this user-team link is currently active"
    )
    expires_at = Column(
        DateTime,
        nullable=True,
        comment="When this user-team link expires; null for no expiry",
    )


class Invitation(
    Base, BaseMixin, UpdateMixin, UserRefMixin, TeamRefMixin, RoleRefMixin
):
    __tablename__ = "invitations"
    __table_args__ = {
        "comment": "Invitations to join teams, can be direct or via invitation code"
    }

    code = Column(
        String,
        nullable=True,
        comment="Invitation code for public sharing; null for direct invitations",
    )
    max_uses = Column(
        Integer,
        nullable=True,
        comment="Maximum number of times this invitation can be used; null for unlimited",
    )
    expires_at = Column(
        DateTime,
        nullable=True,
        comment="When this invitation expires; null for no expiry",
    )


class InvitationInvitee(Base, BaseMixin, UpdateMixin, UserRefMixin):
    __tablename__ = "invitation_invitees"
    __table_args__ = {"comment": "Tracks specific individuals invited to join a team"}

    email = Column(String, nullable=False, comment="Email address of the invitee")
    is_accepted = Column(
        Boolean, default=False, comment="Whether the invitation has been accepted"
    )
    accepted_at = Column(
        DateTime, nullable=True, comment="When the invitation was accepted"
    )

    @declared_attr
    def invitation_id(cls):
        return cls.create_foreign_key(
            Invitation,
            nullable=False,
            comment="Reference to the invitation sent to this invitee",
        )

    invitation = relationship(Invitation.__name__, backref="invitees")


class UserMetadata(Base, BaseMixin, UpdateMixin, UserRefMixin):
    __tablename__ = "user_metadata"
    __table_args__ = {"comment": "Key-value pairs storing custom metadata for users"}

    key = Column(String, nullable=False, comment="Metadata key name")
    value = Column(String, nullable=True, comment="Metadata value")


class FailedLoginAttempt(Base, BaseMixin, UserRefMixin.Optional):
    __tablename__ = "failed_login_attempts"
    __table_args__ = {
        "comment": "Records of failed login attempts for security monitoring and lockout enforcement"
    }

    ip_address = Column(
        String,
        default="",
        nullable=True,
        comment="IP address from which the failed login attempt originated",
    )


class AuthSession(Base, BaseMixin, UpdateMixin, UserRefMixin):
    __tablename__ = "auth_sessions"
    __table_args__ = {
        "comment": "Active user authentication sessions and related metadata"
    }

    # JWT-related fields
    session_key = Column(
        String,
        nullable=False,
        unique=True,
        comment="Unique session identifier used in JWT jti claim",
    )
    jwt_issued_at = Column(DateTime, nullable=False, comment="When the JWT was issued")

    # We still track refresh tokens separately
    refresh_token_hash = Column(
        String,
        nullable=True,
        comment="Hash of refresh token if refresh mechanism is enabled",
    )

    # Device information
    device_type = Column(
        String,
        nullable=True,
        comment="Type of device used for authentication (mobile, desktop, etc.)",
    )
    device_name = Column(
        String, nullable=True, comment="Name of the device if provided"
    )
    browser = Column(
        String, nullable=True, comment="Browser information from user agent"
    )

    # Status
    is_active = Column(
        Boolean, default=True, comment="Whether this session is currently active"
    )
    last_activity = Column(
        DateTime, nullable=False, comment="Timestamp of last activity in this session"
    )
    expires_at = Column(DateTime, nullable=False, comment="When this session expires")
    revoked = Column(
        Boolean,
        default=False,
        comment="Whether this session has been explicitly revoked",
    )

    # Risk assessment
    trust_score = Column(
        Integer, default=50, comment="Trust level of this session (0-100)"
    )
    requires_verification = Column(
        Boolean, default=False, comment="Whether additional verification is required"
    )


class RateLimitPolicy(
    Base,
    BaseMixin,
    UpdateMixin,
    UserRefMixin.Optional,
    RoleRefMixin.Optional,
    TeamRefMixin.Optional,
):
    __tablename__ = "rate_limit_policies"
    system = True
    name = Column(String, nullable=False)
    resource_pattern = Column(String, nullable=False)  # e.g., "api/v1/users/*"
    window_seconds = Column(Integer, nullable=False)  # Time window in seconds
    max_requests = Column(Integer, nullable=False)  # Max requests in window
    scope = Column(String, default="user")  # 'key', 'user', 'team', 'ip', 'global'
