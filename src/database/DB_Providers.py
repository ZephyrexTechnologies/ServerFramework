from sqlalchemy import Boolean, Column, Integer, Text
from sqlalchemy.orm import declared_attr, relationship

from database.AbstractDatabaseEntity import BaseMixin, ParentMixin, UpdateMixin
from database.Base import Base
from database.DB_Auth import TeamRefMixin, UserRefMixin
from database.DB_Extensions import (
    AbilityRefMixin,
    ExtensionRefMixin,
    get_extensions_from_env,
)


class Provider(Base, BaseMixin, UpdateMixin):
    __tablename__ = "providers"
    system = True
    name = Column(Text, nullable=False)
    friendly_name = Column(Text, nullable=True)
    agent_settings_json = Column(Text, nullable=True)
    # Define a class-specific seed_list to avoid sharing with other BaseMixin classes
    seed_id = "SYSTEM_ID"
    seed_list = [
        # Ensure we always have these two providers available for the provider instances
        {"name": "OpenAI", "friendly_name": "OpenAI"},
        {"name": "AGInYourPC", "friendly_name": "AGInYourPC"},
    ]
    __table_args__ = {
        "comment": "A Provider represents an external provder of data or functionality. It represents an extension provider. Settings should exclude model name and api key, as those are stored in provider instance as fields."
    }

    @classmethod
    def get_seed_list(cls):
        """Dynamically collect provider information from the environment and extensions"""
        import glob
        import importlib
        import logging
        import os

        # Initialize with any existing seed items
        seed_items = cls.seed_list.copy()

        # Get extensions from APP_EXTENSIONS
        extensions = get_extensions_from_env()

        for extension_name in extensions:

            # Get the extension directory
            try:
                current_file = os.path.abspath(__file__)
                src_dir = os.path.dirname(
                    os.path.dirname(current_file)
                )  # src directory
                extension_dir = os.path.join(src_dir, "extensions", extension_name)

                if not os.path.exists(extension_dir):
                    logging.warning(f"Extension directory not found: {extension_dir}")
                    continue

                provider_files = glob.glob(os.path.join(extension_dir, "PRV_*.py"))
                logging.info(
                    f"Found {len(provider_files)} provider files: {[os.path.basename(f) for f in provider_files]}"
                )

                for file_path in provider_files:
                    filename = os.path.basename(file_path)
                    if filename.endswith("_test.py"):
                        continue

                    # Extract the basename without extension and remove PRV_ prefix
                    base_name = (
                        os.path.basename(file_path)
                        .replace(".py", "")
                        .replace("PRV_", "")
                    )
                    logging.info(f"Processing provider: {base_name}")

                    try:
                        # Import the module dynamically
                        module_name = f"extensions.{extension_name}.{filename[:-3]}"
                        module = importlib.import_module(module_name)

                        # Find the provider class
                        class_name = f"{base_name}Provider"

                        # Check if the class exists in the module
                        if hasattr(module, class_name):
                            provider_class = getattr(module, class_name)

                            # Create a seed item for this provider
                            seed_item = {
                                "name": base_name,
                                "friendly_name": getattr(
                                    provider_class, "name", base_name
                                ),
                            }

                            # Check if this provider already exists in seed_items
                            exists = False
                            for item in seed_items:
                                if item.get("name") == base_name:
                                    exists = True
                                    break

                            if not exists:
                                seed_items.append(seed_item)
                                logging.info(f"Added provider {base_name} to seed list")
                    except Exception as e:
                        logging.error(
                            f"Error processing provider {base_name}: {str(e)}"
                        )

            except Exception as e:
                logging.error(f"Error processing extension {extension_name}: {str(e)}")

        logging.info(f"Provider seed list contains {len(seed_items)} items")
        return seed_items

    @classmethod
    def user_has_read_access(cls, user_id, id, db, minimum_role=None, referred=False):
        return True


class ProviderRefMixin:
    @declared_attr
    def provider_id(cls):
        # Required foreign key to the Provider table
        return cls.create_foreign_key(Provider, nullable=False)

    @declared_attr
    def provider(cls):
        return relationship(
            Provider.__name__,
            backref=cls.__tablename__,
        )


class _ProviderOptional(ProviderRefMixin):
    @declared_attr
    def provider_id(cls):
        return cls.create_foreign_key(Provider)  # nullable=True by default


ProviderRefMixin.Optional = _ProviderOptional


