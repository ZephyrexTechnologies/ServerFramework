import logging
from typing import Optional, TypeVar

from sqlalchemy import Enum

from lib.Environment import env

# Type variable for generic models
T = TypeVar("T")

# Define system IDs with different permission levels
ROOT_ID = env("ROOT_ID")
SYSTEM_ID = env("SYSTEM_ID")
TEMPLATE_ID = env("TEMPLATE_ID")


def is_system_id(user_id: str) -> bool:
    """Check if the user ID is any of the system IDs."""
    return user_id in (ROOT_ID, SYSTEM_ID, TEMPLATE_ID)


def is_root_id(user_id: str) -> bool:
    """Check if the user ID is the ROOT_ID."""
    return user_id == ROOT_ID


def is_system_user_id(user_id: str) -> bool:
    """Check if the user ID is the SYSTEM_ID."""
    return user_id == SYSTEM_ID


def is_template_id(user_id: str) -> bool:
    """Check if the user ID is the TEMPLATE_ID."""
    return user_id == TEMPLATE_ID


def can_access_system_record(
    user_id: str, record_user_id: str, minimum_role: Optional[str] = None
) -> bool:
    """
    Determine if a user can access a system-owned record based on the system ID type.

    Args:
        user_id: The ID of the user requesting access
        record_user_id: The system ID that owns the record
        minimum_role: The minimum role required (if applicable)

    Returns:
        bool: True if access is granted, False otherwise
    """
    # ROOT_ID records are only accessible by ROOT_ID
    if record_user_id == ROOT_ID:
        return user_id == ROOT_ID

    # SYSTEM_ID records are accessible by ROOT_ID and SYSTEM_ID
    # For non-system users, regular permission checks will apply
    if record_user_id == SYSTEM_ID:
        if user_id in (ROOT_ID, SYSTEM_ID):
            return True
        # For regular users, if minimum_role is None or 'user', they can access
        # Otherwise, regular permission checks will apply
        if minimum_role in (None, "user"):
            return True

    # TEMPLATE_ID records are accessible by all users for reading
    # but only system users can modify them
    if record_user_id == TEMPLATE_ID:
        if user_id in (ROOT_ID, SYSTEM_ID, TEMPLATE_ID):
            return True
        # For regular users, if minimum_role is None or 'user', they can access
        # Otherwise (like for admin operations), they can't
        if minimum_role in (None, "user"):
            return True

    # Default: system records can only be accessed by system users
    return False


def gen_not_found_msg(classname):
    """Generate a standard 'not found' message for a given class."""
    return f"Request searched {classname} and could not find the required record."


def validate_columns(cls, updated=None, **kwargs):
    """
    Validate that the provided column names exist in the model.

    Args:
        cls: The model class
        updated: Dictionary of fields to update
        **kwargs: Additional filter parameters

    Raises:
        ValueError: If invalid columns are provided
    """
    valid_columns = {column.name for column in cls.__table__.columns}
    invalid_keys = [key for key in kwargs if key not in valid_columns]
    logging.debug(f"Valid columns for {cls.__name__}: {valid_columns}")
    logging.debug(f"Invalid keys for {cls.__name__}: {invalid_keys}")
    if updated:
        invalid_update = [key for key in updated if key not in valid_columns]
        logging.debug(f"Invalid update for {cls.__name__}: {invalid_update}")
    if invalid_keys or (updated and invalid_update):
        raise ValueError(
            f"Invalid keys for {cls.__name__} in validation: {invalid_keys}"
            if not updated
            else f"Invalid keys for {cls.__name__} in validation: (keys, update) {invalid_keys, invalid_update}"
        )


def get_referenced_records(record, visited=None):
    """
    Follow all permission_references chains to find the records that hold the actual permissions.

    Args:
        record: The record to start from
        visited: Set of already visited records to prevent infinite recursion

    Returns:
        list: All records that hold actual permissions (with user_id and team_id)
    """
    if visited is None:
        visited = set()

    # Create a unique identifier for the record to prevent infinite recursion
    record_id = (type(record).__name__, getattr(record, "id", None))

    # If we've already visited this record, we have a circular reference
    if record_id in visited:
        raise ValueError(f"Circular permission reference detected for {record_id}")

    visited.add(record_id)

    # Check for both permission_references (plural) and permission_reference (singular)
    has_plural_refs = (
        hasattr(record, "permission_references") and record.permission_references
    )
    has_singular_ref = (
        hasattr(record, "permission_reference") and record.permission_reference
    )

    # If record doesn't have any permission references, this is a leaf record
    if not has_plural_refs and not has_singular_ref:
        return [record]

    referenced_records = []

    # Follow each reference in permission_references (plural)
    if has_plural_refs:
        for ref_name in record.permission_references:
            # Get the reference attribute (relationship)
            ref_attr = getattr(record, ref_name, None)

            # Only follow this reference if it's populated
            if ref_attr is not None:
                try:
                    # Follow the reference recursively and collect all referenced records
                    referenced_records.extend(
                        get_referenced_records(ref_attr, visited.copy())
                    )
                except ValueError as e:
                    # Log the error but continue with other references
                    logging.error(f"Error following reference {ref_name}: {str(e)}")
                    continue

    # Follow permission_reference (singular) for backward compatibility
    elif has_singular_ref:
        ref_name = record.permission_reference
        ref_attr = getattr(record, ref_name, None)

        if ref_attr is not None:
            try:
                referenced_records.extend(
                    get_referenced_records(ref_attr, visited.copy())
                )
            except ValueError as e:
                logging.error(f"Error following reference {ref_name}: {str(e)}")
                pass

    # If we found referenced records, return them
    if referenced_records:
        return referenced_records

    # If all references were None or led to errors, return the current record
    return [record]


