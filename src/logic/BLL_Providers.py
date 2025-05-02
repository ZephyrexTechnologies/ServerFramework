from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.DB_Providers import (
    Provider,
    ProviderExtension,
    ProviderExtensionAbility,
    ProviderInstance,
    ProviderInstanceExtensionAbility,
    ProviderInstanceSetting,
    ProviderInstanceUsage,
    Rotation,
    RotationProviderInstance,
)
from logic.AbstractLogicManager import (
    AbstractBLLManager,
    BaseMixinModel,
    NameMixinModel,
    NumericalSearchModel,
    ParentMixinModel,
    StringSearchModel,
    UpdateMixinModel,
)
from logic.BLL_Auth import TeamModel, UserModel


class ProviderModel(BaseMixinModel, UpdateMixinModel, NameMixinModel):
    agent_settings_json: Optional[str] = None
    system: bool = False

    class ReferenceID:
        provider_id: str = Field(..., description="The ID of the related provider")

        class Optional:
            provider_id: Optional[str] = None

        class Search:
            provider_id: Optional[StringSearchModel] = None

    class Create(BaseModel):
        name: str
        agent_settings_json: Optional[str] = None
        system: bool = False

    class Update(BaseModel):
        name: Optional[str] = None
        agent_settings_json: Optional[str] = None
        system: Optional[bool] = None

    class Search(BaseMixinModel.Search, NameMixinModel.Search, UpdateMixinModel.Search):
        agent_settings_json: Optional[StringSearchModel] = None
        system: Optional[bool] = None


class ProviderReferenceModel(ProviderModel.ReferenceID):
    provider: Optional[ProviderModel] = None

    class Optional(ProviderModel.ReferenceID.Optional):
        provider: Optional[ProviderModel] = None


class ProviderNetworkModel:
    class POST(BaseModel):
        provider: ProviderModel.Create

    class PUT(BaseModel):
        provider: ProviderModel.Update

    class SEARCH(BaseModel):
        provider: ProviderModel.Search

    class ResponseSingle(BaseModel):
        provider: ProviderModel

    class ResponsePlural(BaseModel):
        providers: List[ProviderModel]


class ProviderManager(AbstractBLLManager):
    Model = ProviderModel
    ReferenceModel = ProviderReferenceModel
    NetworkModel = ProviderNetworkModel
    DBClass = Provider

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
        self._extension = None
        self._instance = None
        self._rotation = None

    @property
    def extension(self):
        if self._extension is None:
            # Import locally to avoid circular imports
            self._extension = ProviderExtensionManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._extension

    @property
    def instance(self):
        if self._instance is None:
            # Import locally to avoid circular imports
            self._instance = ProviderInstanceManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._instance

    @property
    def rotation(self):
        if self._rotation is None:
            # Import locally to avoid circular imports
            self._rotation = RotationManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._rotation

    def createValidation(self, entity):
        if hasattr(entity, "name") and entity.name and len(entity.name) < 2:
            raise HTTPException(
                status_code=400,
                detail="Provider name must be at least 2 characters long",
            )

    @staticmethod
    def list_runtime_providers():
        return ["OpenAI", "AGInYourPC"]

    @staticmethod
    def get_runtime_provider_options(provider_name):
        if provider_name == "OpenAI":
            return {"OPENAI_API_KEY": "", "OPENAI_MODEL": "gpt-4"}
        elif provider_name == "AGInYourPC":
            return {"AGINYOURPC_API_KEY": "", "AGINYOURPC_AI_MODEL": "local"}
        return {}


class ProviderExtensionModel(BaseMixinModel, UpdateMixinModel):
    provider_id: str
    extension_id: str

    class Create(BaseModel):
        provider_id: str
        extension_id: str

    class Update(BaseModel):
        provider_id: Optional[str] = None
        extension_id: Optional[str] = None

    class Search(
        BaseMixinModel.Search,
        UpdateMixinModel.Search,
    ):
        provider_id: Optional[StringSearchModel] = None
        extension_id: Optional[StringSearchModel] = None

    class ReferenceID:
        provider_extension_id: str = Field(
            ..., description="The ID of the related provider extension"
        )

        class Optional:
            provider_extension_id: Optional[str] = None

        class Search:
            provider_extension_id: Optional[StringSearchModel] = None


class ProviderExtensionReferenceModel(ProviderExtensionModel.ReferenceID):
    provider_extension: Optional[ProviderExtensionModel] = None

    class Optional(ProviderExtensionModel.ReferenceID.Optional):
        provider_extension: Optional[ProviderExtensionModel] = None


