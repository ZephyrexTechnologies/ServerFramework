from cryptography.fernet import Fernet
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declared_attr, relationship

from database.Base import Base
from database.Mixins import BaseMixin, ImageMixin, ParentMixin, UpdateMixin
from lib.Environment import env


class User(Base, BaseMixin, UpdateMixin, ImageMixin):
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
    # TODO Get the base domain from APP_URI (no https, paths or subdomains).
    seed_list = [
        {
            "id": env("ROOT_ID"),
            "email": f"root@{env('APP_URI')}",
        },
        {
            "id": env("SYSTEM_ID"),
            "email": f"system@{env('APP_URI')}",
        },
        {
            "id": env("TEMPLATE_ID"),
            "email": f"template@{env('APP_URI')}",
        },
    ]


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
        "comment": "Organizations or groups of users that collaborate together with shared permissions"
    }

    name = Column(String, comment="Team name displayed in the UI")
    description = Column(
        String,
        nullable=True,
        comment="Optional description of the team and its purpose",
    )
    encryption_key = Column(
        String,
        nullable=False,
        default=lambda: Fernet.generate_key().decode(),
        comment="Encryption key used for securing team-specific data",
    )
    token = Column(
        String, nullable=True, comment="Public token for external integrations"
    )
    training_data = Column(
        String,
        nullable=True,
        comment="Custom training data for team-specific AI models",
    )

    @classmethod
    def user_can_create(cls, user_id, db, **kwargs):
        # Allow any authenticated user to create a team
        return True


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
    seed_list = [
        {
            "id": "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF",
            "name": "user",
            "friendly_name": "User",
            "parent_id": None,
        },
        {
            "id": "FFFFFFFF-FFFF-FFFF-AAAA-FFFFFFFFFFFF",
            "name": "admin",
            "friendly_name": "Admin",
            "parent_id": "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF",
        },
        {
            "id": "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
            "name": "superadmin",
            "friendly_name": "Superadmin",
            "parent_id": "FFFFFFFF-FFFF-FFFF-AAAA-FFFFFFFFFFFF",
        },
    ]

    @classmethod
    def user_has_read_access(cls, user_id, id, db, minimum_role=None, referred=False):
        # Get the record first
        record = db.query(cls).filter(cls.id == id).first()
        if not record:
            return False

        # If the record's team_id is null, it's a system role and anyone can read it
        if record.team_id is None:
            return True

        # Otherwise, evaluate BaseMixin's user_has_read_access
        return BaseMixin.user_has_read_access.__func__(
            cls, user_id, id, db, minimum_role, referred
        )


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


class UserTeam(Base, BaseMixin, UpdateMixin, UserRefMixin, TeamRefMixin, RoleRefMixin):
    __tablename__ = "user_teams"
    __table_args__ = {
        "comment": "Junction table linking users to teams with assigned roles"
    }

    enabled = Column(
        Boolean, default=True, comment="Whether this user-team relationship is active"
    )


class Invitation(Base, BaseMixin, UpdateMixin, TeamRefMixin, RoleRefMixin):
    __tablename__ = "invitations"
    __table_args__ = {
        "comment": "Invitations to join teams, can be direct or via invitation code"
    }

    code = Column(
        String,
        nullable=True,
        comment="Invitation code for public sharing; null for direct invitations",
    )

    @declared_attr
    def inviter_id(cls):
        return cls.create_foreign_key(User, comment="User who created this invitation")

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

    inviter = relationship(User.__name__)


class InvitationInvitee(Base, BaseMixin, UpdateMixin):
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

    @declared_attr
    def invitee_user_id(cls):
        return cls.create_foreign_key(
            User,
            nullable=False,
            comment="User who accepted the invitation, if accepted",
        )

    invitee_user = relationship(User.__name__, backref="invitations")


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
