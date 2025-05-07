from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from urllib3 import HTTPResponse

from endpoints.AbstractEndpointRouter import AbstractEPRouter
from endpoints.StaticExampleFactory import ExampleGenerator
from lib.Environment import env
from logic.BLL_Auth import (
    FailedLoginAttemptManager,
    InvitationInviteeManager,
    InvitationManager,
    InvitationNetworkModel,
    PermissionManager,
    RoleManager,
    RoleNetworkModel,
    TeamManager,
    TeamMetadataManager,
    TeamNetworkModel,
    UserCredentialManager,
    UserManager,
    UserMetadataManager,
    UserModel,
    UserNetworkModel,
    UserRecoveryQuestionManager,
    UserSessionManager,
    UserSessionNetworkModel,
    UserTeamManager,
    UserTeamNetworkModel,
)


# Manager factory functions
def get_user_manager(
    user: UserModel = Depends(UserManager.auth),
    target_user_id: Optional[str] = Query(
        None, description="Target user ID for admin operations"
    ),
):
    """Get an initialized User manager instance."""
    return UserManager(requester_id=user.id, target_user_id=target_user_id or user.id)


def get_team_manager(
    user: UserModel = Depends(UserManager.auth),
    target_team_id: Optional[str] = Query(
        None, description="Target team ID for admin operations"
    ),
):
    """Get an initialized Team manager instance."""
    return TeamManager(requester_id=user.id, target_team_id=target_team_id)


def get_invitation_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized Invitation manager instance."""
    return InvitationManager(requester_id=user.id)


def get_invitation_invitee_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized InvitationInvitee manager instance."""
    return InvitationInviteeManager(requester_id=user.id)


def get_role_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized Role manager instance."""
    return RoleManager(requester_id=user.id)


def get_user_team_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized UserTeam manager instance."""
    return UserTeamManager(requester_id=user.id)


def get_team_metadata_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized TeamMetadata manager instance."""
    return TeamMetadataManager(requester_id=user.id)


def get_user_metadata_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized UserMetadata manager instance."""
    return UserMetadataManager(requester_id=user.id)


def get_user_credential_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized UserCredential manager instance."""
    return UserCredentialManager(requester_id=user.id)


def get_recovery_question_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized UserRecoveryQuestion manager instance."""
    return UserRecoveryQuestionManager(requester_id=user.id)


def get_failed_login_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized FailedLoginAttempt manager instance."""
    return FailedLoginAttemptManager(requester_id=user.id)


def get_user_session_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized UserSession manager instance."""
    return UserSessionManager(requester_id=user.id)


def get_permission_manager(user: UserModel = Depends(UserManager.auth)):
    """Get an initialized Permission manager instance."""
    return PermissionManager(requester_id=user.id)


# Generate examples using ExampleGenerator for OpenAPI documentation
user_examples = ExampleGenerator.generate_operation_examples(UserNetworkModel, "user")
user_examples["get"]["user"].update(
    {
        "email": "user@example.com",
        "display_name": "John Doe",
        "first_name": "John",
        "last_name": "Doe",
        "active": True,
        "mfa_count": 1,
        "image_url": "https://example.com/avatar.jpg",
    }
)

team_examples = ExampleGenerator.generate_operation_examples(TeamNetworkModel, "team")
team_examples["get"]["team"].update(
    {
        "name": "Marketing Team",
        "description": "Team responsible for marketing activities",
        "encryption_key": "enc_key_2af23c8d9f1e",
        "image_url": "https://example.com/team-logo.png",
    }
)

invitation_examples = ExampleGenerator.generate_operation_examples(
    InvitationNetworkModel, "invitation"
)
invitation_examples["get"]["invitation"].update(
    {
        "code": "ABCXYZ123",
        "max_uses": 5,
    }
)


# Generate examples for Role router
role_examples = ExampleGenerator.generate_operation_examples(RoleNetworkModel, "role")
role_examples["get"]["role"].update(
    {
        "name": "admin",
        "friendly_name": "Administrator",
        "mfa_count": 1,
        "password_change_frequency_days": 90,
    }
)

user_session_examples = ExampleGenerator.generate_operation_examples(
    UserSessionNetworkModel, "user_session"
)
user_session_examples["get"]["user_session"].update(
    {
        "session_key": "session_key_value",
        "device_type": "web",
        "browser": "Chrome",
        "last_activity": "2025-01-01T12:00:00Z",
    }
)