class ProviderExtensionNetworkModel:
    class POST(BaseModel):
        provider_extension: ProviderExtensionModel.Create

    class PUT(BaseModel):
        provider_extension: ProviderExtensionModel.Update

    class SEARCH(BaseModel):
        provider_extension: ProviderExtensionModel.Search

    class ResponseSingle(BaseModel):
        provider_extension: ProviderExtensionModel

    class ResponsePlural(BaseModel):
        provider_extensions: List[ProviderExtensionModel]


class ProviderExtensionManager(AbstractBLLManager):
    Model = ProviderExtensionModel
    ReferenceModel = ProviderExtensionReferenceModel
    NetworkModel = ProviderExtensionNetworkModel
    DBClass = ProviderExtension

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
        self._ability = None

    @property
    def ability(self):
        if self._ability is None:
            # Import locally to avoid circular imports
            self._ability = ProviderExtensionAbilityManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._ability


class ProviderExtensionAbilityModel(BaseMixinModel, UpdateMixinModel):
    provider_extension_id: str
    ability_id: str

    class Create(BaseModel):
        provider_extension_id: str
        ability_id: str

    class Update(BaseModel):
        provider_extension_id: Optional[str] = None
        ability_id: Optional[str] = None

    class Search(BaseMixinModel.Search, UpdateMixinModel.Search):
        provider_extension_id: Optional[StringSearchModel] = None
        ability_id: Optional[StringSearchModel] = None

    class ReferenceID:
        provider_extension_ability_id: str = Field(
            ..., description="The ID of the related provider extension ability"
        )

        class Optional:
            provider_extension_ability_id: Optional[str] = None

        class Search:
            provider_extension_ability_id: Optional[StringSearchModel] = None


class ProviderExtensionAbilityReferenceModel(ProviderExtensionAbilityModel.ReferenceID):
    provider_extension_ability: Optional[ProviderExtensionAbilityModel] = None

    class Optional(ProviderExtensionAbilityModel.ReferenceID.Optional):
        provider_extension_ability: Optional[ProviderExtensionAbilityModel] = None


class ProviderExtensionAbilityNetworkModel:
    class POST(BaseModel):
        provider_extension_ability: ProviderExtensionAbilityModel.Create

    class PUT(BaseModel):
        provider_extension_ability: ProviderExtensionAbilityModel.Update

    class SEARCH(BaseModel):
        provider_extension_ability: ProviderExtensionAbilityModel.Search

    class ResponseSingle(BaseModel):
        provider_extension_ability: ProviderExtensionAbilityModel

    class ResponsePlural(BaseModel):
        provider_extension_abilities: List[ProviderExtensionAbilityModel]


class ProviderExtensionAbilityManager(AbstractBLLManager):
    Model = ProviderExtensionAbilityModel
    ReferenceModel = ProviderExtensionAbilityReferenceModel
    NetworkModel = ProviderExtensionAbilityNetworkModel
    DBClass = ProviderExtensionAbility


class ProviderInstanceModel(
    BaseMixinModel,
    UpdateMixinModel,
    NameMixinModel,
    UserModel.ReferenceID.Optional,
    TeamModel.ReferenceID.Optional,
):
    provider_id: str
    model_name: Optional[str] = None
    api_key: Optional[str] = None

    class Create(BaseModel):
        name: str
        provider_id: str
        model_name: Optional[str] = None
        api_key: Optional[str] = None
        user_id: Optional[str] = None
        team_id: Optional[str] = None

    class Update(BaseModel):
        name: Optional[str] = None
        provider_id: Optional[str] = None
        model_name: Optional[str] = None
        api_key: Optional[str] = None
        user_id: Optional[str] = None
        team_id: Optional[str] = None

    class Search(
        BaseMixinModel.Search,
        UpdateMixinModel.Search,
        NameMixinModel.Search,
        UserModel.ReferenceID.Search,
        TeamModel.ReferenceID.Search,
    ):
        provider_id: Optional[StringSearchModel] = None
        model_name: Optional[StringSearchModel] = None
        api_key: Optional[StringSearchModel] = None

    class ReferenceID:
        provider_instance_id: str = Field(
            ..., description="The ID of the related provider instance"
        )

        class Optional:
            provider_instance_id: Optional[str] = None

        class Search:
            provider_instance_id: Optional[StringSearchModel] = None


