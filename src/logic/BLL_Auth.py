import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.Base import get_session
from database.DB_Auth import (
    AuthSession,
    FailedLoginAttempt,
    Invitation,
    InvitationInvitee,
    Permission,
    Role,
    Team,
    TeamMetadata,
    User,
    UserCredential,
    UserMetadata,
    UserRecoveryQuestion,
    UserTeam,
)
from lib.Dependencies import jwt
from lib.Environment import env
from logic.AbstractBLLManager import (
    AbstractBLLManager,
    BaseMixinModel,
    DateSearchModel,
    ImageMixinModel,
    NameMixinModel,
    NumericalSearchModel,
    ParentMixinModel,
    StringSearchModel,
    UpdateMixinModel,
)


class UserModel(BaseMixinModel, UpdateMixinModel, ImageMixinModel.Optional):
    model_config = {"extra": "ignore", "populate_by_name": True}
    email: Optional[str] = Field(description="User's email address")
    username: Optional[str] = Field(description="User's username")
    display_name: Optional[str] = Field(description="User's display name")
    first_name: Optional[str] = Field(description="User's first name")
    last_name: Optional[str] = Field(description="User's last name")
    mfa_count: Optional[int] = Field(description="Number of MFA verifications required")
    active: Optional[bool] = Field(description="Whether the user is active")

    class ReferenceID:
        user_id: str = Field(..., description="The ID of the related user")

        class Optional:
            user_id: Optional[str] = None

        class Search:
            user_id: Optional[StringSearchModel] = None

    class Create(BaseModel, ImageMixinModel.Optional):
        email: str = Field(..., description="User's email address")
        username: Optional[str] = Field(None, description="User's username")
        display_name: Optional[str] = Field(None, description="User's display name")
        first_name: Optional[str] = Field(None, description="User's first name")
        last_name: Optional[str] = Field(None, description="User's last name")
        password: Optional[str] = Field(None, description="User's password")

        @model_validator(mode="after")
        def validate_email(self):
            if "@" not in self.email:
                raise ValueError("Invalid email format")
            return self

    class Update(BaseModel, ImageMixinModel.Optional):
        email: Optional[str] = Field(None, description="User's email address")
        username: Optional[str] = Field(None, description="User's username")
        display_name: Optional[str] = Field(None, description="User's display name")
        first_name: Optional[str] = Field(None, description="User's first name")
        last_name: Optional[str] = Field(None, description="User's last name")
        mfa_count: Optional[int] = Field(
            None, description="Number of MFA verifications required"
        )
        active: Optional[bool] = Field(None, description="Whether the user is active")

        @model_validator(mode="after")
        def validate_email(self):
            if self.email is not None and "@" not in self.email:
                raise ValueError("Invalid email format")
            return self

    class Search(BaseMixinModel.Search, ImageMixinModel.Search):
        email: Optional[StringSearchModel] = None
        username: Optional[StringSearchModel] = None
        display_name: Optional[StringSearchModel] = None
        first_name: Optional[StringSearchModel] = None
        last_name: Optional[StringSearchModel] = None
        active: Optional[bool] = None


class UserReferenceModel(UserModel.ReferenceID):
    user: Optional[UserModel] = None

    class Optional(UserModel.ReferenceID.Optional):
        user: Optional[UserModel] = None


class UserNetworkModel:
    class POST(BaseModel):
        user: UserModel.Create

    class PUT(BaseModel):
        user: UserModel.Update

    class SEARCH(BaseModel):
        user: UserModel.Search

    class ResponseSingle(BaseModel):
        user: UserModel

        @model_validator(mode="before")
        @classmethod
        def validate_partial_data(cls, data):
            # If we have a partial user dict, we only validate the fields that are present
            if (
                isinstance(data, dict)
                and "user" in data
                and isinstance(data["user"], dict)
            ):
                # Do nothing with the fields - keep them as they are
                # This effectively bypasses validation for missing fields
                pass
            return data

    class ResponsePlural(BaseModel):
        users: List[UserModel]

    class Login(BaseModel):
        email: str = Field(..., description="User's email or username")
        password: Optional[str] = Field(None, description="User's password")
        token: Optional[str] = Field(None, description="MFA token")


