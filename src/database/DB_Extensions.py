from sqlalchemy import Column, Text
from sqlalchemy.orm import declared_attr, relationship

from database.AbstractDatabaseEntity import BaseMixin, UpdateMixin
from database.Base import Base
from lib.Environment import env


def get_extensions_from_env():
    """Get extensions from the APP_EXTENSIONS environment variable"""
    import logging

    # Get extensions from APP_EXTENSIONS environment variable
    app_extensions = env("APP_EXTENSIONS")
    if app_extensions:
        extension_list = [
            ext.strip() for ext in app_extensions.split(",") if ext.strip()
        ]
        if extension_list:
            logging.info(f"Using extensions from APP_EXTENSIONS: {extension_list}")
            return extension_list
    return []


class Extension(Base, BaseMixin, UpdateMixin):
    __tablename__ = "extensions"
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True, default="")
    __table_args__ = {
        "comment": "An Extension represents a third-party integration. This is SEPARATE from an oauth link."
    }

    # Define basic seed data to avoid circular imports
    seed_id = "SYSTEM_ID"
    seed_list = [
        {
            "id": "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF",
            "name": "system",
            "description": "System-level capabilities",
        },
    ]
    system = True

    @classmethod
    def get_seed_list(cls):
        """Dynamically get the seed list to avoid circular imports"""
        import logging

        # Start with the basic seed list
        dynamic_seed_list = cls.seed_list.copy()

        # Add extensions from APP_EXTENSIONS environment variable
        extensions = get_extensions_from_env()

        for extension_name in extensions:
            # Skip duplicates
            if any(item.get("name") == extension_name for item in dynamic_seed_list):
                continue

            # Add the extension to the seed list
            try:
                # Try to get the description from the EXT_{extension_name} module
                try:
                    description = getattr(
                        __import__(
                            f"extensions.EXT_{extension_name}", fromlist=["description"]
                        ),
                        "description",
                        "",
                    )
                except (ImportError, AttributeError):
                    description = f"{extension_name} extension"

                dynamic_seed_list.append(
                    {
                        "name": extension_name,
                        "description": description,
                    }
                )
                logging.info(f"Added extension to seed list: {extension_name}")
            except Exception as e:
                logging.error(
                    f"Error adding extension {extension_name} to seed list: {str(e)}"
                )

        logging.info(f"Extension seed list contains {len(dynamic_seed_list)} items")
        return dynamic_seed_list

    @classmethod
    def user_has_read_access(cls, user_id, id, db, minimum_role=None, referred=False):
        """Allow all users to read extensions."""
        return True

    @classmethod
    def user_has_admin_access(cls, user_id, id, db):
        """Check if user has admin access to this record.
        For system entities, only ROOT_ID and SYSTEM_ID have admin access."""
        from database.StaticPermissions import is_root_id, is_system_user_id

        # Only root or system users can edit/delete system entities
        return is_root_id(user_id) or is_system_user_id(user_id)


class ExtensionRefMixin:
    @declared_attr
    def extension_id(cls):
        # Required foreign key to the Extension table
        return cls.create_foreign_key(Extension, nullable=False)

    @declared_attr
    def extension(cls):
        return relationship(
            Extension.__name__,
            backref=cls.__tablename__,
        )


class _ExtensionOptional(ExtensionRefMixin):
    @declared_attr
    def extension_id(cls):
        return cls.create_foreign_key(Extension)


ExtensionRefMixin.Optional = _ExtensionOptional


class Ability(Base, BaseMixin, UpdateMixin, ExtensionRefMixin):
    __tablename__ = "abilities"
    name = Column(Text, nullable=False)
    system = True
    __table_args__ = {"comment": "An Ability represents something an extension can do."}

    @classmethod
    def user_has_read_access(cls, user_id, id, db, minimum_role=None, referred=False):
        """Allow all users to read abilities."""
        return True

    @classmethod
    def user_has_admin_access(cls, user_id, id, db):
        """Check if user has admin access to this record.
        For system entities, only ROOT_ID and SYSTEM_ID have admin access."""
        from database.StaticPermissions import is_root_id, is_system_user_id

        # Only root or system users can edit/delete system entities
        return is_root_id(user_id) or is_system_user_id(user_id)


class AbilityRefMixin:
    @declared_attr
    def ability_id(cls):
        # Required foreign key to the Ability table
        return cls.create_foreign_key(Ability, nullable=False)

    @declared_attr
    def ability(cls):
        return relationship(
            Ability.__name__,
            backref=cls.__tablename__,
        )


class _AbilityOptional(AbilityRefMixin):
    @declared_attr
    def ability_id(cls):
        return cls.create_foreign_key(Ability)


AbilityRefMixin.Optional = _AbilityOptional