def find_create_permission_reference_chain(cls, db, visited=None):
    """
    Follow create_permission_reference chain to find the class that determines create permissions.

    Args:
        cls: The model class to start from
        db: Database session
        visited: Set of already visited classes to prevent infinite recursion

    Returns:
        tuple: (final_class, ref_attr_name) tuple with the class that determines permissions
               and the attribute name that references it
    """
    if visited is None:
        visited = set()

    # Prevent infinite recursion
    if cls in visited:
        raise ValueError(
            f"Circular create_permission_reference detected for {cls.__name__}"
        )

    visited.add(cls)

    # If the class has a create_permission_reference, follow it
    if hasattr(cls, "create_permission_reference") and cls.create_permission_reference:
        ref_name = cls.create_permission_reference

        # Get the relationship attribute from the class
        ref_attr = getattr(cls, ref_name, None)

        if ref_attr is None:
            raise ValueError(
                f"Invalid create_permission_reference '{ref_name}' in {cls.__name__}"
            )

        # Get the referenced model class
        if hasattr(ref_attr, "property") and hasattr(ref_attr.property, "mapper"):
            ref_model = ref_attr.property.mapper.class_

            # Recursively follow the chain
            return find_create_permission_reference_chain(ref_model, db, visited)
        else:
            raise ValueError(
                f"Invalid relationship attribute '{ref_name}' in {cls.__name__}"
            )

    # If no create_permission_reference, this class determines permissions
    return (cls, None)


def user_owns_record(user_id, record):
    """
    Check if the user owns the record by matching user_id with any of the record's
    referenced records' user_id if they exist.

    Args:
        user_id: The ID of the user to check
        record: The record to check ownership for

    Returns:
        bool: True if user owns the record or any of its referenced records
    """
    try:
        # Handle User table specifically
        if type(record).__name__ == "User":
            # User automatically owns their own record
            return user_id == record.id

        # Check for system ownership
        if hasattr(record, "user_id") and record.user_id is not None:
            # If system-owned record, apply special system access rules
            if is_system_id(record.user_id):
                return can_access_system_record(user_id, record.user_id)

            # Direct ownership check
            if user_id == record.user_id:
                return True

        # Check if the record has permission_references
        if (
            not hasattr(record, "permission_references")
            or not record.permission_references
        ):
            # If record doesn't have permission references, we've already checked
            # direct ownership above, so just return False
            return False

        # Follow permission reference chains
        referenced_records = get_referenced_records(record)

        # Check if user owns any of the referenced records
        for referenced_record in referenced_records:
            if (
                hasattr(referenced_record, "user_id")
                and referenced_record.user_id is not None
            ):
                # Check system ownership for referenced records
                if is_system_id(referenced_record.user_id):
                    if can_access_system_record(user_id, referenced_record.user_id):
                        return True
                # Check direct ownership
                elif user_id == referenced_record.user_id:
                    return True

        return False
    except ValueError as e:
        # If there's an error with permission references, fall back to direct check
        logging.error(f"Error checking ownership: {str(e)}")
        if not hasattr(record, "user_id") or record.user_id is None:
            return False

        # Check system ownership
        if is_system_id(record.user_id):
            return can_access_system_record(user_id, record.user_id)

        return user_id == record.user_id


def get_role_hierarchy(db):
    """
    Get the role hierarchy with roles ordered from least to most permissive.

    Returns:
        dict: Dictionary mapping role names to their level in the hierarchy (higher = more permissive)
    """
    # Import here to avoid circular imports
    from database.DB_Auth import Role

    # Get all roles
    roles = db.query(Role).all()

    # Build role hierarchy
    role_hierarchy = {}
    level = 0

    # Start with roles that have no parent (least permissive)
    current_level_roles = [role for role in roles if role.parent_id is None]

    while current_level_roles:
        # Add current level roles to hierarchy
        for role in current_level_roles:
            role_hierarchy[role.name] = level

        # Move to next level in hierarchy
        level += 1
        next_level_roles = []

        # Find child roles
        for parent_role in current_level_roles:
            children = [role for role in roles if role.parent_id == parent_role.id]
            next_level_roles.extend(children)

        current_level_roles = next_level_roles

    return role_hierarchy


def is_role_sufficient(user_role, minimum_role, role_hierarchy):
    """
    Check if the user's role is sufficient compared to the minimum required role.

    Args:
        user_role: The role name of the user
        minimum_role: The minimum role name required
        role_hierarchy: Dictionary mapping role names to their level in the hierarchy

    Returns:
        bool: True if the user's role is sufficient
    """
    if minimum_role is None:
        return True

    if user_role not in role_hierarchy or minimum_role not in role_hierarchy:
        return False

    # Higher level in hierarchy = more permissive
    return role_hierarchy[user_role] >= role_hierarchy[minimum_role]


def is_team_membership_expired(user_team):
    """
    Check if a user's team membership has expired.

    Args:
        user_team: The UserTeam object to check

    Returns:
        bool: True if membership has expired, False otherwise
    """
    from datetime import datetime

    # If there's no expiration date, the membership doesn't expire
    if not hasattr(user_team, "expires_at") or user_team.expires_at is None:
        return False

    # Check if the membership has expired
    return user_team.expires_at < datetime.now()