class ProviderExtension(
    Base, BaseMixin, UpdateMixin, ProviderRefMixin, ExtensionRefMixin
):
    __tablename__ = "provider_extensions"
    system = True
    seed_id = "SYSTEM_ID"
    __table_args__ = {
        "comment": "A ProviderExtension represents Provider support for an Extension."
    }

    @classmethod
    def get_seed_list(cls):
        """Create associations between providers and extensions"""
        import logging

        from sqlalchemy import or_, select

        from database.Base import get_session
        from database.DB_Extensions import Extension

        seed_items = []

        # Get a session for database access
        session = get_session()

        try:

            # First try by name

            # Check if 'system' extension exists instead
            stmt = select(Extension).where(Extension.name == "system")
            ai_extension = session.execute(stmt).scalar_one_or_none()

            if not ai_extension:
                # Try known UUID for system extension
                stmt = select(Extension).where(
                    Extension.id == "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF"
                )
                ai_extension = session.execute(stmt).scalar_one_or_none()

            logging.info(
                f"Using extension '{ai_extension.name}' (ID: {ai_extension.id}) for provider extensions"
            )

            # Get all providers to associate with the extension
            stmt = select(Provider)
            providers = session.execute(stmt).scalars().all()

            for provider in providers:
                # Skip already existing associations
                stmt = select(ProviderExtension).where(
                    ProviderExtension.provider_id == provider.id,
                    ProviderExtension.extension_id == ai_extension.id,
                )
                existing = session.execute(stmt).scalar_one_or_none()

                if not existing:
                    seed_item = {
                        "provider_id": str(provider.id),
                        "extension_id": str(ai_extension.id),
                    }
                    seed_items.append(seed_item)
                    logging.info(
                        f"Added provider extension for {provider.name} with extension {ai_extension.name}"
                    )

            logging.info(f"Created {len(seed_items)} provider extension seed items")
        except Exception as e:
            logging.error(f"Error creating provider extensions: {e}")
        finally:
            session.close()

        return seed_items


class ProviderInstance(
    Base,
    BaseMixin,
    UpdateMixin,
    UserRefMixin.Optional,
    TeamRefMixin.Optional,
    ProviderRefMixin,
):
    __tablename__ = "provider_instances"
    name = Column(Text, nullable=False)
    model_name = Column(Text, nullable=True)
    api_key = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    seed_id = "ROOT_ID"
    __table_args__ = {
        "comment": "A ProviderInstance represents a User or Team's instance of a Provider. They can have multiple of the same Provider."
    }

    @classmethod
    def get_seed_list(cls):
        """Create system provider instances for available API keys"""
        import logging

        from sqlalchemy import select

        from database.Base import get_session
        from lib.Environment import env

        seed_items = []

        # Get all providers with API keys from environment variables
        api_key_mapping = {
            "OpenAI": env("OPENAI_API_KEY"),
            "AGInYourPC": env("AGINYOURPC_API_KEY"),
        }

        # Get a session for database access
        session = get_session()

        try:
            for provider_name, api_key in api_key_mapping.items():
                if not api_key:
                    logging.warning(f"No API key found for {provider_name}")
                    continue

                # Look up the provider by name from the database
                stmt = select(Provider).where(Provider.name == provider_name)
                provider = session.execute(stmt).scalar_one_or_none()

                if not provider:
                    # If the provider doesn't exist in the database yet, just use the name
                    # It will be linked correctly during the actual seeding process
                    logging.warning(
                        f"Provider {provider_name} not found in database yet."
                    )

                    # Create a seed item for the provider instance
                    seed_item = {
                        "name": f"System_{provider_name}",
                        "api_key": api_key,
                        # For OpenAI, set a default model
                        "model_name": "gpt-4" if provider_name == "OpenAI" else None,
                        # Use provider name for lookup - special handling in seeding will connect it
                        "_provider_name": provider_name,  # This is a temporary field to be processed by seeding
                        "enabled": True,
                    }

                    seed_items.append(seed_item)
                    logging.info(
                        f"Added provider instance for {provider_name} without provider_id"
                    )
                else:
                    # Create a seed item for the provider instance with provider_id
                    seed_item = {
                        "name": f"System_{provider_name}",
                        "api_key": api_key,
                        # For OpenAI, set a default model
                        "model_name": "gpt-4" if provider_name == "OpenAI" else None,
                        "provider_id": str(
                            provider.id
                        ),  # Convert UUID to string if needed
                        "enabled": True,
                    }

                    seed_items.append(seed_item)
                    logging.info(
                        f"Added provider instance for {provider_name} with provider_id {provider.id}"
                    )
        except Exception as e:
            logging.error(f"Error creating provider instances: {e}")
        finally:
            session.close()

        logging.info(f"Created {len(seed_items)} provider instance seed items")
        return seed_items