class ProviderInstanceReferenceModel(ProviderInstanceModel.ReferenceID):
    provider_instance: Optional[ProviderInstanceModel] = None

    class Optional(ProviderInstanceModel.ReferenceID.Optional):
        provider_instance: Optional[ProviderInstanceModel] = None


class ProviderInstanceNetworkModel:
    class POST(BaseModel):
        provider_instance: ProviderInstanceModel.Create

    class PUT(BaseModel):
        provider_instance: ProviderInstanceModel.Update

    class SEARCH(BaseModel):
        provider_instance: ProviderInstanceModel.Search

    class ResponseSingle(BaseModel):
        provider_instance: ProviderInstanceModel

    class ResponsePlural(BaseModel):
        provider_instances: List[ProviderInstanceModel]


class ProviderInstanceManager(AbstractBLLManager):
    Model = ProviderInstanceModel
    ReferenceModel = ProviderInstanceReferenceModel
    NetworkModel = ProviderInstanceNetworkModel
    DBClass = ProviderInstance

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
        self._usage = None
        self._setting = None
        self._ability = None

    @property
    def usage(self):
        if self._usage is None:
            # Import locally to avoid circular imports
            self._usage = ProviderInstanceUsageManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._usage

    @property
    def setting(self):
        if self._setting is None:
            # Import locally to avoid circular imports
            self._setting = ProviderInstanceSettingManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._setting

    @property
    def ability(self):
        if self._ability is None:
            # Import locally to avoid circular imports
            self._ability = ProviderInstanceExtensionAbilityManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._ability

    def createValidation(self, entity):
        if hasattr(entity, "name") and entity.name and len(entity.name) < 2:
            raise HTTPException(
                status_code=400,
                detail="Provider instance name must be at least 2 characters long",
            )


class ProviderInstanceUsageModel(
    BaseMixinModel,
    UpdateMixinModel,
    UserModel.ReferenceID.Optional,
    TeamModel.ReferenceID.Optional,
):
    provider_instance_id: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    class Create(BaseModel):
        provider_instance_id: str
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        user_id: Optional[str] = None
        team_id: Optional[str] = None

    class Update(BaseModel):
        provider_instance_id: Optional[str] = None
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        user_id: Optional[str] = None
        team_id: Optional[str] = None

    class Search(
        BaseMixinModel.Search,
        UpdateMixinModel.Search,
        UserModel.ReferenceID.Search,
        TeamModel.ReferenceID.Search,
    ):
        provider_instance_id: Optional[StringSearchModel] = None
        input_tokens: Optional[NumericalSearchModel] = None
        output_tokens: Optional[NumericalSearchModel] = None

    class ReferenceID:
        provider_instance_usage_id: str = Field(
            ..., description="The ID of the related provider instance usage"
        )

        class Optional:
            provider_instance_usage_id: Optional[str] = None

        class Search:
            provider_instance_usage_id: Optional[StringSearchModel] = None


class ProviderInstanceUsageReferenceModel(ProviderInstanceUsageModel.ReferenceID):
    provider_instance_usage: Optional[ProviderInstanceUsageModel] = None

    class Optional(ProviderInstanceUsageModel.ReferenceID.Optional):
        provider_instance_usage: Optional[ProviderInstanceUsageModel] = None


class ProviderInstanceUsageNetworkModel:
    class POST(BaseModel):
        provider_instance_usage: ProviderInstanceUsageModel.Create

    class PUT(BaseModel):
        provider_instance_usage: ProviderInstanceUsageModel.Update

    class SEARCH(BaseModel):
        provider_instance_usage: ProviderInstanceUsageModel.Search

    class ResponseSingle(BaseModel):
        provider_instance_usage: ProviderInstanceUsageModel

    class ResponsePlural(BaseModel):
        provider_instance_usages: List[ProviderInstanceUsageModel]


class ProviderInstanceUsageManager(AbstractBLLManager):
    Model = ProviderInstanceUsageModel
    ReferenceModel = ProviderInstanceUsageReferenceModel
    NetworkModel = ProviderInstanceUsageNetworkModel
    DBClass = ProviderInstanceUsage

    def createValidation(self, entity):
        if entity.input_tokens is None and entity.output_tokens is None:
            raise HTTPException(
                status_code=400,
                detail="At least one of input_tokens or output_tokens must be provided",
            )