def is_user_on_team(user_id, team_id, db, minimum_role=None):
    """
    Check if user is a member of the specified team with sufficient role.

    Args:
        user_id: The ID of the user to check
        team_id: The ID of the team to check membership for
        db: Database session
        minimum_role: Minimum role name required (None means any role is sufficient)

    Returns:
        bool: True if user is on the team with sufficient role
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True  # ROOT_ID has access to all teams

    # Import here to avoid circular imports
    from database.DB_Auth import Role, UserTeam

    # Get the user's team membership
    user_team = (
        db.query(UserTeam, Role)
        .join(Role, UserTeam.role_id == Role.id)
        .filter(
            UserTeam.user_id == user_id,
            UserTeam.team_id == team_id,
            UserTeam.enabled == True,
        )
        .first()
    )

    if not user_team:
        return False

    # Check if the membership has expired
    if is_team_membership_expired(user_team[0]):
        return False

    # If no minimum role specified, any membership is sufficient
    if minimum_role is None:
        return True

    # Get the role hierarchy
    role_hierarchy = get_role_hierarchy(db)

    # Check if the user's role is sufficient
    return is_role_sufficient(user_team[1].name, minimum_role, role_hierarchy)


def is_user_on_team_recursive(user_id, team_id, db, minimum_role=None, visited=None):
    """
    Check if user is a member of the specified team or any parent team recursively
    with sufficient role.

    Args:
        user_id: The ID of the user to check
        team_id: The ID of the team to check membership for
        db: Database session
        minimum_role: Minimum role name required (None means any role is sufficient)
        visited: Set of already visited team IDs to prevent infinite recursion

    Returns:
        bool: True if user is a member of the team or any parent team with sufficient role
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True  # ROOT_ID has access to all teams

    # Import here to avoid circular imports
    from database.DB_Auth import Team

    if visited is None:
        visited = set()

    # Prevent infinite recursion
    if team_id in visited:
        return False

    visited.add(team_id)

    # Check direct membership with sufficient role
    if is_user_on_team(user_id, team_id, db, minimum_role):
        return True

    # Get parent team if exists
    team = db.query(Team).filter(Team.id == team_id).first()
    if team and team.parent_id:
        # Check parent team recursively
        return is_user_on_team_recursive(
            user_id, team.parent_id, db, minimum_role, visited
        )

    return False


def user_is_on_record_team(user_id, record, db, minimum_role=None):
    """
    Check if the user is on any of the record's teams or parent teams recursively
    with sufficient role. Follows all permission_references if they exist.

    Special handling for Team records:
    - For Team records, use the team's own ID for checking membership

    Args:
        user_id: The ID of the user to check
        record: The record to check access for
        db: Database session
        minimum_role: Minimum role name required (None means any role is sufficient)

    Returns:
        bool: True if user is on any of the record's referenced teams with sufficient role
    """
    try:
        # Special handling for system users
        if is_root_id(user_id):
            return True  # ROOT_ID has access to all teams

        # Handle Team table specifically
        if type(record).__name__ == "Team":
            # Check if user is on this team or parent teams
            return is_user_on_team_recursive(user_id, record.id, db, minimum_role)

        # Follow all permission reference chains if they exist
        referenced_records = get_referenced_records(record)

        # Check each referenced record for team membership
        for referenced_record in referenced_records:
            if (
                hasattr(referenced_record, "team_id")
                and referenced_record.team_id is not None
            ):
                if is_user_on_team_recursive(
                    user_id, referenced_record.team_id, db, minimum_role
                ):
                    return True

        return False
    except ValueError as e:
        # If there's an error with permission references, fall back to direct check
        logging.error(f"Error checking team membership: {str(e)}")
        if not hasattr(record, "team_id") or record.team_id is None:
            return False

        return is_user_on_team_recursive(user_id, record.team_id, db, minimum_role)


def users_share_team(user_id1, user_id2, db):
    """
    Check if two users share any team.

    Args:
        user_id1: First user ID
        user_id2: Second user ID
        db: Database session

    Returns:
        bool: True if users share at least one team
    """
    # Special handling for system users
    if is_root_id(user_id1) or is_root_id(user_id2):
        return True  # ROOT_ID is considered to share teams with everyone

    # Import here to avoid circular imports
    from database.DB_Auth import UserTeam

    # Get all teams for the first user
    user1_teams = (
        db.query(UserTeam.team_id)
        .filter(UserTeam.user_id == user_id1, UserTeam.enabled == True)
        .all()
    )

    # Convert to list of team IDs
    user1_team_ids = [team.team_id for team in user1_teams]

    # Check if user2 is on any of user1's teams
    shared_team = (
        db.query(UserTeam)
        .filter(
            UserTeam.user_id == user_id2,
            UserTeam.team_id.in_(user1_team_ids),
            UserTeam.enabled == True,
        )
        .first()
    )

    return shared_team is not None


