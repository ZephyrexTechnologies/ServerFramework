from sqlalchemy import Column, Text
from sqlalchemy.orm import declared_attr, relationship

from database.Base import Base
from database.Mixins import BaseMixin, UpdateMixin
from lib.Environment import env


def get_extension_seed_list():
    # Import here to avoid circular dependency issues
    from logic.BLL_Extensions import ExtensionManager

    # Retrieve the list of runtime extensions from the ExtensionManager
    extensions = ExtensionManager(
        requester_id=env("SYSTEM_ID")
    ).list_runtime_extensions()

    seed_list = [
        {
            "name": extension_name,
            "description": getattr(
                __import__(
                    f"extensions.EXT_{extension_name}", fromlist=["description"]
                ),
                "description",
                "",
            ),
        }
        for extension_name in extensions
    ]

    # Append additional seed information as needed
    seed_list += [
        {
            "id": "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF",
            "name": "system",
            "friendly_name": "Artificial Intelligence Agents",
            "parent_id": None,
        },
    ]
    return seed_list


class Extension(Base, BaseMixin, UpdateMixin):
    __tablename__ = "extensions"
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True, default="")
    __table_args__ = {
        "comment": "An Extension represents a third-party integration. This is SEPARATE from an oauth link."
    }
    # TODO Make the seed logic check if it's a callable and call it if so.
    seed_list = get_extension_seed_list


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

    __table_args__ = {
        "comment": "An Ability represents something an Agent can *do* with an Extension."
    }


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