class ProviderInstanceRefMixin:
    @declared_attr
    def provider_instance_id(cls):
        # Required foreign key to the ProviderInstance table
        return cls.create_foreign_key(ProviderInstance, nullable=False)

    @declared_attr
    def provider_instance(cls):
        return relationship(
            ProviderInstance.__name__,
            backref=cls.__tablename__,
        )


class _ProviderInstanceOptional(ProviderInstanceRefMixin):
    @declared_attr
    def provider_instance_id(cls):
        return cls.create_foreign_key(ProviderInstance)  # nullable=True by default


ProviderInstanceRefMixin.Optional = _ProviderInstanceOptional


class ProviderExtensionAbility(Base, BaseMixin, UpdateMixin, AbilityRefMixin):
    __tablename__ = "provider_extension_abilities"
    system = True

    @declared_attr
    def provider_extension_id(cls):
        return cls.create_foreign_key(ProviderExtension, nullable=False)

    provider_extension = relationship(ProviderExtension.__name__, backref="abilities")
    __table_args__ = {
        "comment": "A ProviderExtensionAbility represents a ProviderExtension and Ability combination. This allows for a provider to provide partial functionality to an extension, for example SendGrid only provides sending email, but not an inbox."
    }


class ProviderInstanceUsage(
    Base,
    BaseMixin,
    UpdateMixin,
    UserRefMixin.Optional,
    TeamRefMixin.Optional,
    ProviderInstanceRefMixin,
):
    __tablename__ = "provider_instance_usage"

    # provider_instance_id and provider_instance relationship defined by mixin

    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    __table_args__ = {
        "comment": "A ProviderInstanceUsage represents a User's usage of a provider. If team_id is also populated, it was used on behalf of a team by a user. Lack of a record means a user has never used the ProviderInstance. Note that ProviderInstances lower on a rotation may be seldom/never used."
    }


class ProviderInstanceSetting(Base, BaseMixin, UpdateMixin, ProviderInstanceRefMixin):
    __tablename__ = "provider_instance_settings"

    # provider_instance_id and provider_instance relationship defined by mixin

    key = Column(Text, nullable=False)
    value = Column(Text, nullable=True)
    __table_args__ = {
        "comment": "A ProviderInstanceSetting represents a non-default configuration setting for a User or Team's instance of an Provider."
    }


class ProviderInstanceExtensionAbility(
    Base, BaseMixin, UpdateMixin, ProviderInstanceRefMixin
):
    __tablename__ = "provider_instance_extension_abilities"

    # provider_instance_id and provider_instance relationship defined by mixin

    @declared_attr
    def provider_extension_ability_id(cls):
        return cls.create_foreign_key(ProviderExtensionAbility, nullable=False)

    provider_extension_ability = relationship(
        ProviderExtensionAbility.__name__, backref="instance_abilities"
    )
    state = Column(Boolean, nullable=False, default=True)
    forced = Column(Boolean, nullable=False, default=False)
    __table_args__ = {
        "comment": "A ProviderInstanceExtensionAbility represents whether an ability is enabled for that ProviderInstance. Forced abilities are always enabled downstream (Companies can force all Users and their Agents within Team Scope to use them, and Users can force their own Agents to use them). Nonpresence of a record is equivalent to state=False, forced=False."
    }


class Rotation(
    Base, BaseMixin, UpdateMixin, UserRefMixin.Optional, TeamRefMixin.Optional
):
    __tablename__ = "rotations"
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    __table_args__ = {
        "comment": "A Rotation represents a collection of Providers to be used by one or more Agents. All Agents interface with Providers through a Rotation."
    }


class RotationProviderInstance(
    Base, BaseMixin, UpdateMixin, ParentMixin, ProviderInstanceRefMixin
):
    __tablename__ = "rotation_provider_instances"

    @declared_attr
    def rotation_id(cls):
        return cls.create_foreign_key(Rotation, nullable=False)

    rotation = relationship(Rotation.__name__, backref="provider_instances")

    # provider_instance_id and provider_instance relationship defined by mixin

    permission_references = ["rotation"]
    __table_args__ = {
        "comment": "A RotationProviderInstance represents a link between a Rotation and a ProviderInstance. Order is determined by record parentage (NULL parent is first)."
    }