def check_permission_table_access(user_id, cls, db, **kwargs):
    """
    Special permission check for the Permission table.
    Users need SHARE permission or admin access to the resource they're trying to assign permissions for.

    Args:
        user_id: The ID of the user to check
        cls: The Permission model class
        db: Database session
        **kwargs: Permission properties, including resource_type and resource_id

    Returns:
        tuple: (True/False, error_message) indicating if access is granted and why not if denied
    """
    # If not adding a Permission record, don't do special checks
    if cls.__tablename__ != "permissions":
        return (True, None)

    # For Permission entities, ensure user can manage permissions on the target resource
    resource_type = kwargs.get("resource_type")
    resource_id = kwargs.get("resource_id")

    if not resource_type or not resource_id:
        return (False, "Missing resource_type or resource_id for permission assignment")

    # Check if the user can manage permissions for this resource
    return can_manage_permissions(user_id, resource_type, resource_id, db)


def check_access_to_all_referenced_entities(
    user_id, cls, db, minimum_role=None, **kwargs
):
    """
    Check if the user has access to all referenced entities specified by foreign keys.

    Args:
        user_id: The ID of the user to check
        cls: The model class
        db: Database session
        minimum_role: Minimum role name required
        **kwargs: Foreign key values to check

    Returns:
        tuple: (True/False, missing_entity_info) tuple indicating if access is granted
               and which entity is missing if access is denied
    """
    # Special handling for Permission table
    if cls.__tablename__ == "permissions":
        can_access, error_msg = check_permission_table_access(
            user_id, cls, db, **kwargs
        )
        if not can_access:
            return (
                False,
                ("Permission", "resource", kwargs.get("resource_id"), error_msg),
            )

    # Get all the foreign key relationships
    if not hasattr(cls, "permission_references") or not cls.permission_references:
        return (True, None)

    # Check each reference from permission_references
    for ref_name in cls.permission_references:
        ref_id_field = f"{ref_name}_id"

        # Skip if this reference isn't in the kwargs
        if ref_id_field not in kwargs or kwargs[ref_id_field] is None:
            continue

        # Get the referenced model class
        ref_attr = getattr(cls, ref_name, None)
        if (
            not ref_attr
            or not hasattr(ref_attr, "property")
            or not hasattr(ref_attr.property, "mapper")
        ):
            continue

        ref_model = ref_attr.property.mapper.class_

        # Get the referenced record
        ref_id = kwargs[ref_id_field]
        ref_record = db.query(ref_model).filter(ref_model.id == ref_id).first()

        # If record doesn't exist, return False
        if not ref_record:
            return (False, (ref_model.__name__, ref_id_field, ref_id, "not_found"))

        # Check if user has access to this record
        if not ref_model.user_has_read_access(user_id, ref_id, db, minimum_role):
            return (False, (ref_model.__name__, ref_id_field, ref_id, "no_access"))

    # If all checks pass, user has access to all referenced entities
    return (True, None)