class UserManager(AbstractBLLManager):
    Model = UserModel
    ReferenceModel = UserReferenceModel
    NetworkModel = UserNetworkModel
    DBClass = User

    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        self._user_credentials = None
        self._user_metadata = None
        self._user_mfa_methods = None
        self._failed_logins = None
        self._user_teams = None
        self._user_session_manager = None

    def _register_search_transformers(self):
        self.register_search_transformer("name", self._transform_name_search)

    def _transform_name_search(self, value):
        if not value:
            return []

        search_value = f"%{value}%"
        return [
            or_(
                User.first_name.ilike(search_value),
                User.last_name.ilike(search_value),
                User.display_name.ilike(search_value),
                User.username.ilike(search_value),
            )
        ]

    @property
    def user_credentials(self):
        if self._user_credentials is None:
            self._user_credentials = UserCredentialManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                db=self.db,
            )
        return self._user_credentials

    @property
    def user_metadata(self):
        if self._user_metadata is None:
            self._user_metadata = UserMetadataManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                db=self.db,
            )
        return self._user_metadata

    @property
    def user_mfa_methods(self):
        if self._user_mfa_methods is None:
            from extensions.mfa.BLL_MFA import UserMFAMethodManager

            self._user_mfa_methods = UserMFAMethodManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                db=self.db,
            )
        return self._user_mfa_methods

    @property
    def failed_logins(self):
        if self._failed_logins is None:
            self._failed_logins = FailedLoginAttemptManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                db=self.db,
            )
        return self._failed_logins

    @property
    def user_teams(self):
        if self._user_teams is None:
            self._user_teams = UserTeamManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                db=self.db,
            )
        return self._user_teams

    @property
    def user_session_manager(self):
        if self._user_session_manager is None:
            self._user_session_manager = UserSessionManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                db=self.db,
            )
        return self._user_session_manager

    def createValidation(self, entity):
        """Validates the entity before creation"""
        if User.exists(requester_id=self.requester.id, db=self.db, email=entity.email):
            raise HTTPException(status_code=400, detail="Email already in use")

        if entity.username and User.exists(
            requester_id=self.requester.id, db=self.db, username=entity.username
        ):
            raise HTTPException(status_code=400, detail="Username already in use")

    def create(self, **kwargs):
        """Create a user with optional metadata"""
        # Extract metadata fields (non-model fields)
        password = kwargs.pop("password", None)
        if not password:
            raise HTTPException(status_code=400, detail="Password is required")

        metadata_fields = {}
        model_fields = {}

        # Get the model fields for comparison
        model_fields_set = set(self.Model.__annotations__.keys())
        for key, value in kwargs.items():
            if key in model_fields_set or key == "password":
                model_fields[key] = value
            else:
                metadata_fields[key] = value

        # Create the user
        user = super().create(**model_fields)

        # Create metadata if provided
        if metadata_fields and user:
            for key, value in metadata_fields.items():
                self.user_metadata.create(
                    user_id=user.id,
                    key=key,
                    value=str(value),
                )

        super().__init__(
            requester_id=user.id,
            target_user_id=user.id,
            target_team_id=self.target_team_id,
            db=self.db,
        )
        self.user_credentials.create(user_id=user.id, password=password)
        return user

    def update(self, id: str, **kwargs):
        """Update a user with optional metadata"""
        # Extract metadata fields (non-model fields)
        metadata_fields = {}
        model_fields = {}

        # Get the model fields for comparison
        model_fields_set = set(self.Model.Update.__annotations__.keys())
        for key, value in kwargs.items():
            if key in model_fields_set:
                model_fields[key] = value
            else:
                metadata_fields[key] = value

        # Update the user
        user = super().update(id, **model_fields)

        # Update metadata if provided
        if metadata_fields and user:
            existing_metadata = self.user_metadata.list(user_id=id)
            existing_metadata_dict = {item.key: item for item in existing_metadata}

            for key, value in metadata_fields.items():
                if key in existing_metadata_dict:
                    # Update existing metadata
                    self.user_metadata.update(
                        id=existing_metadata_dict[key].id,
                        value=str(value),
                    )
                else:
                    # Create new metadata
                    self.user_metadata.create(
                        user_id=id,
                        key=key,
                        value=str(value),
                    )

        return user

    @staticmethod
    def generate_jwt_token(user_id: str, email: str, expiration_hours: int = 24) -> str:
        """Generate a JWT token for authentication"""
        expiration = datetime.utcnow() + timedelta(hours=expiration_hours)
        payload = {
            "sub": user_id,
            "email": email,
            "exp": expiration,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, env("JWT_SECRET"), algorithm="HS256")

    @staticmethod
    def verify_token(token: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Verify a JWT token and return user information"""
        try:
            close_session = False
            if db is None:
                db = get_session()
                close_session = True

            try:
                payload = jwt.decode(token, env("JWT_SECRET"), algorithms=["HS256"])

                user = User.get(
                    requester_id=env("ROOT_ID"),
                    db=db,
                    id=payload["sub"],
                    return_type="dto",
                    override_dto=UserModel,
                )

                if not user.active:
                    raise HTTPException(status_code=401, detail="Inactive user")

                return True
            except Exception as e:
                raise HTTPException(
                    status_code=401, detail=f"Token verification failed: {str(e)}"
                )
            finally:
                if close_session:
                    db.close()

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            raise HTTPException(
                status_code=401, detail=f"Token verification failed: {str(e)}"
            )

    @staticmethod
    def auth(authorization: str = Header(None), request: Request = None) -> User:
        """Authenticate a user from Authorization header"""
        if not authorization:
            raise HTTPException(
                status_code=401, detail="Authorization header is missing!"
            )

        ip = None
        server = None
        if request:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                ip = forwarded_for.split(",")[0].strip()
            elif request.client:
                ip = request.client.host
            host = request.headers.get("Host")
            scheme = request.headers.get("X-Forwarded-Proto", "http")
            server = None
            if host:
                server = f"{scheme}://{host}"

        with get_session() as db:

            if authorization.startswith("Bearer"):
                # JWT Token authentication
                token = (
                    authorization.replace("Bearer ", "").replace("bearer ", "").strip()
                )

                if token == env("ROOT_API_KEY"):
                    return db.query(User).filter(User.id == env("ROOT_ID")).first()

                try:
                    # Regular JWT auth
                    payload = jwt.decode(
                        jwt=token,
                        key=env("JWT_SECRET"),
                        algorithms=["HS256"],
                        leeway=timedelta(minutes=5),
                        i=ip,
                        s=server,
                    )

                    user = db.query(User).filter(User.id == payload["sub"]).first()
                    if not user:
                        raise HTTPException(status_code=404, detail="User not found")

                    if not user.active:
                        raise HTTPException(
                            status_code=403, detail="User account is disabled"
                        )

                    return user
                except jwt.ExpiredSignatureError:
                    raise HTTPException(status_code=401, detail="Token has expired")
                except jwt.InvalidTokenError:
                    raise HTTPException(status_code=401, detail="Invalid token")

            elif authorization.startswith("Basic"):
                # Basic auth with username/email and password
                try:
                    import base64

                    auth_encoded = authorization.replace("Basic ", "").strip()
                    auth_decoded = base64.b64decode(auth_encoded).decode("utf-8")

                    if ":" not in auth_decoded:
                        raise HTTPException(
                            status_code=401, detail="Invalid authentication format"
                        )

                    identifier, password = auth_decoded.split(":", 1)

                    # Try to find user by email or username
                    user = (
                        db.query(User)
                        .filter(
                            or_(
                                User.email == identifier,
                                User.username == identifier,
                            )
                        )
                        .first()
                    )

                    if not user:
                        raise HTTPException(
                            status_code=401, detail="Invalid credentials"
                        )

                    if not user.active:
                        raise HTTPException(
                            status_code=403, detail="User account is disabled"
                        )

                    # Get current credential (password_changed is NULL for current password)
                    credentials = (
                        db.query(UserCredential)
                        .filter(
                            UserCredential.user_id == user.id,
                            UserCredential.password_changed == None,
                        )
                        .first()
                    )

                    if not credentials:
                        raise HTTPException(
                            status_code=401, detail="No valid credentials found"
                        )

                    # Check password
                    if not bcrypt.checkpw(
                        password.encode(), credentials.password_hash.encode()
                    ):
                        # Check if there is an older password that matches
                        old_credentials = (
                            db.query(UserCredential)
                            .filter(
                                UserCredential.user_id == user.id,
                                UserCredential.password_changed != None,
                            )
                            .order_by(UserCredential.password_changed.desc())
                            .first()
                        )

                        if old_credentials and bcrypt.checkpw(
                            password.encode(),
                            old_credentials.password_hash.encode(),
                        ):
                            change_date = old_credentials.password_changed.strftime(
                                "%Y-%m"
                            )
                            raise HTTPException(
                                status_code=401,
                                detail=f"Your password was changed during {change_date}.",
                            )
                        else:
                            raise HTTPException(
                                status_code=401, detail="Invalid credentials"
                            )

                    return user
                except Exception as e:
                    if isinstance(e, HTTPException):
                        raise e
                    raise HTTPException(status_code=401, detail="Authentication failed")
            else:
                raise HTTPException(
                    status_code=401, detail="Unsupported authorization method"
                )

    def verify_password(self, user_id: str, password: str) -> bool:
        """Verify a user's password"""
        credentials = UserCredential.list(
            requester_id=self.requester.id,
            db=self.db,
            user_id=user_id,
            filters=[UserCredential.password_changed == None],
        )

        if not credentials or not credentials[0].password_hash:
            return False

        try:
            return bcrypt.checkpw(
                password.encode(), credentials[0].password_hash.encode()
            )
        except Exception:
            return False

    def get_metadata(self) -> Dict[str, str]:
        """Get all metadata for the target user"""
        metadata_items = UserMetadata.list(
            requester_id=self.requester.id, db=self.db, user_id=self.target_user_id
        )
        return {item.key: item.value for item in metadata_items}

    @staticmethod
    def login(
        login_data: Dict[str, Any] = None,
        ip_address: str = None,
        req_uri: Optional[str] = None,
        authorization: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Process user login from various input methods"""
        if db is None:
            db = get_session()

        system_id = env("SYSTEM_ID")

        # Extract credentials from Basic Auth header if provided
        if authorization and authorization.startswith("Basic "):
            try:
                import base64

                auth_encoded = authorization.replace("Basic ", "").strip()
                auth_decoded = base64.b64decode(auth_encoded).decode("utf-8")

                if ":" not in auth_decoded:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid Authorization header, bad format for mode 'Basic'.",
                    )

                identifier, password = auth_decoded.split(":", 1)
                login_data = {"email": identifier, "password": password}
            except Exception:
                raise HTTPException(status_code=401, detail="Authentication failed.")

        if not login_data:
            raise HTTPException(status_code=400, detail="Invalid Authorization header.")

        login_model = UserNetworkModel.Login(**login_data)
        normalized_identifier = login_model.email.lower().strip()

        # Try to find user by email or username
        user = User.list(
            requester_id=env("ROOT_ID"),
            filters=[
                or_(
                    User.email == normalized_identifier,
                    User.username == normalized_identifier,
                )
            ],
        )
        if len(user) != 1:
            logging.warning("This should never have multiple users!")
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        user = user[0]

        # Check for too many failed login attempts
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        failed_login_count = FailedLoginAttempt.count(
            requester_id=user["id"],
            db=db,
            user_id=user["id"],
            filters=[FailedLoginAttempt.created_at >= one_hour_ago],
        )

        max_failed_attempts = 5
        if failed_login_count >= max_failed_attempts:
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Please try again later.",
            )

        # Check if user account is active
        if not user["active"]:
            FailedLoginAttempt.create(
                requester_id=user["id"],
                db=db,
                user_id=user["id"],
                ip_address=ip_address,
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Handle password-based login
        if login_model.password:
            credential = UserCredential.get(
                requester_id=user["id"],
                db=db,
                user_id=user["id"],
                filters=[UserCredential.password_changed == None],
            )

            if not bcrypt.checkpw(
                login_model.password.encode(), credential["password_hash"].encode()
            ):
                # Check if there is an older password that matches
                old_credentials = (
                    db.query(UserCredential)
                    .filter(
                        UserCredential.user_id == user["id"],
                        UserCredential.password_changed != None,
                    )
                    .order_by(UserCredential.password_changed.desc())
                    .first()
                )

                if old_credentials and bcrypt.checkpw(
                    login_model.password.encode(),
                    old_credentials.password_hash.encode(),
                ):
                    change_date = old_credentials.password_changed.strftime("%Y-%m")
                    raise HTTPException(
                        status_code=401,
                        detail=f"Your password was changed during {change_date}.",
                    )
                else:
                    FailedLoginAttempt.create(
                        requester_id=user["id"],
                        db=db,
                        user_id=user["id"],
                        ip_address=ip_address,
                    )
                    raise HTTPException(status_code=401, detail="Invalid credentials")

        # Handle MFA token login
        elif login_model.token:
            from extensions.mfa.BLL_MFA import UserMFAMethodManager

            mfa_methods = UserMFAMethod.list(
                requester_id=system_id,
                db=db,
                user_id=user.id,
                is_enabled=True,
            )

            if not mfa_methods:
                FailedLoginAttempt.create(
                    requester_id=system_id,
                    db=db,
                    user_id=user.id,
                    ip_address=ip_address,
                )
                raise HTTPException(status_code=401, detail="No MFA methods configured")

            # This would use the actual UserMFAMethodManager method in a real implementation
            valid_mfa = False
            for method in mfa_methods:
                method_manager = UserMFAMethodManager(
                    requester_id=system_id,
                    target_user_id=user.id,
                    db=db,
                )
                if method_manager.verify_token_for_method(method, login_model.token):
                    valid_mfa = True
                    method_manager.update(
                        id=method.id,
                        last_used=datetime.utcnow(),
                    )
                    break

            if not valid_mfa:
                FailedLoginAttempt.create(
                    requester_id=system_id,
                    db=db,
                    user_id=user.id,
                    ip_address=ip_address,
                )
                raise HTTPException(status_code=401, detail="Invalid credentials")

        else:
            raise HTTPException(
                status_code=400, detail="Either password or token is required"
            )

        # Login successful - generate JWT token
        token = UserManager.generate_jwt_token(
            user_id=str(user["id"]), email=user["email"]
        )

        # Create session
        session_key = secrets.token_hex(16)
        AuthSession.create(
            requester_id=system_id,
            db=db,
            user_id=user["id"],
            session_key=session_key,
            jwt_issued_at=datetime.utcnow(),
            device_type="web",
            browser="unknown",
            is_active=True,
            last_activity=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            revoked=False,
            trust_score=50,
        )

        # Get user preferences
        preferences = {}
        try:
            metadata_items = UserMetadata.list(
                requester_id=system_id, db=db, user_id=user["id"]
            )
            preferences = {item.key: item.value for item in metadata_items}
        except Exception:
            pass

        # Get user teams with roles
        user_teams = UserTeam.list(
            requester_id=system_id,
            db=db,
            user_id=user["id"],
            enabled=True,
        )

        teams_with_roles = []
        for user_team in user_teams:
            team = Team.get(requester_id=system_id, db=db, id=user_team.team_id)

            role = Role.get(requester_id=system_id, db=db, id=user_team.role_id)

            teams_with_roles.append(
                {
                    "id": team.id,
                    "name": team.name,
                    "description": team.description,
                    "role_id": user_team.role_id,
                    "role_name": role.name if role else None,
                }
            )

        return {
            "id": str(user["id"]),
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "display_name": user["display_name"],
            "token": token,
            "teams": teams_with_roles,
            "detail": f"{req_uri or env('APP_URI')}?token={token}",
            **preferences,
        }

    def get(
        self,
        include: Optional[List[str]] = None,
        fields: Optional[List[str]] = [],
        **kwargs,
    ) -> Any:
        """Get a user with optional included relationships."""
        options = []

        # TODO Move generate_joins to Mixins.py
        if include:
            options = self.generate_joins(self.DBClass, include)

        return self.DBClass.get(
            requester_id=self.requester.id,
            fields=fields,
            db=self.db,
            return_type="dto" if not fields else "dict",
            override_dto=self.Model if not fields else None,
            options=options,
            **kwargs,
        )


class UserCredentialModel(BaseMixinModel, UserModel.ReferenceID):
    password_hash: Optional[str] = Field(None, description="Hashed password")
    password_changed_at: Optional[datetime] = Field(
        None, description="When password was last changed"
    )

    class ReferenceID:
        user_credential_id: str = Field(
            ..., description="The ID of the related user credential"
        )

        class Optional:
            user_credential_id: Optional[str] = None

        class Search:
            user_credential_id: Optional[StringSearchModel] = None

    class Create(BaseModel, UserModel.ReferenceID):
        password_hash: Optional[str]

    class CreateRaw(BaseModel, UserModel.ReferenceID):
        password: str = Field(None, description="New password (will be hashed)")

    class Update(BaseModel):
        # TODO This model and entity should not be updatable.
        pass

    class Search(BaseMixinModel.Search, UserModel.ReferenceID.Search):
        password_changed: Optional[DateSearchModel] = None


class UserCredentialReferenceModel(UserCredentialModel.ReferenceID):
    user_credential: Optional[UserCredentialModel] = None

    class Optional(UserCredentialModel.ReferenceID.Optional):
        user_credential: Optional[UserCredentialModel] = None


class UserCredentialNetworkModel:
    class POST(BaseModel):
        user_credential: UserCredentialModel.CreateRaw

    class PUT(BaseModel):
        user_credential: UserCredentialModel.Update

    class SEARCH(BaseModel):
        user_credential: UserCredentialModel.Search

    class ResponseSingle(BaseModel):
        user_credential: UserCredentialModel

    class ResponsePlural(BaseModel):
        user_credentials: List[UserCredentialModel]


class UserCredentialManager(AbstractBLLManager):
    Model = UserCredentialModel
    ReferenceModel = UserCredentialReferenceModel
    NetworkModel = UserCredentialNetworkModel
    DBClass = UserCredential

    def create(self, **kwargs):
        """Create new user credentials (password)"""
        # TODO Implement this without try/catch, update on the filter?
        try:
            UserCredential.update(
                requester_id=self.requester.id,
                db=self.db,
                id=UserCredential.get(
                    requester_id=self.requester.id,
                    db=self.db,
                    override_dto=self.Model,
                    return_type="dto",
                    user_id=kwargs.get("user_id"),
                    filters=[UserCredential.password_changed == None],
                ).id,
                new_properties={"password_changed": datetime.utcnow()},
            )
        except:
            pass  # No previous password found to update.
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(kwargs.pop("password").encode(), salt).decode()

        return super().create(
            password_hash=password_hash, password_salt=salt.decode(), **kwargs
        )

    def update(self, id: str, **kwargs):
        """Update user credentials (password)"""
        if "password" in kwargs:
            # Get the credential we're updating
            credential = UserCredential.get(
                requester_id=self.requester.id, db=self.db, id=id
            )

            # If this is the current password (password_changed is None)
            if credential.password_changed is None:
                # Create a new credential record instead of updating
                return self.create(
                    user_id=credential.user_id, password=kwargs.pop("password")
                )
            else:
                # Otherwise, just update this old password record
                password = kwargs.pop("password")
                salt = bcrypt.gensalt()
                kwargs["password_hash"] = bcrypt.hashpw(
                    password.encode(), salt
                ).decode()
                kwargs["password_salt"] = salt.decode()

        return super().update(id, **kwargs)

    def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> Dict[str, str]:
        """Change a user's password with verification"""
        # Find current active credential
        credentials = UserCredential.list(
            requester_id=self.requester.id,
            db=self.db,
            user_id=user_id,
            filters=[UserCredential.password_changed == None],
        )

        if not credentials:
            raise HTTPException(status_code=404, detail="User credentials not found")

        credential = credentials[0]

        # Handle both dictionary and object return types
        password_hash = (
            credential["password_hash"]
            if isinstance(credential, dict)
            else credential.password_hash
        )

        # Verify current password
        if not bcrypt.checkpw(current_password.encode(), password_hash.encode()):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        # Mark the current password as changed
        credential_id = (
            credential["id"] if isinstance(credential, dict) else credential.id
        )
        self.update(id=credential_id, password_changed=datetime.utcnow())

        # Create a new credential entry with the new password
        self.create(user_id=user_id, password=new_password)

        return {"message": "Password changed successfully"}


class UserRecoveryQuestionModel(
    BaseMixinModel, UpdateMixinModel, UserModel.ReferenceID
):
    question: str = Field(..., description="Recovery question")
    answer: str = Field(..., description="Hashed answer to recovery question")

    class ReferenceID:
        recovery_question_id: str = Field(
            ..., description="The ID of the related recovery question"
        )

        class Optional:
            recovery_question_id: Optional[str] = None

        class Search:
            recovery_question_id: Optional[StringSearchModel] = None

    class Create(BaseModel, UserModel.ReferenceID):
        question: str = Field(..., description="Recovery question")
        answer: str = Field(
            ..., description="Answer to recovery question (will be hashed)"
        )

    class Update(BaseModel):
        question: Optional[str] = Field(None, description="Recovery question")
        answer: Optional[str] = Field(
            None, description="Answer to recovery question (will be hashed)"
        )

    class Search(BaseMixinModel.Search, UserModel.ReferenceID.Search):
        question: Optional[StringSearchModel] = None


class UserRecoveryQuestionReferenceModel(UserRecoveryQuestionModel.ReferenceID):
    recovery_question: Optional[UserRecoveryQuestionModel] = None

    class Optional(UserRecoveryQuestionModel.ReferenceID.Optional):
        recovery_question: Optional[UserRecoveryQuestionModel] = None


class UserRecoveryQuestionNetworkModel:
    class POST(BaseModel):
        recovery_question: UserRecoveryQuestionModel.Create

    class PUT(BaseModel):
        recovery_question: UserRecoveryQuestionModel.Update

    class SEARCH(BaseModel):
        recovery_question: UserRecoveryQuestionModel.Search

    class ResponseSingle(BaseModel):
        recovery_question: UserRecoveryQuestionModel

    class ResponsePlural(BaseModel):
        recovery_questions: List[UserRecoveryQuestionModel]


class UserRecoveryQuestionManager(AbstractBLLManager):
    Model = UserRecoveryQuestionModel
    ReferenceModel = UserRecoveryQuestionReferenceModel
    NetworkModel = UserRecoveryQuestionNetworkModel
    DBClass = UserRecoveryQuestion

    def createValidation(self, entity):
        """Validate recovery question creation"""
        if not User.exists(
            requester_id=self.requester.id, db=self.db, id=entity.user_id
        ):
            raise HTTPException(status_code=404, detail="User not found")

    def create(self, **kwargs):
        """Create a recovery question with hashed answer"""
        if "answer" in kwargs:
            answer = kwargs.pop("answer")
            normalized_answer = answer.lower().strip()
            salt = bcrypt.gensalt()
            kwargs["answer"] = bcrypt.hashpw(normalized_answer.encode(), salt).decode()

        return super().create(**kwargs)

    def update(self, id: str, **kwargs):
        """Update a recovery question with hashed answer"""
        if "answer" in kwargs:
            answer = kwargs.pop("answer")
            normalized_answer = answer.lower().strip()
            salt = bcrypt.gensalt()
            kwargs["answer"] = bcrypt.hashpw(normalized_answer.encode(), salt).decode()

        return super().update(id, **kwargs)

    def verify_answer(self, question_id: str, answer: str) -> bool:
        """Verify a recovery question answer"""
        question = UserRecoveryQuestion.get(
            requester_id=self.requester.id, db=self.db, id=question_id
        )

        if not question:
            return False

        normalized_answer = answer.lower().strip()
        return bcrypt.checkpw(normalized_answer.encode(), question.answer.encode())


class FailedLoginAttemptModel(BaseMixinModel, UserReferenceModel):
    ip_address: Optional[str] = Field(
        None, description="IP address of the failed login attempt"
    )

    class ReferenceID:
        failed_login_id: str = Field(
            ..., description="The ID of the related failed login attempt"
        )

        class Optional:
            failed_login_id: Optional[str] = None

        class Search:
            failed_login_id: Optional[StringSearchModel] = None

    class Create(BaseModel, UserModel.ReferenceID):
        ip_address: Optional[str] = Field(
            None, description="IP address of the failed login attempt"
        )

    class Update(BaseModel):
        pass

    class Search(BaseMixinModel.Search, UserModel.ReferenceID.Search):
        ip_address: Optional[StringSearchModel] = None
        created_at: Optional[DateSearchModel] = None


class FailedLoginAttemptReferenceModel(FailedLoginAttemptModel.ReferenceID):
    failed_login: Optional[FailedLoginAttemptModel] = None

    class Optional(FailedLoginAttemptModel.ReferenceID.Optional):
        failed_login: Optional[FailedLoginAttemptModel] = None


class FailedLoginAttemptNetworkModel:
    class POST(BaseModel):
        failed_login: FailedLoginAttemptModel.Create

    class PUT(BaseModel):
        failed_login: FailedLoginAttemptModel.Update

    class SEARCH(BaseModel):
        failed_login: FailedLoginAttemptModel.Search

    class ResponseSingle(BaseModel):
        failed_login: FailedLoginAttemptModel

    class ResponsePlural(BaseModel):
        failed_logins: List[FailedLoginAttemptModel]


class FailedLoginAttemptManager(AbstractBLLManager):
    Model = FailedLoginAttemptModel
    ReferenceModel = FailedLoginAttemptReferenceModel
    NetworkModel = FailedLoginAttemptNetworkModel
    DBClass = FailedLoginAttempt

    def _register_search_transformers(self):
        self.register_search_transformer("recent", self._transform_recent_search)

    def _transform_recent_search(self, hours):
        """Transform a 'recent' search parameter to filter by recent time period"""
        if not hours or not isinstance(hours, int):
            hours = 1

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [FailedLoginAttempt.created_at >= cutoff_time]

    def count_recent(self, user_id: str, hours: int = 1) -> int:
        """Count recent failed login attempts for a user"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        return FailedLoginAttempt.count(
            requester_id=self.requester.id,
            db=self.db,
            user_id=user_id,
            filters=[FailedLoginAttempt.created_at >= cutoff_time],
        )

    def is_account_locked(
        self, user_id: str, max_attempts: int = 5, hours: int = 1
    ) -> bool:
        """Check if an account is locked due to too many failed attempts"""
        recent_count = self.count_recent(user_id, hours)
        return recent_count >= max_attempts


class TeamModel(
    BaseMixinModel,
    UpdateMixinModel,
    ParentMixinModel.Optional,
    NameMixinModel,
    ImageMixinModel.Optional,
):
    description: Optional[str] = Field(None, description="Team description")
    encryption_key: str = Field(..., description="Encryption key for team data")
    token: Optional[str] = Field(None, description="Team token")
    training_data: Optional[str] = Field(None, description="Training data for team")

    class ReferenceID:
        team_id: str = Field(..., description="The ID of the related team")

        class Optional:
            team_id: Optional[str] = None

        class Search:
            team_id: Optional[StringSearchModel] = None

    class Create(
        BaseModel, NameMixinModel, ParentMixinModel.Optional, ImageMixinModel.Optional
    ):
        description: Optional[str] = Field(None, description="Team description")
        encryption_key: Optional[str] = Field(
            None, description="Encryption key for team data"
        )

    class Update(
        BaseModel,
        NameMixinModel.Optional,
        ParentMixinModel.Optional,
        ImageMixinModel.Optional,
    ):
        description: Optional[str] = Field(None, description="Team description")
        token: Optional[str] = Field(None, description="Team token")
        training_data: Optional[str] = Field(None, description="Training data for team")

    class Search(
        BaseMixinModel.Search,
        NameMixinModel.Search,
        ParentMixinModel.Search,
        ImageMixinModel.Search,
    ):
        description: Optional[StringSearchModel] = None


class TeamReferenceModel(TeamModel.ReferenceID):
    team: Optional[TeamModel] = None

    class Optional(TeamModel.ReferenceID.Optional):
        team: Optional[TeamModel] = None


class TeamNetworkModel:
    class POST(BaseModel):
        team: TeamModel.Create

    class PUT(BaseModel):
        team: TeamModel.Update

    class SEARCH(BaseModel):
        team: TeamModel.Search

    class ResponseSingle(BaseModel):
        team: TeamModel

    class ResponsePlural(BaseModel):
        teams: List[TeamModel]


class TeamManager(AbstractBLLManager):
    Model = TeamModel
    ReferenceModel = TeamReferenceModel
    NetworkModel = TeamNetworkModel
    DBClass = Team

    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        self._team_metadata_manager = None
        self._user_team_manager = None

    @property
    def team_metadata_manager(self):
        """Get the team metadata manager"""
        if self._team_metadata_manager is None:
            self._team_metadata_manager = TeamMetadataManager(
                requester_id=self.requester.id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._team_metadata_manager

    @property
    def user_team_manager(self):
        """Get the user team manager"""
        if self._user_team_manager is None:
            self._user_team_manager = UserTeamManager(
                requester_id=self.requester.id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._user_team_manager

    def createValidation(self, entity):
        """Validate team creation"""
        # Check if the parent team exists when parent_id is provided
        if hasattr(entity, "parent_id") and entity.parent_id:
            parent_exists = Team.exists(
                requester_id=self.requester.id, db=self.db, id=entity.parent_id
            )
            if not parent_exists:
                raise HTTPException(status_code=404, detail="Parent team not found")

    def create(self, **kwargs):
        """Create a team with metadata"""
        # Extract metadata fields (non-model fields)
        metadata_fields = {}
        model_fields = {}

        # Get the model fields for comparison
        model_fields_set = set(self.Model.Create.__annotations__.keys())
        # TODO Add fields from mixins dynamically that might not be in annotations
        model_fields_set.add("name")
        model_fields_set.add("parent_id")
        model_fields_set.add("description")
        model_fields_set.add("image_url")

        for key, value in kwargs.items():
            if key in model_fields_set:
                model_fields[key] = value
            else:
                metadata_fields[key] = value

        # Generate encryption key if not provided
        if "encryption_key" not in model_fields:
            model_fields["encryption_key"] = secrets.token_hex(32)

        # Create the team
        team = super().create(**model_fields)

        # Create metadata if provided
        if metadata_fields and team:
            for key, value in metadata_fields.items():
                self.team_metadata_manager.create(
                    team_id=team.id,
                    key=key,
                    value=str(value),
                )

        UserTeamManager(
            requester_id=env("ROOT_ID")
        ).create(  # Must create with Root ID or can't see Team (yet).
            team_id=team.id,
            user_id=self.requester.id,
            role_id="FFFFFFFF-FFFF-FFFF-AAAA-FFFFFFFFFFFF",  # Admin
        )

        return team

    def update(self, id: str, **kwargs):
        """Update a team with metadata"""
        # Extract metadata fields (non-model fields)
        metadata_fields = {}
        model_fields = {}

        # Get the model fields for comparison
        model_fields_set = set(self.Model.Update.__annotations__.keys())
        for key, value in kwargs.items():
            if key in model_fields_set:
                model_fields[key] = value
            else:
                metadata_fields[key] = value

        # Update the team
        team = super().update(id, **model_fields)

        # Update metadata if provided
        if metadata_fields and team:
            existing_metadata = self.team_metadata_manager.list(team_id=id)
            existing_metadata_dict = {item.key: item for item in existing_metadata}

            for key, value in metadata_fields.items():
                if key in existing_metadata_dict:
                    # Update existing metadata
                    self.team_metadata_manager.update(
                        id=existing_metadata_dict[key].id,
                        value=str(value),
                    )
                else:
                    # Create new metadata
                    self.team_metadata_manager.create(
                        team_id=id,
                        key=key,
                        value=str(value),
                    )

        return team

    def get_metadata(self) -> Dict[str, str]:
        """Get all metadata for the target team"""
        if not self.target_team_id:
            raise HTTPException(status_code=400, detail="Team ID is required")

        metadata_items = TeamMetadata.list(
            requester_id=self.requester.id, db=self.db, team_id=self.target_team_id
        )

        return {item.key: item.value for item in metadata_items}


class TeamMetadataModel(BaseMixinModel, UpdateMixinModel, TeamReferenceModel):
    key: str = Field(..., description="Metadata key")
    value: Optional[str] = Field(None, description="Metadata value")

    class ReferenceID:
        team_metadata_id: str = Field(
            ..., description="The ID of the related team metadata"
        )

        class Optional:
            team_metadata_id: Optional[str] = None

        class Search:
            team_metadata_id: Optional[StringSearchModel] = None

    class Create(BaseModel, TeamModel.ReferenceID):
        key: str = Field(..., description="Metadata key")
        value: Optional[str] = Field(None, description="Metadata value")

    class Update(BaseModel):
        value: Optional[str] = Field(None, description="Metadata value")

    class Search(BaseMixinModel.Search, TeamModel.ReferenceID.Search):
        key: Optional[StringSearchModel] = None
        value: Optional[StringSearchModel] = None


class TeamMetadataReferenceModel(TeamMetadataModel.ReferenceID):
    team_metadata: Optional[TeamMetadataModel] = None

    class Optional(TeamMetadataModel.ReferenceID.Optional):
        team_metadata: Optional[TeamMetadataModel] = None


class TeamMetadataNetworkModel:
    class POST(BaseModel):
        team_metadata: TeamMetadataModel.Create

    class PUT(BaseModel):
        team_metadata: TeamMetadataModel.Update

    class SEARCH(BaseModel):
        team_metadata: TeamMetadataModel.Search

    class ResponseSingle(BaseModel):
        team_metadata: TeamMetadataModel

    class ResponsePlural(BaseModel):
        team_metadata_items: List[TeamMetadataModel]


class TeamMetadataManager(AbstractBLLManager):
    Model = TeamMetadataModel
    ReferenceModel = TeamMetadataReferenceModel
    NetworkModel = TeamMetadataNetworkModel
    DBClass = TeamMetadata

    def createValidation(self, entity):
        """Validate team metadata creation"""
        if not Team.exists(
            requester_id=self.requester.id, db=self.db, id=entity.team_id
        ):
            raise HTTPException(status_code=404, detail="Team not found")


class RoleModel(
    BaseMixinModel,
    ParentMixinModel,
    NameMixinModel,
    UpdateMixinModel,
    TeamReferenceModel,
):
    friendly_name: Optional[str] = Field(None, description="Human-readable role name")
    mfa_count: int = Field(1, description="Number of MFA verifications required")
    password_change_frequency_days: int = Field(
        365, description="How often password must be changed"
    )

    class ReferenceID:
        role_id: str = Field(..., description="The ID of the related role")

        class Optional:
            role_id: Optional[str] = None

        class Search:
            role_id: Optional[StringSearchModel] = None

    class Create(
        BaseModel,
        NameMixinModel,
        ParentMixinModel.Optional,
        TeamModel.ReferenceID.Optional,
    ):
        friendly_name: Optional[str] = Field(
            None, description="Human-readable role name"
        )
        mfa_count: Optional[int] = Field(
            1, description="Number of MFA verifications required"
        )
        password_change_frequency_days: Optional[int] = Field(
            365, description="How often password must be changed"
        )

    class Update(BaseModel, NameMixinModel.Optional, ParentMixinModel.Optional):
        friendly_name: Optional[str] = Field(
            None, description="Human-readable role name"
        )
        mfa_count: Optional[int] = Field(
            None, description="Number of MFA verifications required"
        )
        password_change_frequency_days: Optional[int] = Field(
            None, description="How often password must be changed"
        )

    class Search(
        BaseMixinModel.Search,
        NameMixinModel.Search,
        ParentMixinModel.Search,
        TeamModel.ReferenceID.Search,
    ):
        friendly_name: Optional[StringSearchModel] = None
        mfa_count: Optional[NumericalSearchModel] = None


class RoleReferenceModel(RoleModel.ReferenceID):
    role: Optional[RoleModel] = None

    class Optional(RoleModel.ReferenceID.Optional):
        role: Optional[RoleModel] = None


class RoleNetworkModel:
    class POST(BaseModel):
        role: RoleModel.Create

    class PUT(BaseModel):
        role: RoleModel.Update

    class SEARCH(BaseModel):
        role: RoleModel.Search

    class ResponseSingle(BaseModel):
        role: RoleModel

    class ResponsePlural(BaseModel):
        roles: List[RoleModel]


class RoleManager(AbstractBLLManager):
    Model = RoleModel
    ReferenceModel = RoleReferenceModel
    NetworkModel = RoleNetworkModel
    DBClass = Role

    def _register_search_transformers(self):
        self.register_search_transformer("is_system", self._transform_is_system_search)

    def _transform_is_system_search(self, value):
        """Transform is_system search to filter system roles (team_id is NULL)"""
        if value:
            return [Role.team_id == None]
        return [Role.team_id != None]


class UserTeamModel(
    BaseMixinModel,
    UpdateMixinModel,
    UserReferenceModel,
    TeamReferenceModel,
    RoleReferenceModel,
):
    enabled: bool = Field(True, description="Whether this membership is enabled")

    class ReferenceID:
        user_team_id: str = Field(..., description="The ID of the related user team")

        class Optional:
            user_team_id: Optional[str] = None

        class Search:
            user_team_id: Optional[StringSearchModel] = None

    class Create(
        BaseModel, UserModel.ReferenceID, TeamModel.ReferenceID, RoleModel.ReferenceID
    ):
        enabled: Optional[bool] = Field(
            True, description="Whether this membership is enabled"
        )

    class Update(BaseModel):
        role_id: Optional[str] = Field(
            None, description="Role ID assigned to the user in this team"
        )
        enabled: Optional[bool] = Field(
            None, description="Whether this membership is enabled"
        )

    class Search(
        BaseMixinModel.Search,
        UserModel.ReferenceID.Search,
        TeamModel.ReferenceID.Search,
        RoleModel.ReferenceID.Search,
    ):
        enabled: Optional[bool] = None


class UserTeamReferenceModel(UserTeamModel.ReferenceID):
    user_team: Optional[UserTeamModel] = None

    class Optional(UserTeamModel.ReferenceID.Optional):
        user_team: Optional[UserTeamModel] = None


class UserTeamNetworkModel:
    class POST(BaseModel):
        user_team: UserTeamModel.Create

    class PUT(BaseModel):
        user_team: UserTeamModel.Update

    class SEARCH(BaseModel):
        user_team: UserTeamModel.Search

    class ResponseSingle(BaseModel):
        user_team: UserTeamModel

    class ResponsePlural(BaseModel):
        user_teams: List[UserTeamModel]


class UserTeamManager(AbstractBLLManager):
    Model = UserTeamModel
    ReferenceModel = UserTeamReferenceModel
    NetworkModel = UserTeamNetworkModel
    DBClass = UserTeam

    def createValidation(self, entity):
        """Validate user team relationship creation"""
        if not User.exists(
            requester_id=self.requester.id, db=self.db, id=entity.user_id
        ):
            raise HTTPException(status_code=404, detail="User not found")

        if not Team.exists(
            requester_id=self.requester.id, db=self.db, id=entity.team_id
        ):
            raise HTTPException(status_code=404, detail="Team not found")

        if not Role.exists(
            requester_id=self.requester.id, db=self.db, id=entity.role_id
        ):
            raise HTTPException(status_code=404, detail="Role not found")


class UserMetadataModel(BaseMixinModel, UpdateMixinModel, UserReferenceModel):
    key: str = Field(..., description="Metadata key")
    value: Optional[str] = Field(None, description="Metadata value")

    class ReferenceID:
        user_metadata_id: str = Field(
            ..., description="The ID of the related user metadata"
        )

        class Optional:
            user_metadata_id: Optional[str] = None

        class Search:
            user_metadata_id: Optional[StringSearchModel] = None

    class Create(BaseModel, UserModel.ReferenceID):
        key: str = Field(..., description="Metadata key")
        value: Optional[str] = Field(None, description="Metadata value")

    class Update(BaseModel):
        value: Optional[str] = Field(None, description="Metadata value")

    class Search(BaseMixinModel.Search, UserModel.ReferenceID.Search):
        key: Optional[StringSearchModel] = None
        value: Optional[StringSearchModel] = None


class UserMetadataReferenceModel(UserMetadataModel.ReferenceID):
    user_metadata: Optional[UserMetadataModel] = None

    class Optional(UserMetadataModel.ReferenceID.Optional):
        user_metadata: Optional[UserMetadataModel] = None


class UserMetadataNetworkModel:
    class POST(BaseModel):
        user_metadata: UserMetadataModel.Create

    class PUT(BaseModel):
        user_metadata: UserMetadataModel.Update

    class SEARCH(BaseModel):
        user_metadata: UserMetadataModel.Search

    class ResponseSingle(BaseModel):
        user_metadata: UserMetadataModel

    class ResponsePlural(BaseModel):
        user_metadata_items: List[UserMetadataModel]


class UserMetadataManager(AbstractBLLManager):
    Model = UserMetadataModel
    ReferenceModel = UserMetadataReferenceModel
    NetworkModel = UserMetadataNetworkModel
    DBClass = UserMetadata

    def createValidation(self, entity):
        """Validate user metadata creation"""
        if not User.exists(
            requester_id=self.requester.id, db=self.db, id=entity.user_id
        ):
            raise HTTPException(status_code=404, detail="User not found")

    def set_preference(self, key: str, value: str) -> Dict[str, str]:
        """Set or update a user preference"""
        if not self.target_user_id:
            raise HTTPException(status_code=400, detail="User ID is required")

        # Find existing metadata for this key
        existing = UserMetadata.list(
            requester_id=self.requester.id,
            db=self.db,
            user_id=self.target_user_id,
            key=key,
        )

        if existing:
            # Update existing preference
            UserMetadata.update(
                requester_id=self.requester.id,
                db=self.db,
                id=(
                    existing[0].id
                    if isinstance(existing[0], dict)
                    else existing[0]["id"]
                ),
                new_properties={"value": value},
            )
        else:
            # Create new preference
            self.create(user_id=self.target_user_id, key=key, value=value)

        return {"message": "Preference set successfully", "key": key, "value": value}

    def get_preference(self, key: str) -> Dict[str, str]:
        """Get a specific user preference"""
        if not self.target_user_id:
            raise HTTPException(status_code=400, detail="User ID is required")

        preferences = UserMetadata.list(
            requester_id=self.requester.id,
            db=self.db,
            user_id=self.target_user_id,
            key=key,
        )

        if not preferences:
            raise HTTPException(status_code=404, detail=f"Preference '{key}' not found")

        preference = preferences[0]
        value = (
            preference["value"] if isinstance(preference, dict) else preference.value
        )

        return {key: value}

    def get_preferences(self) -> Dict[str, str]:
        """Get all user preferences"""
        if not self.target_user_id:
            raise HTTPException(status_code=400, detail="User ID is required")

        preferences = UserMetadata.list(
            requester_id=self.requester.id,
            db=self.db,
            user_id=self.target_user_id,
        )

        # Convert to dictionary of key-value pairs
        result = {}
        for pref in preferences:
            if isinstance(pref, dict):
                result[pref["key"]] = pref["value"]
            else:
                result[pref.key] = pref.value

        return result


class PermissionModel(BaseMixinModel, UpdateMixinModel):
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="ID of the resource")
    user_id: Optional[str] = Field(
        None, description="User ID if user-specific permission"
    )
    team_id: Optional[str] = Field(
        None, description="Team ID if team-specific permission"
    )
    role_id: Optional[str] = Field(None, description="Role ID for permission level")
    can_view: bool = Field(False, description="Whether user/team can view the resource")
    can_execute: bool = Field(
        False, description="Whether user/team can execute the resource"
    )
    can_copy: bool = Field(False, description="Whether user/team can copy the resource")
    can_edit: bool = Field(False, description="Whether user/team can edit the resource")
    can_delete: bool = Field(
        False, description="Whether user/team can delete the resource"
    )
    can_share: bool = Field(
        False, description="Whether user/team can share the resource"
    )

    class ReferenceID:
        permission_id: str = Field(..., description="The ID of the related permission")

        class Optional:
            permission_id: Optional[str] = None

        class Search:
            permission_id: Optional[StringSearchModel] = None

    class Create(
        BaseModel,
        UserModel.ReferenceID.Optional,
        TeamModel.ReferenceID.Optional,
        RoleModel.ReferenceID.Optional,
    ):
        resource_type: str = Field(..., description="Type of resource")
        resource_id: str = Field(..., description="ID of the resource")
        can_view: Optional[bool] = Field(
            False, description="Whether user/team can view the resource"
        )
        can_execute: Optional[bool] = Field(
            False, description="Whether user/team can execute the resource"
        )
        can_copy: Optional[bool] = Field(
            False, description="Whether user/team can copy the resource"
        )
        can_edit: Optional[bool] = Field(
            False, description="Whether user/team can edit the resource"
        )
        can_delete: Optional[bool] = Field(
            False, description="Whether user/team can delete the resource"
        )
        can_share: Optional[bool] = Field(
            False, description="Whether user/team can share the resource"
        )

        @model_validator(mode="after")
        def validate_ownership(self):
            if (self.user_id is None and self.team_id is None) or (
                self.user_id is not None and self.team_id is not None
            ):
                raise ValueError(
                    "Either user_id or team_id must be provided, not both or neither"
                )
            return self

    class Update(BaseModel, RoleModel.ReferenceID.Optional):
        can_view: Optional[bool] = Field(
            None, description="Whether user/team can view the resource"
        )
        can_execute: Optional[bool] = Field(
            None, description="Whether user/team can execute the resource"
        )
        can_copy: Optional[bool] = Field(
            None, description="Whether user/team can copy the resource"
        )
        can_edit: Optional[bool] = Field(
            None, description="Whether user/team can edit the resource"
        )
        can_delete: Optional[bool] = Field(
            None, description="Whether user/team can delete the resource"
        )
        can_share: Optional[bool] = Field(
            None, description="Whether user/team can share the resource"
        )

    class Search(
        BaseMixinModel.Search,
        UserModel.ReferenceID.Search,
        TeamModel.ReferenceID.Search,
        RoleModel.ReferenceID.Search,
    ):
        resource_type: Optional[StringSearchModel] = None
        resource_id: Optional[StringSearchModel] = None
        can_view: Optional[bool] = None
        can_execute: Optional[bool] = None
        can_copy: Optional[bool] = None
        can_edit: Optional[bool] = None
        can_delete: Optional[bool] = None
        can_share: Optional[bool] = None


class PermissionReferenceModel(PermissionModel.ReferenceID):
    permission: Optional[PermissionModel] = None

    class Optional(PermissionModel.ReferenceID.Optional):
        permission: Optional[PermissionModel] = None


class PermissionNetworkModel:
    class POST(BaseModel):
        permission: PermissionModel.Create

    class PUT(BaseModel):
        permission: PermissionModel.Update

    class SEARCH(BaseModel):
        permission: PermissionModel.Search

    class ResponseSingle(BaseModel):
        permission: PermissionModel

    class ResponsePlural(BaseModel):
        permissions: List[PermissionModel]


class PermissionManager(AbstractBLLManager):
    Model = PermissionModel
    ReferenceModel = PermissionReferenceModel
    NetworkModel = PermissionNetworkModel
    DBClass = Permission

    def createValidation(self, entity):
        """Validate permission creation"""
        if entity.user_id and not User.exists(
            requester_id=self.requester.id, db=self.db, id=entity.user_id
        ):
            raise HTTPException(status_code=404, detail="User not found")

        if entity.team_id and not Team.exists(
            requester_id=self.requester.id, db=self.db, id=entity.team_id
        ):
            raise HTTPException(status_code=404, detail="Team not found")

        if entity.role_id and not Role.exists(
            requester_id=self.requester.id, db=self.db, id=entity.role_id
        ):
            raise HTTPException(status_code=404, detail="Role not found")


class InvitationModel(BaseMixinModel, UpdateMixinModel, TeamReferenceModel):
    code: Optional[str] = Field(None, description="Invitation code")
    role_id: str = Field(..., description="Role ID to assign")
    inviter_id: str = Field(..., description="User ID of the inviter")
    max_uses: Optional[int] = Field(None, description="Maximum number of uses allowed")
    expires_at: Optional[datetime] = Field(None, description="Expiration date/time")

    class ReferenceID:
        invitation_id: str = Field(..., description="The ID of the related invitation")

        class Optional:
            invitation_id: Optional[str] = None

        class Search:
            invitation_id: Optional[StringSearchModel] = None

    class Create(
        BaseModel,
        TeamModel.ReferenceID,
        RoleModel.ReferenceID,
        UserModel.ReferenceID.Optional,
    ):
        code: Optional[str] = Field(
            None, description="Invitation code (auto-generated if not provided)"
        )
        inviter_id: Optional[str] = Field(None, description="User ID of the inviter")
        max_uses: Optional[int] = Field(
            None, description="Maximum number of uses allowed"
        )
        expires_at: Optional[datetime] = Field(None, description="Expiration date/time")

    class Update(BaseModel, RoleModel.ReferenceID.Optional):
        code: Optional[str] = Field(None, description="Invitation code")
        max_uses: Optional[int] = Field(
            None, description="Maximum number of uses allowed"
        )
        expires_at: Optional[datetime] = Field(None, description="Expiration date/time")

    class Search(
        BaseMixinModel.Search,
        TeamModel.ReferenceID.Search,
        RoleModel.ReferenceID.Search,
    ):
        code: Optional[StringSearchModel] = None
        inviter_id: Optional[StringSearchModel] = None
        max_uses: Optional[NumericalSearchModel] = None
        expires_at: Optional[DateSearchModel] = None


class InvitationReferenceModel(InvitationModel.ReferenceID):
    invitation: Optional[InvitationModel] = None

    class Optional(InvitationModel.ReferenceID.Optional):
        invitation: Optional[InvitationModel] = None


class InvitationNetworkModel:
    class POST(BaseModel):
        invitation: InvitationModel.Create

    class PUT(BaseModel):
        invitation: InvitationModel.Update

    class SEARCH(BaseModel):
        invitation: InvitationModel.Search

    class ResponseSingle(BaseModel):
        invitation: InvitationModel

    class ResponsePlural(BaseModel):
        invitations: List[InvitationModel]


class InvitationManager(AbstractBLLManager):
    Model = InvitationModel
    ReferenceModel = InvitationReferenceModel
    NetworkModel = InvitationNetworkModel
    DBClass = Invitation

    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        self._invitation_invitee_manager = None

    @property
    def invitation_invitee_manager(self):
        """Get the invitation invitee manager"""
        if self._invitation_invitee_manager is None:
            self._invitation_invitee_manager = InvitationInviteeManager(
                requester_id=self.requester.id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._invitation_invitee_manager

    def createValidation(self, entity):
        """Validate invitation creation"""
        if not Team.exists(
            requester_id=self.requester.id, db=self.db, id=entity.team_id
        ):
            raise HTTPException(status_code=404, detail="Team not found")

        if not Role.exists(
            requester_id=self.requester.id, db=self.db, id=entity.role_id
        ):
            raise HTTPException(status_code=404, detail="Role not found")

        if entity.inviter_id and not User.exists(
            requester_id=self.requester.id, db=self.db, id=entity.inviter_id
        ):
            raise HTTPException(status_code=404, detail="Inviter not found")

    def create(self, **kwargs):
        """Create an invitation with auto-generated code if needed"""
        if "code" not in kwargs or not kwargs["code"]:
            kwargs["code"] = "".join(
                secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)
            )

        if "inviter_id" not in kwargs or not kwargs["inviter_id"]:
            kwargs["inviter_id"] = self.requester.id

        return super().create(**kwargs)

    @staticmethod
    def generate_invitation_link(code: str) -> str:
        """Generate an invitation link from a code"""
        base_url = env("APP_URI")
        return f"{base_url}/join?code={code}"

    def add_invitee(self, invitation_id: str, email: str) -> Dict[str, Any]:
        """Add an invitee to an invitation"""
        invitation = Invitation.get(
            requester_id=self.requester.id, db=self.db, id=invitation_id
        )

        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        invitee = self.invitation_invitee_manager.create(
            invitation_id=invitation_id,
            email=email.lower().strip(),
            is_accepted=False,
        )

        return {
            "invitation_id": invitation.id,
            "invitation_code": invitation.code,
            "invitation_link": self.generate_invitation_link(invitation.code),
            "invitee_id": invitee.id,
            "email": email,
        }


class InvitationInviteeModel(
    BaseMixinModel, UpdateMixinModel, InvitationReferenceModel
):
    email: str = Field(..., description="Email of the invitee")
    is_accepted: bool = Field(
        False, description="Whether the invitation has been accepted"
    )
    accepted_at: Optional[datetime] = Field(
        None, description="When the invitation was accepted"
    )
    invitee_user_id: Optional[str] = Field(
        None, description="User ID of the invitee after acceptance"
    )

    class ReferenceID:
        invitation_invitee_id: str = Field(
            ..., description="The ID of the related invitation invitee"
        )

        class Optional:
            invitation_invitee_id: Optional[str] = None

        class Search:
            invitation_invitee_id: Optional[StringSearchModel] = None

    class Create(
        BaseModel, InvitationModel.ReferenceID, UserModel.ReferenceID.Optional
    ):
        email: str = Field(..., description="Email of the invitee")
        is_accepted: Optional[bool] = Field(
            False, description="Whether the invitation has been accepted"
        )
        accepted_at: Optional[datetime] = Field(
            None, description="When the invitation was accepted"
        )

    class Update(BaseModel, UserModel.ReferenceID.Optional):
        is_accepted: Optional[bool] = Field(
            None, description="Whether the invitation has been accepted"
        )
        accepted_at: Optional[datetime] = Field(
            None, description="When the invitation was accepted"
        )

    class Search(
        BaseMixinModel.Search,
        InvitationModel.ReferenceID.Search,
        UserModel.ReferenceID.Search,
    ):
        email: Optional[StringSearchModel] = None
        is_accepted: Optional[bool] = None


class InvitationInviteeReferenceModel(InvitationInviteeModel.ReferenceID):
    invitation_invitee: Optional[InvitationInviteeModel] = None

    class Optional(InvitationInviteeModel.ReferenceID.Optional):
        invitation_invitee: Optional[InvitationInviteeModel] = None


class InvitationInviteeNetworkModel:
    class POST(BaseModel):
        invitation_invitee: InvitationInviteeModel.Create

    class PUT(BaseModel):
        invitation_invitee: InvitationInviteeModel.Update

    class SEARCH(BaseModel):
        invitation_invitee: InvitationInviteeModel.Search

    class ResponseSingle(BaseModel):
        invitation_invitee: InvitationInviteeModel

    class ResponsePlural(BaseModel):
        invitation_invitees: List[InvitationInviteeModel]


class InvitationInviteeManager(AbstractBLLManager):
    Model = InvitationInviteeModel
    ReferenceModel = InvitationInviteeReferenceModel
    NetworkModel = InvitationInviteeNetworkModel
    DBClass = InvitationInvitee

    def createValidation(self, entity):
        """Validate invitation invitee creation"""
        if not Invitation.exists(
            requester_id=self.requester.id, db=self.db, id=entity.invitation_id
        ):
            raise HTTPException(status_code=404, detail="Invitation not found")

        if "@" not in entity.email:
            raise HTTPException(status_code=400, detail="Invalid email format")

        if entity.invitee_user_id and not User.exists(
            requester_id=self.requester.id, db=self.db, id=entity.invitee_user_id
        ):
            raise HTTPException(status_code=404, detail="User not found")

        existing = InvitationInvitee.exists(
            requester_id=self.requester.id,
            db=self.db,
            invitation_id=entity.invitation_id,
            email=entity.email.lower().strip(),
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="This email has already been invited"
            )

    def accept_invitation(self, code: str, user_id: str) -> Dict[str, Any]:
        """Accept an invitation using a code and user ID"""
        # Find the invitation by code
        invitation = Invitation.list(
            requester_id=self.requester.id, db=self.db, code=code
        )

        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        invitation = invitation[0]

        # Check if invitation has expired
        if invitation.expires_at and invitation.expires_at < datetime.utcnow():
            raise HTTPException(status_code=410, detail="Invitation has expired")

        # Check if invitation has reached max uses
        if invitation.max_uses is not None:
            used_count = InvitationInvitee.count(
                requester_id=self.requester.id,
                db=self.db,
                invitation_id=invitation.id,
                is_accepted=True,
            )
            if used_count >= invitation.max_uses:
                raise HTTPException(
                    status_code=410, detail="Invitation has reached maximum usage limit"
                )

        # Verify the user
        user = User.get(requester_id=self.requester.id, db=self.db, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Find invitee by email if exists
        invitees = InvitationInvitee.list(
            requester_id=self.requester.id,
            db=self.db,
            invitation_id=invitation.id,
            email=user.email,
        )

        # For invitation codes that don't have specific invitees, create an invitee record
        if not invitees:
            if not invitation.code:
                # This is a direct invitation without a code, we should have found a matching invitee
                raise HTTPException(
                    status_code=403, detail="Your email is not invited to this team"
                )
            else:
                # For invitation codes, create an invitee record
                invitee = self.create(
                    invitation_id=invitation.id,
                    email=user.email,
                    is_accepted=True,
                    accepted_at=datetime.utcnow(),
                    invitee_user_id=user_id,
                )
        else:
            # Use existing invitee record
            invitee = invitees[0]
            self.update(
                id=invitee.id,
                is_accepted=True,
                accepted_at=datetime.utcnow(),
                invitee_user_id=user_id,
            )

        # Add user to team or update existing membership
        user_team_manager = UserTeamManager(
            requester_id=self.requester.id, target_user_id=user_id, db=self.db
        )

        existing_team_membership = UserTeam.list(
            requester_id=self.requester.id,
            db=self.db,
            user_id=user_id,
            team_id=invitation.team_id,
        )

        if existing_team_membership:
            # Update existing team membership
            user_team = user_team_manager.update(
                id=existing_team_membership[0].id,
                role_id=invitation.role_id,
                enabled=True,
            )
        else:
            # Create new team membership
            user_team = user_team_manager.create(
                user_id=user_id,
                team_id=invitation.team_id,
                role_id=invitation.role_id,
                enabled=True,
            )

        return {
            "success": True,
            "team_id": invitation.team_id,
            "role_id": invitation.role_id,
            "user_team_id": user_team.id,
        }


class UserSessionModel(BaseMixinModel, UpdateMixinModel, UserReferenceModel):
    session_key: str = Field(..., description="Unique session identifier")
    jwt_issued_at: datetime = Field(..., description="When the JWT was issued")
    refresh_token_hash: Optional[str] = Field(None, description="Hashed refresh token")
    device_type: Optional[str] = Field(None, description="Type of device")
    device_name: Optional[str] = Field(None, description="Name of device")
    browser: Optional[str] = Field(None, description="Browser used")
    is_active: bool = Field(True, description="Whether the session is active")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    expires_at: datetime = Field(..., description="When the session expires")
    revoked: bool = Field(False, description="Whether the session has been revoked")
    trust_score: int = Field(50, description="Trust score for the session")
    requires_verification: bool = Field(
        False, description="Whether verification is required"
    )

    class ReferenceID:
        user_session_id: str = Field(
            ..., description="The ID of the related user session"
        )

        class Optional:
            user_session_id: Optional[str] = None

        class Search:
            user_session_id: Optional[StringSearchModel] = None

    class Create(BaseModel, UserModel.ReferenceID):
        session_key: str = Field(..., description="Unique session identifier")
        jwt_issued_at: datetime = Field(..., description="When the JWT was issued")
        refresh_token_hash: Optional[str] = Field(
            None, description="Hashed refresh token"
        )
        device_type: Optional[str] = Field(None, description="Type of device")
        device_name: Optional[str] = Field(None, description="Name of device")
        browser: Optional[str] = Field(None, description="Browser used")
        is_active: Optional[bool] = Field(
            True, description="Whether the session is active"
        )
        last_activity: datetime = Field(..., description="Last activity timestamp")
        expires_at: datetime = Field(..., description="When the session expires")
        revoked: Optional[bool] = Field(
            False, description="Whether the session has been revoked"
        )
        trust_score: Optional[int] = Field(
            50, description="Trust score for the session"
        )
        requires_verification: Optional[bool] = Field(
            False, description="Whether verification is required"
        )

    class Update(BaseModel):
        is_active: Optional[bool] = Field(
            None, description="Whether the session is active"
        )
        last_activity: Optional[datetime] = Field(
            None, description="Last activity timestamp"
        )
        expires_at: Optional[datetime] = Field(
            None, description="When the session expires"
        )
        revoked: Optional[bool] = Field(
            None, description="Whether the session has been revoked"
        )
        trust_score: Optional[int] = Field(
            None, description="Trust score for the session"
        )
        requires_verification: Optional[bool] = Field(
            None, description="Whether verification is required"
        )
        refresh_token_hash: Optional[str] = Field(
            None, description="Hashed refresh token"
        )

    class Search(BaseMixinModel.Search, UserModel.ReferenceID.Search):
        session_key: Optional[StringSearchModel] = None
        is_active: Optional[bool] = None
        revoked: Optional[bool] = None
        expires_at: Optional[DateSearchModel] = None
        device_type: Optional[StringSearchModel] = None
        browser: Optional[StringSearchModel] = None
        requires_verification: Optional[bool] = None


class UserSessionReferenceModel(UserSessionModel.ReferenceID):
    user_session: Optional[UserSessionModel] = None

    class Optional(UserSessionModel.ReferenceID.Optional):
        user_session: Optional[UserSessionModel] = None


class UserSessionNetworkModel:
    class POST(BaseModel):
        user_session: UserSessionModel.Create

    class PUT(BaseModel):
        user_session: UserSessionModel.Update

    class SEARCH(BaseModel):
        user_session: UserSessionModel.Search

    class ResponseSingle(BaseModel):
        user_session: UserSessionModel

    class ResponsePlural(BaseModel):
        user_sessions: List[UserSessionModel]


class UserSessionManager(AbstractBLLManager):
    Model = UserSessionModel
    ReferenceModel = UserSessionReferenceModel
    NetworkModel = UserSessionNetworkModel
    DBClass = AuthSession

    def __init__(
        self,
        requester_id: str,
        target_user_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        self._users = None

    @property
    def users(self):
        """Get the user manager"""
        if self._users is None:
            self._users = UserManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._users

    def createValidation(self, entity):
        """Validate user session creation"""
        if not User.exists(
            requester_id=self.requester.id, db=self.db, id=entity.user_id
        ):
            raise HTTPException(status_code=404, detail="User not found")

        if AuthSession.exists(
            requester_id=self.requester.id, db=self.db, session_key=entity.session_key
        ):
            raise HTTPException(status_code=400, detail="Session key already exists")

    def revoke_session(self, session_id: str) -> Dict[str, str]:
        """Revoke a single session"""
        session = AuthSession.get(
            requester_id=self.requester.id, db=self.db, id=session_id
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        AuthSession.update(
            requester_id=self.requester.id,
            db=self.db,
            id=session_id,
            new_properties={"revoked": True, "is_active": False},
        )

        return {"message": "Session revoked successfully"}

    def update_activity(self, session_key: str) -> Dict[str, str]:
        """Update the last activity timestamp for a session"""
        sessions = AuthSession.list(
            requester_id=self.requester.id, db=self.db, session_key=session_key
        )

        if not sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[0]

        AuthSession.update(
            requester_id=self.requester.id,
            db=self.db,
            id=session.id,
            new_properties={"last_activity": datetime.utcnow()},
        )

        return {"message": "Session activity updated successfully"}

    def revoke_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user"""
        sessions = AuthSession.list(
            requester_id=self.requester.id,
            db=self.db,
            user_id=user_id,
            is_active=True,
            revoked=False,
        )

        revoked_count = 0
        for session in sessions:
            AuthSession.update(
                requester_id=self.requester.id,
                db=self.db,
                id=session.id,
                new_properties={"is_active": False, "revoked": True},
            )
            revoked_count += 1

        return revoked_count
