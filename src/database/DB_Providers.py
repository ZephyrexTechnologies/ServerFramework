from sqlalchemy import Boolean, Column, Integer, Text
from sqlalchemy.orm import declared_attr, relationship

from database.Base import Base
from database.DB_Auth import TeamRefMixin, UserRefMixin
from database.DB_Extensions import AbilityRefMixin, ExtensionRefMixin
from database.Mixins import BaseMixin, ParentMixin, UpdateMixin


def get_provider_seed_list():
    from logic.BLL_Providers import ProviderManager

    return [
        {
            "name": provider_name,
            "settings": ProviderManager.get_runtime_provider_options(provider_name),
        }
        for provider_name in ProviderManager.list_runtime_providers()
    ]


class Provider(Base, BaseMixin, UpdateMixin):
    __tablename__ = "providers"
    system = True
    name = Column(Text, nullable=False)
    agent_settings_json = Column(Text, nullable=True)
    __table_args__ = {
        "comment": "A Provider represents an external provder of data or functionality. If extension_id is null, it represents an AI provider. If it is not, it represents an extension provider. Settings should exclude model name and api key, as those are stored in provider instance as fields."
    }
    seed_list = get_provider_seed_list

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
    __table_args__ = {
        "comment": "A ProviderExtension represents Provider support for an Extension."
    }


class ProviderExtensionAbility(Base, BaseMixin, UpdateMixin, AbilityRefMixin):
    __tablename__ = "provider_extension_abilities"

    @declared_attr
    def provider_extension_id(cls):
        return cls.create_foreign_key(ProviderExtension, nullable=False)

    provider_extension = relationship(ProviderExtension.__name__, backref="abilities")
    __table_args__ = {
        "comment": "A ProviderExtensionAbility represents a ProviderExtension and Ability combination. This allows for a provider to provide partial functionality to an extension, for example SendGrid only provides sending email, but not an inbox."
    }


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
    __table_args__ = {
        "comment": "A ProviderInstance represents a User or Team's instance of a Provider. They can have multiple of the same Provider."
    }


class ProviderInstanceUsage(
    Base, BaseMixin, UpdateMixin, UserRefMixin.Optional, TeamRefMixin.Optional
):
    __tablename__ = "provider_instance_usage"

    @declared_attr
    def provider_instance_id(cls):
        return cls.create_foreign_key(ProviderInstance, nullable=False)

    provider_instance = relationship(ProviderInstance.__name__, backref="usage")
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    __table_args__ = {
        "comment": "A ProviderInstanceUsage represents a User's usage of a provider. If team_id is also populated, it was used on behalf of a team by a user (through a team agent). Lack of a record means a user has never used the ProviderInstance. Note that ProviderInstances lower on a rotation may be seldom/never used."
    }


class ProviderInstanceSetting(Base, BaseMixin, UpdateMixin):
    __tablename__ = "provider_instance_settings"

    @declared_attr
    def provider_instance_id(cls):
        return cls.create_foreign_key(ProviderInstance, nullable=False)

    provider_instance = relationship(ProviderInstance.__name__, backref="settings")
    key = Column(Text, nullable=False)
    value = Column(Text, nullable=True)
    __table_args__ = {
        "comment": "A ProviderInstanceSetting represents a non-default configuration setting for a User or Team's instance of an Provider."
    }


class ProviderInstanceExtensionAbility(Base, BaseMixin, UpdateMixin):
    __tablename__ = "provider_instance_extension_abilities"

    @declared_attr
    def provider_instance_id(cls):
        return cls.create_foreign_key(ProviderInstance, nullable=False)

    provider_instance = relationship(
        ProviderInstance.__name__, backref="extension_abilities"
    )

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


class RotationProviderInstance(Base, BaseMixin, UpdateMixin, ParentMixin):
    __tablename__ = "rotation_provider_instances"

    @declared_attr
    def rotation_id(cls):
        return cls.create_foreign_key(Rotation, nullable=False)

    rotation = relationship(Rotation.__name__, backref="provider_instances")

    @declared_attr
    def provider_instance_id(cls):
        return cls.create_foreign_key(ProviderInstance, nullable=False)

    provider_instance = relationship(ProviderInstance.__name__, backref="rotations")
    permission_references = ["rotation"]
    __table_args__ = {
        "comment": "A RotationProviderInstance represents a link between a Rotation and a ProviderInstance. Order is determined by record parentage (NULL parent is first)."
    }