class ProviderInstanceSettingModel(BaseMixinModel, UpdateMixinModel):
    provider_instance_id: str
    key: str
    value: Optional[str] = None

    class Create(BaseModel):
        provider_instance_id: str
        key: str
        value: Optional[str] = None

    class Update(BaseModel):
        provider_instance_id: Optional[str] = None
        key: Optional[str] = None
        value: Optional[str] = None

    class Search(
        BaseMixinModel.Search,
        UpdateMixinModel.Search,
    ):
        provider_instance_id: Optional[StringSearchModel] = None
        key: Optional[StringSearchModel] = None
        value: Optional[StringSearchModel] = None

    class ReferenceID:
        provider_instance_setting_id: str = Field(
            ..., description="The ID of the related provider instance setting"
        )

        class Optional:
            provider_instance_setting_id: Optional[str] = None

        class Search:
            provider_instance_setting_id: Optional[StringSearchModel] = None


class ProviderInstanceSettingReferenceModel(ProviderInstanceSettingModel.ReferenceID):
    provider_instance_setting: Optional[ProviderInstanceSettingModel] = None

    class Optional(ProviderInstanceSettingModel.ReferenceID.Optional):
        provider_instance_setting: Optional[ProviderInstanceSettingModel] = None


class ProviderInstanceSettingNetworkModel:
    class POST(BaseModel):
        provider_instance_setting: ProviderInstanceSettingModel.Create

    class PUT(BaseModel):
        provider_instance_setting: ProviderInstanceSettingModel.Update

    class SEARCH(BaseModel):
        provider_instance_setting: ProviderInstanceSettingModel.Search

    class ResponseSingle(BaseModel):
        provider_instance_setting: ProviderInstanceSettingModel

    class ResponsePlural(BaseModel):
        provider_instance_settings: List[ProviderInstanceSettingModel]


class ProviderInstanceSettingManager(AbstractBLLManager):
    Model = ProviderInstanceSettingModel
    ReferenceModel = ProviderInstanceSettingReferenceModel
    NetworkModel = ProviderInstanceSettingNetworkModel
    DBClass = ProviderInstanceSetting

    def createValidation(self, entity):
        if not entity.key:
            raise HTTPException(
                status_code=400,
                detail="Setting key is required",
            )


class ProviderInstanceExtensionAbilityModel(BaseMixinModel, UpdateMixinModel):
    provider_instance_id: str
    provider_extension_ability_id: str
    state: bool = True
    forced: bool = False

    class Create(BaseModel):
        provider_instance_id: str
        provider_extension_ability_id: str
        state: bool = True
        forced: bool = False

    class Update(BaseModel):
        provider_instance_id: Optional[str] = None
        provider_extension_ability_id: Optional[str] = None
        state: Optional[bool] = None
        forced: Optional[bool] = None

    class Search(
        BaseMixinModel.Search,
        UpdateMixinModel.Search,
    ):
        provider_instance_id: Optional[StringSearchModel] = None
        provider_extension_ability_id: Optional[StringSearchModel] = None
        state: Optional[bool] = None
        forced: Optional[bool] = None


class ProviderInstanceExtensionAbilityReferenceModel(BaseMixinModel):
    provider_instance_extension_ability_id: str = Field(
        ..., description="The ID of the related provider instance extension ability"
    )
    provider_instance_extension_ability: Optional[
        ProviderInstanceExtensionAbilityModel
    ] = None

    class Optional:
        provider_instance_extension_ability_id: Optional[str] = None
        provider_instance_extension_ability: Optional[
            ProviderInstanceExtensionAbilityModel
        ] = None


class ProviderInstanceExtensionAbilityNetworkModel:
    class POST(BaseModel):
        provider_instance_extension_ability: (
            ProviderInstanceExtensionAbilityModel.Create
        )

    class PUT(BaseModel):
        provider_instance_extension_ability: (
            ProviderInstanceExtensionAbilityModel.Update
        )

    class SEARCH(BaseModel):
        provider_instance_extension_ability: (
            ProviderInstanceExtensionAbilityModel.Search
        )

    class ResponseSingle(BaseModel):
        provider_instance_extension_ability: ProviderInstanceExtensionAbilityModel

    class ResponsePlural(BaseModel):
        provider_instance_extension_abilities: List[
            ProviderInstanceExtensionAbilityModel
        ]


class ProviderInstanceExtensionAbilityManager(AbstractBLLManager):
    Model = ProviderInstanceExtensionAbilityModel
    ReferenceModel = ProviderInstanceExtensionAbilityReferenceModel
    NetworkModel = ProviderInstanceExtensionAbilityNetworkModel
    DBClass = ProviderInstanceExtensionAbility