def user_owns_record_or_is_on_record_team(user_id, record, db, minimum_role=None):
    """
    Check if the user owns the record or is on any of the record's teams (or parent teams)
    with sufficient role. Follows all permission_references if they exist.

    Special handling for User and Team records:
    - For User records, if requester is the user, they have full permission;
      otherwise, they have read permission if they share a team with the user
    - For Team records, use the team's own ID for checking membership

    Args:
        user_id: The ID of the user to check
        record: The record to check access for
        db: Database session
        minimum_role: Minimum role name required (None means any role is sufficient)
            Only applies to team membership, not ownership

    Returns:
        bool: True if user owns the record or is on any of the record's teams with sufficient role
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True  # ROOT_ID has access to everything

    # Special handling for User table
    if type(record).__name__ == "User":
        # User automatically has permission to their own record
        if user_id == record.id:
            return True

        # For other users' records, check if they share any team
        # This provides read permission
        return users_share_team(user_id, record.id, db)

    # Special handling for Team table
    elif type(record).__name__ == "Team":
        # Check if user is on this team or parent teams
        return is_user_on_team_recursive(user_id, record.id, db, minimum_role)

    # For all other tables, use the standard logic
    return user_owns_record(user_id, record) or user_is_on_record_team(
        user_id, record, db, minimum_role
    )


def can_manage_permissions(user_id, resource_type, resource_id, db):
    """
    Check if a user can manage permissions for a resource.
    Users need SHARE permission or admin access to manage permissions.

    Args:
        user_id: The ID of the user to check
        resource_type: The type of resource to check
        resource_id: The ID of the resource to check
        db: Database session

    Returns:
        tuple: (bool, error_message) indicating if user can manage permissions and why not if they can't
    """
    # Special handling for system users
    if is_root_id(user_id):
        return (True, None)  # ROOT_ID can manage all permissions

    # Check for explicit SHARE permission
    if check_direct_permission(
        user_id, resource_type, resource_id, db, PermissionType.SHARE
    ):
        return (True, None)

    # Find the model class for this resource type
    import importlib
    import inspect

    from sqlalchemy.ext.declarative import DeclarativeMeta

    # Try to locate the model class
    model_class = None

    # Common database module paths
    db_modules = ["database.DB_Auth", "database.DB_Agents", "database.DB_Providers"]

    for module_name in db_modules:
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module):
                if (
                    isinstance(obj, DeclarativeMeta)
                    and hasattr(obj, "__tablename__")
                    and obj.__tablename__ == resource_type
                ):
                    model_class = obj
                    break
            if model_class:
                break
        except (ImportError, ModuleNotFoundError):
            continue

    if not model_class:
        return (False, f"Could not find model class for resource type: {resource_type}")

    # Check if the user has admin access to the resource
    if model_class.user_has_admin_access(user_id, resource_id, db):
        return (True, None)

    return (
        False,
        f"User {user_id} does not have permission to manage permissions for {resource_type} {resource_id}",
    )


def user_can_create_referenced_entity(cls, user_id, db, minimum_role=None, **kwargs):
    """
    Check if user can create an entity based on create_permission_reference.

    Args:
        cls: The model class
        user_id: The ID of the user requesting to create
        db: Database session
        minimum_role: Minimum role required
        **kwargs: Foreign key values and other parameters

    Returns:
        tuple: (True/False, error_message) indicating if the user can create and why not if they can't
    """
    # Special handling for system users
    if is_root_id(user_id):
        return (True, None)  # ROOT_ID can create anything

    # If no create_permission_reference, default to standard permission check
    if (
        not hasattr(cls, "create_permission_reference")
        or not cls.create_permission_reference
    ):
        return (True, None)

    try:
        # Special handling for Permission table
        if cls.__tablename__ == "permissions":
            resource_type = kwargs.get("resource_type")
            resource_id = kwargs.get("resource_id")

            if not resource_type or not resource_id:
                return (False, "Missing resource_type or resource_id for permission")

            # Check if the user can manage permissions for this resource
            can_manage, error_msg = can_manage_permissions(
                user_id, resource_type, resource_id, db
            )
            return (can_manage, error_msg)

        # Find the class that determines create permissions
        target_cls, _ = find_create_permission_reference_chain(cls, db)

        # If the target class is this class, no need for special checks
        if target_cls == cls:
            return (True, None)

        # Check if the user has sufficient permissions on the referenced entity
        ref_name = cls.create_permission_reference
        ref_id_field = f"{ref_name}_id"

        # If the reference ID isn't provided, we can't check permissions
        if ref_id_field not in kwargs or kwargs[ref_id_field] is None:
            return (False, f"Missing required reference: {ref_id_field}")

        ref_id = kwargs[ref_id_field]

        # Get the referenced entity
        ref_attr = getattr(cls, ref_name, None)
        if (
            not ref_attr
            or not hasattr(ref_attr, "property")
            or not hasattr(ref_attr.property, "mapper")
        ):
            return (False, f"Invalid reference attribute: {ref_name}")

        ref_model = ref_attr.property.mapper.class_

        # Check if the user has admin access to the referenced entity
        # Admin access is required to create entities that reference this entity
        if not ref_model.user_has_admin_access(user_id, ref_id, db):
            return (
                False,
                f"User {user_id} does not have admin access to {ref_model.__name__} {ref_id}",
            )

        return (True, None)

    except ValueError as e:
        logging.error(f"Error checking create permissions: {str(e)}")
        return (False, str(e))


class PermissionType(Enum):
    """Enum representing the type of permission."""

    VIEW = "can_view"
    EXECUTE = "can_execute"
    COPY = "can_copy"
    EDIT = "can_edit"
    DELETE = "can_delete"
    SHARE = "can_share"


class PermissionResult(Enum):
    """Enum representing the result of a permission check."""

    GRANTED = "granted"
    DENIED = "denied"
    NOT_FOUND = "not_found"
    ERROR = "error"
    EXPIRED = "expired"


def is_permission_expired(permission):
    """
    Check if a permission has expired.

    Args:
        permission: The Permission object to check

    Returns:
        bool: True if permission has expired, False otherwise
    """
    from datetime import datetime

    # If there's no expiration date, the permission doesn't expire
    if not hasattr(permission, "expires_at") or permission.expires_at is None:
        return False

    # Check if the permission has expired
    return permission.expires_at < datetime.now()


def check_direct_permission(
    user_id, resource_type, resource_id, db, permission_type=PermissionType.VIEW
):
    """
    Check if a user has a direct permission assignment for a resource.
    Takes into account user-specific, team-based, and role-based permissions.

    Args:
        user_id: The ID of the user to check
        resource_type: The type of resource to check
        resource_id: The ID of the resource to check
        db: Database session
        permission_type: The type of permission to check

    Returns:
        bool: True if the user has the requested permission, False otherwise
    """
    from database.DB_Auth import Permission, Role, UserTeam

    # Special handling for system users
    if is_root_id(user_id):
        return True  # ROOT_ID has all permissions

    # Get the permission field name
    permission_field = (
        permission_type.value
        if isinstance(permission_type, PermissionType)
        else permission_type
    )

    # Check for direct user permission
    user_permission = (
        db.query(Permission)
        .filter(
            Permission.resource_type == resource_type,
            Permission.resource_id == resource_id,
            Permission.user_id == user_id,
            getattr(Permission, permission_field) == True,
        )
        .first()
    )

    if user_permission and not is_permission_expired(user_permission):
        return True

    # Get all teams the user is a member of
    user_teams = (
        db.query(UserTeam)
        .filter(UserTeam.user_id == user_id, UserTeam.enabled == True)
        .all()
    )

    # Check team-based permissions
    for user_team in user_teams:
        # Skip expired team memberships
        if is_team_membership_expired(user_team):
            continue

        # Check for team permission
        team_permission = (
            db.query(Permission)
            .filter(
                Permission.resource_type == resource_type,
                Permission.resource_id == resource_id,
                Permission.team_id == user_team.team_id,
                getattr(Permission, permission_field) == True,
            )
            .first()
        )

        if team_permission and not is_permission_expired(team_permission):
            return True

        # Check for role-based permission
        role_permission = (
            db.query(Permission)
            .filter(
                Permission.resource_type == resource_type,
                Permission.resource_id == resource_id,
                Permission.role_id == user_team.role_id,
                getattr(Permission, permission_field) == True,
            )
            .first()
        )

        if role_permission and not is_permission_expired(role_permission):
            return True

    # Also check for role-based permissions that apply to all users
    # (where the role is null but role_id is not)
    role_permission = (
        db.query(Permission)
        .filter(
            Permission.resource_type == resource_type,
            Permission.resource_id == resource_id,
            Permission.user_id == None,
            Permission.team_id == None,
            Permission.role_id != None,
            getattr(Permission, permission_field) == True,
        )
        .all()
    )

    if role_permission:
        # Get all the user's roles
        user_roles = set()
        for user_team in user_teams:
            if not is_team_membership_expired(user_team):
                user_roles.add(user_team.role_id)

        # Get the role hierarchy
        role_hierarchy = get_role_hierarchy(db)

        # Check each role permission
        for perm in role_permission:
            if not is_permission_expired(perm):
                # Check if the user has the role or a superior role
                for user_role_id in user_roles:
                    user_role = db.query(Role).filter(Role.id == user_role_id).first()
                    perm_role = db.query(Role).filter(Role.id == perm.role_id).first()

                    if (
                        user_role
                        and perm_role
                        and is_role_sufficient(
                            user_role.name, perm_role.name, role_hierarchy
                        )
                    ):
                        return True

    return False


def user_can_view(user_id, record_cls, record_id, db):
    """
    Check if a user can view a record.
    Uses can_view from Permissions, or User role if no direct permission exists.

    Args:
        user_id: The ID of the user to check
        record_cls: The model class of the record
        record_id: The ID of the record to check
        db: Database session

    Returns:
        bool: True if user can view the record, False otherwise
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True

    # Get the record
    record = db.query(record_cls).filter(record_cls.id == record_id).first()
    if not record:
        return False

    # Check for direct permission first
    if check_direct_permission(
        user_id, record_cls.__tablename__, record_id, db, PermissionType.VIEW
    ):
        return True

    # Otherwise follow standard permission checks with 'user' role
    try:
        # Check permissions through referenced entities
        if hasattr(record, "permission_references") and record.permission_references:
            # We need to check ALL references, and ANY can grant permission
            for ref_name in record.permission_references:
                ref_attr = getattr(record, ref_name, None)
                if ref_attr is not None:
                    # Get ID of the referenced record
                    ref_id = getattr(ref_attr, "id", None)
                    if ref_id:
                        # Get class of the referenced record
                        ref_class = type(ref_attr)
                        # Check permissions on the referenced record
                        if user_can_view(user_id, ref_class, ref_id, db):
                            return True

            # If no reference granted permission, return False
            return False

        # Check direct ownership
        if hasattr(record, "user_id") and record.user_id == user_id:
            return True

        # Check for system-owned records with user access
        if hasattr(record, "user_id") and is_system_id(record.user_id):
            return can_access_system_record(user_id, record.user_id, "user")

        # Check team membership
        if hasattr(record, "team_id") and record.team_id:
            from database.Permissions import is_user_on_team_recursive

            if is_user_on_team_recursive(user_id, record.team_id, db, "user"):
                return True

        # Fall back to standard permission check
        return user_owns_record_or_is_on_record_team(user_id, record, db, "user")

    except Exception as e:
        logging.error(f"Error checking view permission: {str(e)}")
        return False