# Define standard response examples
login_example = {
    "content": {
        "application/json": {
            "example": {
                "id": "u1s2e3r4-5678-90ab-cdef-123456789012",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "display_name": "John Doe",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "teams": [
                    {
                        "id": "t1e2a3m4-5678-90ab-cdef-123456789012",
                        "name": "Marketing Team",
                        "description": "Team responsible for marketing activities",
                        "role_id": "r1o2l3e4-5678-90ab-cdef-123456789012",
                        "role_name": "admin",
                    }
                ],
                "detail": "https://example.com?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    }
}

register_example = {
    "content": {
        "application/json": {
            "example": {
                "id": "u1s2e3r4-5678-90ab-cdef-123456789012",
                "email": "newuser@example.com",
                "display_name": "New User",
                "first_name": "New",
                "last_name": "User",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    }
}

password_change_example = {
    "content": {
        "application/json": {"example": {"message": "Password changed successfully"}}
    }
}

revoke_session_example = {
    "content": {
        "application/json": {"example": {"message": "Session revoked successfully"}}
    }
}


# Create base routers
user_router = AbstractEPRouter(
    prefix="/v1/user",
    tags=["User Management"],
    manager_factory=get_user_manager,
    network_model_cls=UserNetworkModel,
    resource_name="user",
    example_overrides=user_examples,
    routes_to_register=[
        "search",
        "update",
        "delete",
    ],  # Exclude "create" and "batch_update"
)
team_router = AbstractEPRouter(
    prefix="/v1/team",
    tags=["Team Management"],
    manager_factory=get_team_manager,
    network_model_cls=TeamNetworkModel,
    resource_name="team",
    example_overrides=team_examples,
)

invitation_router = AbstractEPRouter(
    prefix="/v1/invitation",
    tags=["Team Management"],
    manager_factory=get_invitation_manager,
    network_model_cls=InvitationNetworkModel,
    resource_name="invitation",
    example_overrides=invitation_examples,
)


session_router = AbstractEPRouter(
    prefix="/v1/session",
    tags=["User Management"],
    manager_factory=get_user_session_manager,
    network_model_cls=UserSessionNetworkModel,
    resource_name="user_session",
    example_overrides=user_session_examples,
)

# Create nested routers
team_invitation_router = team_router.create_nested_router(
    parent_prefix="/v1/team",
    parent_param_name="team_id",
    child_resource_name="invitation",
    manager_property="invitations",
    tags=["Team Management"],
)

user_team_router = user_router.create_nested_router(
    parent_prefix="/v1/user",
    parent_param_name="user_id",
    child_resource_name="team",
    manager_property="teams",
    tags=["User Management"],
)

team_metadata_router = team_router.create_nested_router(
    parent_prefix="/v1/team",
    parent_param_name="team_id",
    child_resource_name="metadata",
    manager_property="metadata",
    tags=["Team Management"],
)

user_metadata_router = user_router.create_nested_router(
    parent_prefix="/v1/user",
    parent_param_name="user_id",
    child_resource_name="metadata",
    manager_property="metadata",
    tags=["User Management"],
)

user_session_router = user_router.create_nested_router(
    parent_prefix="/v1/user",
    parent_param_name="user_id",
    child_resource_name="session",
    manager_property="sessions",
    tags=["User Management"],
)


# Add custom routes to routers
@user_router.post(
    "",
    summary="Create (Register) a user",
    description="Registers a new user account.",
    response_model=UserNetworkModel.ResponseSingle,
    status_code=status.HTTP_201_CREATED,
    # Note: No auth dependency here
)
async def register_user(
    body: UserNetworkModel.POST = Body(...),
):
    """Register a new user."""
    user_manager = UserManager(requester_id=env("ROOT_ID"))
    user_data = body.user.model_dump(exclude_unset=True)
    created_user = user_manager.create(**user_data)
    return UserNetworkModel.ResponseSingle(user=created_user)


# User Router custom routes
@user_router.post(
    "/authorize",
    summary="Login with credentials",
    description="""
    Authenticates a user using their credentials and returns a JWT token.
    
    The endpoint accepts credentials via the Authorization header using Basic auth
    format (base64 encoded email:password) or through the request body.
    
    If successful, returns user information including teams and a JWT token
    for authentication in subsequent requests.
    """,
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "description": "Authentication successful",
            **login_example,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"},
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Too many failed login attempts"
        },
    },
)
async def login(
    request: Request,
    authorization: Optional[str] = Header(None),
    # login_data: Optional[UserNetworkModel.Login] = Body(None),
):
    """Authenticate a user with credentials"""
    user_manager = UserManager(requester_id=env("ROOT_ID"))
    return user_manager.login(
        # login_data=login_data.model_dump() if login_data else None,
        ip_address=request.headers.get("X-Forwarded-For") or request.client.host,
        req_uri=request.headers.get("Referer"),
        authorization=authorization,
    )


@user_router.get(
    "",
    summary="Get current user",
    description="Retrieves the current user's profile based on JWT token.",
    response_model=UserNetworkModel.ResponseSingle,
    status_code=status.HTTP_200_OK,
)
async def get_current_user(
    manager=Depends(get_user_manager),
    fields: Optional[List[str]] = Query(
        None, description="Fields to include in response"
    ),
):
    """Get the current user's profile."""
    user = manager.get(id=manager.requester.id, fields=fields)
    return UserNetworkModel.ResponseSingle(user=user)


@user_router.put(
    "",
    summary="Update current user",
    description="Updates the current user's profile.",
    response_model=UserNetworkModel.ResponseSingle,
    status_code=status.HTTP_200_OK,
)
async def update_current_user(
    body: UserNetworkModel.PUT = Body(...),
    manager=Depends(get_user_manager),
):
    """Update the current user's profile."""
    user_data = body.user.model_dump(exclude_unset=True)
    updated_user = manager.update(id=manager.requester.id, **user_data)
    return UserNetworkModel.ResponseSingle(user=updated_user)


@user_router.patch(
    "",
    summary="Change user password",
    description="Changes the password for the current user account.",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "description": "Password changed successfully",
            **password_change_example,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Current password is incorrect"},
    },
)
async def change_password(
    current_password: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    manager=Depends(get_user_manager),
):
    """Change the current user's password"""
    credential_manager = manager.credentials
    return credential_manager.change_password(
        user_id=manager.requester.id,
        current_password=current_password,
        new_password=new_password,
    )


@user_router.delete(
    "",
    summary="Delete current user",
    description="Marks the current user as deleted (deactivates the account).",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_current_user(
    manager=Depends(get_user_manager),
):
    """Deactivate (self-delete) the current user."""
    manager.update(id=manager.requester.id, active=False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Create standalone Role router for /v1/role/{id} GET, PUT, DELETE
role_router = AbstractEPRouter(
    prefix="/v1/role",
    tags=["Role Management"],
    manager_factory=get_role_manager,
    network_model_cls=RoleNetworkModel,
    resource_name="role",
    example_overrides=role_examples,
    routes_to_register=["get", "update", "delete"],  # Only these operations
)

# Create nested router for Role under Team for /v1/team/{team_id}/role POST, GET
team_role_router = team_router.create_nested_router(
    parent_prefix="/v1/team",
    parent_param_name="team_id",
    child_resource_name="role",
    manager_property="roles",  # Assuming TeamManager has a 'roles' property
    child_network_model_cls=RoleNetworkModel,
    tags=["Role Management"],
    routes_to_register=["create", "list", "search"],  # Add search
)


# Root level authorization verification endpoint
root_router = APIRouter(prefix="/v1", tags=["Authentication"])


@root_router.get(
    "",
    summary="Verify authorization",
    description="Verifies if the provided JWT token or API Key is valid.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Authorization is valid"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid authorization"},
    },
)
async def verify_authorization(
    authorization: str = Header(
        ..., description="Authorization header with Bearer token or API Key"
    ),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )
    UserManager.verify_token(token=authorization.replace("Bearer ", "").strip())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Team Router custom routes
@team_router.get(
    "/{id}/user",
    summary="Get team users",
    description="Gets users belonging to a team.",
    response_model=UserTeamNetworkModel.ResponsePlural,
    status_code=status.HTTP_200_OK,
)
async def get_team_users(
    id: str = Path(..., description="Team ID"),
    manager=Depends(get_team_manager),
):
    return UserTeamNetworkModel.ResponsePlural(
        user_teams=manager.user_teams.list(team_id=id, include=["users"])
    )


@team_router.put(
    "/{id}/user/{user_id}/role",
    summary="Update user role",
    description="Updates a user's role within a team.",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
)
async def update_user_role(
    id: str = Path(..., description="Team ID"),
    user_id: str = Path(..., description="User ID"),
    role_id: str = Body(..., embed=True),
    manager=Depends(get_team_manager),
):
    """Update a user's role within a team."""
    # Verify team exists
    team = manager.get(id=id)

    # Update the user's role using team manager
    existing_role = manager.user_teams.get(team_id=id, user_id=user_id)

    manager.user_teams.update(role_id=role_id, id=existing_role.id)
    return {"message": "Role updated successfully"}


# Team Invitation specific routes
@team_invitation_router.delete(
    "",
    summary="Revoke all invitations",
    description="Revokes ALL open invitations for a team.",
    # response_model=Dict[str, Any],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_all_invitations(
    team_id: str = Path(..., description="Team ID"),
    manager=Depends(get_invitation_manager),
):
    """Revoke all invitations for a team"""
    manager.batch_delete(ids=[team.id for team in manager.list(team_id=team_id)])
    return HTTPResponse(status=204)


# Session router endpoints
@session_router.get(
    "/{id}",
    summary="Get session details",
    description="Gets a specific user session.",
    response_model=UserSessionNetworkModel.ResponseSingle,
    status_code=status.HTTP_200_OK,
)
async def get_session(
    id: str = Path(..., description="Session ID"),
    manager=Depends(get_user_session_manager),
):
    """Get a user session"""
    return UserSessionNetworkModel.ResponseSingle(user_session=manager.get(id=id))


@session_router.get(
    "",
    summary="List sessions",
    description="Lists user sessions with optional filtering.",
    response_model=UserSessionNetworkModel.ResponsePlural,
    status_code=status.HTTP_200_OK,
)
async def list_sessions(
    manager=Depends(get_user_session_manager),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
):
    """List user sessions"""
    return UserSessionNetworkModel.ResponsePlural(
        user_sessions=manager.list(
            offset=offset,
            limit=limit,
        )
    )


@session_router.delete(
    "/{id}",
    summary="Revoke session",
    description="Revokes a user session.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_session(
    id: str = Path(..., description="Session ID"),
    manager=Depends(get_user_session_manager),
):
    """Revoke a user session"""
    manager.revoke_session(session_id=id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# User session router endpoints
@user_session_router.get(
    "/{id}",
    summary="Get user session",
    description="Gets a specific session for a user.",
    response_model=UserSessionNetworkModel.ResponseSingle,
    status_code=status.HTTP_200_OK,
)
async def get_user_session(
    user_id: str = Path(..., description="User ID"),
    id: str = Path(..., description="Session ID"),
    manager=Depends(get_user_session_manager),
):
    """Get a specific session for a user"""
    session = manager.get(id=id)
    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID '{id}' not found for user '{user_id}'",
        )
    return UserSessionNetworkModel.ResponseSingle(user_session=session)


@user_session_router.get(
    "",
    summary="List user sessions",
    description="Lists all sessions for a user.",
    response_model=UserSessionNetworkModel.ResponsePlural,
    status_code=status.HTTP_200_OK,
)
async def list_user_sessions(
    user_id: str = Path(..., description="User ID"),
    manager=Depends(get_user_session_manager),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
):
    """List all sessions for a user"""
    return UserSessionNetworkModel.ResponsePlural(
        user_sessions=manager.list(
            user_id=user_id,
            offset=offset,
            limit=limit,
        )
    )


# Placeholder Test Class (adjust imports and base class as needed)
# from tests.base import BaseTestCRUD  # Assuming this exists
# Create a merged router to include all auth endpoints
router = APIRouter()

# Include all routers
all_routers = [
    root_router,
    user_router,
    team_router,
    invitation_router,
    session_router,
    team_invitation_router,
    user_team_router,
    team_metadata_router,
    user_metadata_router,
    user_session_router,
    role_router,
    team_role_router,
]

for endpoint_router in all_routers:
    router.include_router(endpoint_router)
# Note: Adding test classes directly to endpoint files is unconventional.
# Consider moving this to a dedicated test file in the 'tests' directory.
# Also, ensure the BaseTestCRUD class and necessary fixtures/setup exist.