class RotationModel(
    BaseMixinModel,
    UpdateMixinModel,
    NameMixinModel,
    UserModel.ReferenceID.Optional,
    TeamModel.ReferenceID.Optional,
):
    description: Optional[str] = None

    class Create(BaseModel):
        name: str
        description: Optional[str] = None
        user_id: Optional[str] = None
        team_id: Optional[str] = None

    class Update(BaseModel):
        name: Optional[str] = None
        description: Optional[str] = None
        user_id: Optional[str] = None
        team_id: Optional[str] = None

    class Search(
        BaseMixinModel.Search,
        UpdateMixinModel.Search,
        NameMixinModel.Search,
        UserModel.ReferenceID.Search,
        TeamModel.ReferenceID.Search,
    ):
        description: Optional[StringSearchModel] = None

    class ReferenceID:
        rotation_id: str = Field(..., description="The ID of the related rotation")

        class Optional:
            rotation_id: Optional[str] = None

        class Search:
            rotation_id: Optional[StringSearchModel] = None


class RotationReferenceModel(RotationModel.ReferenceID):
    rotation: Optional[RotationModel] = None

    class Optional(RotationModel.ReferenceID.Optional):
        rotation: Optional[RotationModel] = None


class RotationNetworkModel:
    class POST(BaseModel):
        rotation: RotationModel.Create

    class PUT(BaseModel):
        rotation: RotationModel.Update

    class SEARCH(BaseModel):
        rotation: RotationModel.Search

    class ResponseSingle(BaseModel):
        rotation: RotationModel

    class ResponsePlural(BaseModel):
        rotations: List[RotationModel]


class RotationManager(AbstractBLLManager):
    Model = RotationModel
    ReferenceModel = RotationReferenceModel
    NetworkModel = RotationNetworkModel
    DBClass = Rotation

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
        self._provider_instances = None

    @property
    def provider_instances(self):
        if self._provider_instances is None:
            # Import locally to avoid circular imports
            self._provider_instances = RotationProviderInstanceManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._provider_instances

    def createValidation(self, entity):
        if hasattr(entity, "name") and entity.name and len(entity.name) < 2:
            raise HTTPException(
                status_code=400,
                detail="Rotation name must be at least 2 characters long",
            )


class RotationProviderInstanceModel(
    BaseMixinModel,
    UpdateMixinModel,
    ParentMixinModel,
):
    rotation_id: str
    provider_instance_id: str
    permission_references: List[str] = ["rotation"]

    class Create(BaseModel):
        rotation_id: str
        provider_instance_id: str
        parent_id: Optional[str] = None

    class Update(BaseModel):
        rotation_id: Optional[str] = None
        provider_instance_id: Optional[str] = None
        parent_id: Optional[str] = None

    class Search(
        BaseMixinModel.Search,
        UpdateMixinModel.Search,
        ParentMixinModel.Search,
    ):
        rotation_id: Optional[StringSearchModel] = None
        provider_instance_id: Optional[StringSearchModel] = None


class RotationProviderInstanceReferenceModel(BaseMixinModel):
    rotation_provider_instance_id: str = Field(
        ..., description="The ID of the related rotation provider instance"
    )
    rotation_provider_instance: Optional[RotationProviderInstanceModel] = None

    class Optional:
        rotation_provider_instance_id: Optional[str] = None
        rotation_provider_instance: Optional[RotationProviderInstanceModel] = None


class RotationProviderInstanceNetworkModel:
    class POST(BaseModel):
        rotation_provider_instance: RotationProviderInstanceModel.Create

    class PUT(BaseModel):
        rotation_provider_instance: RotationProviderInstanceModel.Update

    class SEARCH(BaseModel):
        rotation_provider_instance: RotationProviderInstanceModel.Search

    class ResponseSingle(BaseModel):
        rotation_provider_instance: RotationProviderInstanceModel

    class ResponsePlural(BaseModel):
        rotation_provider_instances: List[RotationProviderInstanceModel]


class RotationProviderInstanceManager(AbstractBLLManager):
    Model = RotationProviderInstanceModel
    ReferenceModel = RotationProviderInstanceReferenceModel
    NetworkModel = RotationProviderInstanceNetworkModel
    DBClass = RotationProviderInstance

    def createValidation(self, entity):
        if (
            hasattr(entity, "parent_id")
            and entity.parent_id
            and entity.parent_id == entity.id
        ):
            raise HTTPException(
                status_code=400,
                detail="A rotation provider instance cannot be its own parent",
            )