def user_can_execute(user_id, record_cls, record_id, db):
    """
    Check if a user can execute a record.
    Uses can_execute from Permissions, or User role if no direct permission exists.

    Args:
        user_id: The ID of the user to check
        record_cls: The model class of the record
        record_id: The ID of the record to check
        db: Database session

    Returns:
        bool: True if user can execute the record, False otherwise
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True

    # Get the record
    record = db.query(record_cls).filter(record_cls.id == record_id).first()
    if not record:
        return False

    # Check for direct permission first
    if check_direct_permission(
        user_id, record_cls.__tablename__, record_id, db, PermissionType.EXECUTE
    ):
        return True

    # Otherwise follow standard permission checks with 'user' role
    try:
        # Check permissions through referenced entities
        if hasattr(record, "permission_references") and record.permission_references:
            # We need to check ALL references, and ANY can grant permission
            for ref_name in record.permission_references:
                ref_attr = getattr(record, ref_name, None)
                if ref_attr is not None:
                    # Get ID of the referenced record
                    ref_id = getattr(ref_attr, "id", None)
                    if ref_id:
                        # Get class of the referenced record
                        ref_class = type(ref_attr)
                        # Check permissions on the referenced record
                        if user_can_execute(user_id, ref_class, ref_id, db):
                            return True

            # If no reference granted permission, return False
            return False

        # Check direct ownership
        if hasattr(record, "user_id") and record.user_id == user_id:
            return True

        # Check for system-owned records with user access
        if hasattr(record, "user_id") and is_system_id(record.user_id):
            return can_access_system_record(user_id, record.user_id, "user")

        # Check team membership
        if hasattr(record, "team_id") and record.team_id:
            from database.Permissions import is_user_on_team_recursive

            if is_user_on_team_recursive(user_id, record.team_id, db, "user"):
                return True

        # Fall back to standard permission check
        return user_owns_record_or_is_on_record_team(user_id, record, db, "user")

    except Exception as e:
        logging.error(f"Error checking execute permission: {str(e)}")
        return False


def user_can_copy(user_id, record_cls, record_id, db):
    """
    Check if a user can copy a record.
    Uses can_copy from Permissions, or User role if no direct permission exists.

    Args:
        user_id: The ID of the user to check
        record_cls: The model class of the record
        record_id: The ID of the record to check
        db: Database session

    Returns:
        bool: True if user can copy the record, False otherwise
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True

    # Get the record
    record = db.query(record_cls).filter(record_cls.id == record_id).first()
    if not record:
        return False

    # Check for direct permission first
    if check_direct_permission(
        user_id, record_cls.__tablename__, record_id, db, PermissionType.COPY
    ):
        return True

    # Otherwise follow standard permission checks with 'user' role
    try:
        # Check permissions through referenced entities
        if hasattr(record, "permission_references") and record.permission_references:
            # We need to check ALL references, and ANY can grant permission
            for ref_name in record.permission_references:
                ref_attr = getattr(record, ref_name, None)
                if ref_attr is not None:
                    # Get ID of the referenced record
                    ref_id = getattr(ref_attr, "id", None)
                    if ref_id:
                        # Get class of the referenced record
                        ref_class = type(ref_attr)
                        # Check permissions on the referenced record
                        if user_can_copy(user_id, ref_class, ref_id, db):
                            return True

            # If no reference granted permission, return False
            return False

        # Check direct ownership
        if hasattr(record, "user_id") and record.user_id == user_id:
            return True

        # Check for system-owned records with user access
        if hasattr(record, "user_id") and is_system_id(record.user_id):
            # For TEMPLATE_ID records, anyone can copy them
            if is_template_id(record.user_id):
                return True
            return can_access_system_record(user_id, record.user_id, "user")

        # Check team membership
        if hasattr(record, "team_id") and record.team_id:
            from database.Permissions import is_user_on_team_recursive

            if is_user_on_team_recursive(user_id, record.team_id, db, "user"):
                return True

        # Fall back to standard permission check
        return user_owns_record_or_is_on_record_team(user_id, record, db, "user")

    except Exception as e:
        logging.error(f"Error checking copy permission: {str(e)}")
        return False


