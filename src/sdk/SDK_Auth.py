import base64
from typing import Any, Dict, Optional

from .AbstractSDKHandler import AbstractSDKHandler, AuthenticationError


class AuthSDK(AbstractSDKHandler):
    """SDK for authentication and user management.

    This class provides methods for user authentication, registration,
    and management of users, teams, roles, and sessions.
    """

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login with email and password credentials.

        Args:
            email: User email
            password: User password

        Returns:
            User information including JWT token and teams

        Raises:
            AuthenticationError: If authentication fails
        """
        # Create basic auth header
        auth_string = f"{email}:{password}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_auth}"}

        try:
            response = self._request(
                "POST",
                "/v1/user/authorize",
                headers=headers,
                resource_name="user",
            )

            # Update token with the new one from login
            if "token" in response:
                self.token = response["token"]

            return response
        except Exception as e:
            raise AuthenticationError(f"Login failed: {str(e)}")

    def register(
        self,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new user.

        Args:
            email: User email
            password: User password
            first_name: User first name
            last_name: User last name
            display_name: User display name

        Returns:
            New user information including JWT token
        """
        user_data = {
            "user": {
                "email": email,
                "password": password,
            }
        }

        if first_name:
            user_data["user"]["first_name"] = first_name
        if last_name:
            user_data["user"]["last_name"] = last_name
        if display_name:
            user_data["user"]["display_name"] = display_name

        response = self.post("/v1/user", user_data, resource_name="user")

        # Update token with the new one if provided
        if "token" in response:
            self.token = response["token"]

        return response

    def verify_token(self) -> bool:
        """Verify if the current token is valid.

        Returns:
            True if token is valid, False otherwise
        """
        if not self.token:
            return False

        try:
            self.get("/v1", resource_name="auth")
            return True
        except:
            return False

    def change_password(
        self, current_password: str, new_password: str
    ) -> Dict[str, str]:
        """Change the current user's password.

        Args:
            current_password: Current password
            new_password: New password

        Returns:
            Status message
        """
        data = {
            "current_password": current_password,
            "new_password": new_password,
        }

        return self.patch("/v1/user", data, resource_name="user")

    def get_current_user(self) -> Dict[str, Any]:
        """Get the current user's profile.

        Returns:
            Current user information
        """
        return self.get("/v1/user", resource_name="user")

    def update_current_user(self, **user_data) -> Dict[str, Any]:
        """Update the current user's profile.

        Args:
            **user_data: User data to update

        Returns:
            Updated user information
        """
        data = {"user": user_data}
        return self.put("/v1/user", data, resource_name="user")

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get a user by ID.

        Args:
            user_id: User ID

        Returns:
            User information
        """
        return self.get(f"/v1/user/{user_id}", resource_name="user")

    def list_users(
        self,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """List users with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            List of users
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        return self.get("/v1/user", query_params=params, resource_name="users")

    def search_users(
        self, criteria: Dict[str, Any], offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """Search for users.

        Args:
            criteria: Search criteria
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of matching users
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.post(
            "/v1/user/search", criteria, query_params=params, resource_name="users"
        )

    def delete_user(self, user_id: str) -> None:
        """Delete a user.

        Args:
            user_id: User ID
        """
        self.delete(f"/v1/user/{user_id}", resource_name="user")

    def create_team(
        self, name: str, description: Optional[str] = None, **team_data
    ) -> Dict[str, Any]:
        """Create a new team.

        Args:
            name: Team name
            description: Team description
            **team_data: Additional team data

        Returns:
            New team information
        """
        data = {
            "team": {
                "name": name,
                **team_data,
            }
        }

        if description:
            data["team"]["description"] = description

        return self.post("/v1/team", data, resource_name="team")

    def get_team(self, team_id: str) -> Dict[str, Any]:
        """Get a team by ID.

        Args:
            team_id: Team ID

        Returns:
            Team information
        """
        return self.get(f"/v1/team/{team_id}", resource_name="team")

    def update_team(self, team_id: str, **team_data) -> Dict[str, Any]:
        """Update a team.

        Args:
            team_id: Team ID
            **team_data: Team data to update

        Returns:
            Updated team information
        """
        data = {"team": team_data}
        return self.put(f"/v1/team/{team_id}", data, resource_name="team")

    def list_teams(
        self,
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """List teams with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            List of teams
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        return self.get("/v1/team", query_params=params, resource_name="teams")

    def delete_team(self, team_id: str) -> None:
        """Delete a team.

        Args:
            team_id: Team ID
        """
        self.delete(f"/v1/team/{team_id}", resource_name="team")

    def get_team_users(self, team_id: str) -> Dict[str, Any]:
        """Get users belonging to a team.

        Args:
            team_id: Team ID

        Returns:
            List of team users with their roles
        """
        return self.get(f"/v1/team/{team_id}/user", resource_name="team_users")

    def update_user_role(
        self, team_id: str, user_id: str, role_id: str
    ) -> Dict[str, str]:
        """Update a user's role within a team.

        Args:
            team_id: Team ID
            user_id: User ID
            role_id: Role ID

        Returns:
            Status message
        """
        data = {"role_id": role_id}
        return self.put(
            f"/v1/team/{team_id}/user/{user_id}/role", data, resource_name="user_role"
        )

    def create_invitation(
        self,
        team_id: str,
        role_id: str,
        email: Optional[str] = None,
        max_uses: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a team invitation.

        Args:
            team_id: Team ID
            role_id: Role ID for the invitation
            email: Email to invite (optional for general invitations)
            max_uses: Maximum number of times the invitation can be used

        Returns:
            New invitation information
        """
        data = {
            "invitation": {
                "team_id": team_id,
                "role_id": role_id,
            }
        }

        if email:
            data["invitation"]["email"] = email
        if max_uses:
            data["invitation"]["max_uses"] = max_uses

        return self.post("/v1/invitation", data, resource_name="invitation")

    def get_invitation(self, invitation_id: str) -> Dict[str, Any]:
        """Get an invitation by ID.

        Args:
            invitation_id: Invitation ID

        Returns:
            Invitation information
        """
        return self.get(f"/v1/invitation/{invitation_id}", resource_name="invitation")

    def delete_invitation(self, invitation_id: str) -> None:
        """Delete an invitation.

        Args:
            invitation_id: Invitation ID
        """
        self.delete(f"/v1/invitation/{invitation_id}", resource_name="invitation")

    def revoke_all_invitations(self, team_id: str) -> None:
        """Revoke all invitations for a team.

        Args:
            team_id: Team ID
        """
        self.delete(f"/v1/team/{team_id}/invitation", resource_name="invitations")

    def create_role(
        self, team_id: str, name: str, friendly_name: str, **role_data
    ) -> Dict[str, Any]:
        """Create a role within a team.

        Args:
            team_id: Team ID
            name: Role name (system name)
            friendly_name: User-friendly role name
            **role_data: Additional role data

        Returns:
            New role information
        """
        data = {
            "role": {
                "team_id": team_id,
                "name": name,
                "friendly_name": friendly_name,
                **role_data,
            }
        }

        return self.post(f"/v1/team/{team_id}/role", data, resource_name="role")

    def get_role(self, role_id: str) -> Dict[str, Any]:
        """Get a role by ID.

        Args:
            role_id: Role ID

        Returns:
            Role information
        """
        return self.get(f"/v1/role/{role_id}", resource_name="role")

    def update_role(self, role_id: str, **role_data) -> Dict[str, Any]:
        """Update a role.

        Args:
            role_id: Role ID
            **role_data: Role data to update

        Returns:
            Updated role information
        """
        data = {"role": role_data}
        return self.put(f"/v1/role/{role_id}", data, resource_name="role")

    def list_team_roles(
        self,
        team_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """List roles within a team.

        Args:
            team_id: Team ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of roles
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.get(
            f"/v1/team/{team_id}/role", query_params=params, resource_name="roles"
        )

    def delete_role(self, role_id: str) -> None:
        """Delete a role.

        Args:
            role_id: Role ID
        """
        self.delete(f"/v1/role/{role_id}", resource_name="role")

    def get_sessions(self, offset: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List user sessions.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of user sessions
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.get("/v1/session", query_params=params, resource_name="sessions")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session information
        """
        return self.get(f"/v1/session/{session_id}", resource_name="session")

    def revoke_session(self, session_id: str) -> None:
        """Revoke a user session.

        Args:
            session_id: Session ID
        """
        self.delete(f"/v1/session/{session_id}", resource_name="session")

    def get_user_sessions(
        self, user_id: str, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """Get sessions for a specific user.

        Args:
            user_id: User ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of user's sessions
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return self.get(
            f"/v1/user/{user_id}/session",
            query_params=params,
            resource_name="user_sessions",
        )