def user_can_edit(user_id, record_cls, record_id, db):
    """
    Check if a user can edit a record.
    Uses can_edit from Permissions, or Admin role if no direct permission exists.

    Args:
        user_id: The ID of the user to check
        record_cls: The model class of the record
        record_id: The ID of the record to check
        db: Database session

    Returns:
        bool: True if user can edit the record, False otherwise
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True

    # Get the record
    record = db.query(record_cls).filter(record_cls.id == record_id).first()
    if not record:
        return False

    # Check for direct permission first
    if check_direct_permission(
        user_id, record_cls.__tablename__, record_id, db, PermissionType.EDIT
    ):
        return True

    # System entities require higher access level
    if hasattr(record, "user_id") and is_system_id(record.user_id):
        # Regular users cannot edit system-owned records
        # Only ROOT_ID can edit ROOT_ID/SYSTEM_ID records
        # ROOT_ID and SYSTEM_ID can edit TEMPLATE_ID records
        if is_root_id(record.user_id) or is_system_id(record.user_id):
            return is_root_id(user_id)
        elif is_template_id(record.user_id):
            return is_root_id(user_id) or is_system_id(user_id)

    # Otherwise follow standard permission checks with 'admin' role
    try:
        # Check permissions through referenced entities
        if hasattr(record, "permission_references") and record.permission_references:
            # We need to check ALL references, and ANY can grant permission
            for ref_name in record.permission_references:
                ref_attr = getattr(record, ref_name, None)
                if ref_attr is not None:
                    # Get ID of the referenced record
                    ref_id = getattr(ref_attr, "id", None)
                    if ref_id:
                        # Get class of the referenced record
                        ref_class = type(ref_attr)
                        # Check permissions on the referenced record
                        if user_can_edit(user_id, ref_class, ref_id, db):
                            return True

            # If no reference granted permission, return False
            return False

        # Check direct ownership
        if hasattr(record, "user_id") and record.user_id == user_id:
            return True

        # Check team membership
        if hasattr(record, "team_id") and record.team_id:
            from database.Permissions import is_user_on_team_recursive

            if is_user_on_team_recursive(user_id, record.team_id, db, "admin"):
                return True

        # Fall back to standard permission check
        return user_owns_record_or_is_on_record_team(user_id, record, db, "admin")

    except Exception as e:
        logging.error(f"Error checking edit permission: {str(e)}")
        return False


def user_can_delete(user_id, record_cls, record_id, db):
    """
    Check if a user can delete a record.
    Uses can_delete from Permissions, or Admin role if no direct permission exists.

    Args:
        user_id: The ID of the user to check
        record_cls: The model class of the record
        record_id: The ID of the record to check
        db: Database session

    Returns:
        bool: True if user can delete the record, False otherwise
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True

    # Get the record
    record = db.query(record_cls).filter(record_cls.id == record_id).first()
    if not record:
        return False

    # Check for direct permission first
    if check_direct_permission(
        user_id, record_cls.__tablename__, record_id, db, PermissionType.DELETE
    ):
        return True

    # System entities require higher access level
    if hasattr(record, "user_id") and is_system_id(record.user_id):
        # Regular users cannot delete system-owned records
        # Only ROOT_ID can delete ROOT_ID/SYSTEM_ID records
        # ROOT_ID and SYSTEM_ID can delete TEMPLATE_ID records
        if is_root_id(record.user_id) or is_system_id(record.user_id):
            return is_root_id(user_id)
        elif is_template_id(record.user_id):
            return is_root_id(user_id) or is_system_id(user_id)

    # Otherwise follow standard permission checks with 'admin' role
    try:
        # Check permissions through referenced entities
        if hasattr(record, "permission_references") and record.permission_references:
            # We need to check ALL references, and ANY can grant permission
            for ref_name in record.permission_references:
                ref_attr = getattr(record, ref_name, None)
                if ref_attr is not None:
                    # Get ID of the referenced record
                    ref_id = getattr(ref_attr, "id", None)
                    if ref_id:
                        # Get class of the referenced record
                        ref_class = type(ref_attr)
                        # Check permissions on the referenced record
                        if user_can_delete(user_id, ref_class, ref_id, db):
                            return True

            # If no reference granted permission, return False
            return False

        # Check direct ownership
        if hasattr(record, "user_id") and record.user_id == user_id:
            return True

        # Check team membership
        if hasattr(record, "team_id") and record.team_id:
            from database.Permissions import is_user_on_team_recursive

            if is_user_on_team_recursive(user_id, record.team_id, db, "admin"):
                return True

        # Fall back to standard permission check
        return user_owns_record_or_is_on_record_team(user_id, record, db, "admin")

    except Exception as e:
        logging.error(f"Error checking delete permission: {str(e)}")
        return False


def user_can_share(user_id, record_cls, record_id, db):
    """
    Check if a user can share a record (create permissions for it).
    Uses can_share from Permissions, or Admin role if no direct permission exists.

    Args:
        user_id: The ID of the user to check
        record_cls: The model class of the record
        record_id: The ID of the record to check
        db: Database session

    Returns:
        bool: True if user can share the record, False otherwise
    """
    # Special handling for system users
    if is_root_id(user_id):
        return True

    # Get the record
    record = db.query(record_cls).filter(record_cls.id == record_id).first()
    if not record:
        return False

    # Check for direct permission first
    if check_direct_permission(
        user_id, record_cls.__tablename__, record_id, db, PermissionType.SHARE
    ):
        return True

    # System entities require higher access level
    if hasattr(record, "user_id") and is_system_id(record.user_id):
        # Regular users cannot share system-owned records
        # Only ROOT_ID can share ROOT_ID/SYSTEM_ID records
        # ROOT_ID and SYSTEM_ID can share TEMPLATE_ID records
        if is_root_id(record.user_id) or is_system_id(record.user_id):
            return is_root_id(user_id)
        elif is_template_id(record.user_id):
            return is_root_id(user_id) or is_system_id(user_id)

    # Otherwise follow standard permission checks with 'admin' role
    try:
        # Check permissions through referenced entities
        if hasattr(record, "permission_references") and record.permission_references:
            # We need to check ALL references, and ANY can grant permission
            for ref_name in record.permission_references:
                ref_attr = getattr(record, ref_name, None)
                if ref_attr is not None:
                    # Get ID of the referenced record
                    ref_id = getattr(ref_attr, "id", None)
                    if ref_id:
                        # Get class of the referenced record
                        ref_class = type(ref_attr)
                        # Check permissions on the referenced record
                        if user_can_share(user_id, ref_class, ref_id, db):
                            return True

            # If no reference granted permission, return False
            return False

        # Check direct ownership
        if hasattr(record, "user_id") and record.user_id == user_id:
            return True

        # Check team membership
        if hasattr(record, "team_id") and record.team_id:
            from database.Permissions import is_user_on_team_recursive

            if is_user_on_team_recursive(user_id, record.team_id, db, "admin"):
                return True

        # Fall back to standard permission check
        return user_owns_record_or_is_on_record_team(user_id, record, db, "admin")

    except Exception as e:
        logging.error(f"Error checking share permission: {str(e)}")
        return False


def check_permission(user_id, record_cls, record_id, db, minimum_role=None):
    """
    Check if a user has permission to access a record.

    Args:
        user_id: The ID of the user requesting access
        record_cls: The model class
        record_id: The ID of the record to check
        db: Database session
        minimum_role: Minimum role required

    Returns:
        tuple: (PermissionResult, error_message) indicating the result and any error message
    """
    try:
        # Get the record
        record = db.query(record_cls).filter(record_cls.id == record_id).first()

        # Check if record exists
        if not record:
            return (PermissionResult.NOT_FOUND, gen_not_found_msg(record_cls.__name__))

        # Check explicit permissions in Permission table first
        # This overrides the normal permission system if a direct permission exists
        permission_granted = check_direct_permission(
            user_id,
            record_cls.__tablename__,
            record_id,
            db,
            (
                PermissionType.VIEW
                if minimum_role is None or minimum_role == "user"
                else (
                    PermissionType.EDIT
                    if minimum_role == "admin"
                    else PermissionType.SHARE
                )
            ),
        )

        if permission_granted:
            return (PermissionResult.GRANTED, None)

        # Check permissions using the standard permission model
        if record_cls.user_has_read_access(user_id, record_id, db, minimum_role):
            return (PermissionResult.GRANTED, None)
        else:
            return (
                PermissionResult.DENIED,
                f"User {user_id} does not have {minimum_role or 'read'} access to {record_cls.__name__} {record_id}",
            )

    except Exception as e:
        logging.error(f"Error checking permissions: {str(e)}")
        return (PermissionResult.ERROR, str(e))
