from typing import Any, List, Optional

from pydantic import BaseModel, Field

from database.DB_Extensions import Ability, Extension
from logic.AbstractLogicManager import (
    AbstractBLLManager,
    BaseMixinModel,
    NameMixinModel,
    StringSearchModel,
    UpdateMixinModel,
)


class ExtensionModel(BaseMixinModel, NameMixinModel, UpdateMixinModel):
    description: Optional[str] = Field(None, description="Description of the extension")

    class ReferenceID:
        extension_id: str = Field(..., description="Foreign key to Extension")

        class Optional:
            extension_id: Optional[str] = None

        class Search:
            extension_id: Optional[StringSearchModel] = None

    class Create(BaseModel, NameMixinModel):
        description: Optional[str] = Field(
            None, description="Description of the extension"
        )

    class Update(BaseModel, NameMixinModel.Optional):
        description: Optional[str] = Field(
            None, description="Description of the extension"
        )

    class Search(BaseMixinModel.Search, NameMixinModel.Search):
        description: Optional[StringSearchModel] = None


class ExtensionReferenceModel(ExtensionModel.ReferenceID):
    extension: Optional[ExtensionModel] = None

    class Optional(ExtensionModel.ReferenceID.Optional):
        extension: Optional[ExtensionModel] = None


class ExtensionNetworkModel:
    class POST(BaseModel):
        extension: ExtensionModel.Create

    class PUT(BaseModel):
        extension: ExtensionModel.Update

    class SEARCH(BaseModel):
        extension: ExtensionModel.Search

    class ResponseSingle(BaseModel):
        extension: ExtensionModel

    class ResponsePlural(BaseModel):
        extensions: List[ExtensionModel]


class ExtensionManager(AbstractBLLManager):
    Model = ExtensionModel
    ReferenceModel = ExtensionReferenceModel
    NetworkModel = ExtensionNetworkModel
    DBClass = Extension

    def __init__(self, **kwargs: Any) -> None:
        # Accept all parameters as kwargs to change signature
        requester_id = kwargs.get("requester_id")
        target_user_id = kwargs.get("target_user_id")
        target_team_id = kwargs.get("target_team_id")
        db = kwargs.get("db")

        # Initialize parent with the extracted parameters
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
        # Initialize ability manager to None
        self._abilities = None

    @property
    def abilities(self):
        if self._abilities is None:
            self._abilities = AbilityManager(
                requester_id=self.requester.id,
                target_user_id=self.target_user_id,
                target_team_id=self.target_team_id,
                db=self.db,
            )
        return self._abilities

    @staticmethod
    def list_runtime_extensions() -> List[str]:
        import glob
        import logging
        import os

        from lib.Environment import env

        # Get extensions from APP_EXTENSIONS environment variable
        app_extensions = env("APP_EXTENSIONS")
        if app_extensions:
            extension_list = [
                ext.strip() for ext in app_extensions.split(",") if ext.strip()
            ]
            if extension_list:
                logging.info(f"Using extensions from APP_EXTENSIONS: {extension_list}")
                return extension_list

        # Fallback to finding EXT_*.py files
        try:
            # Get the current directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(current_dir)  # parent of logic dir
            extensions_dir = os.path.join(src_dir, "extensions")

            logging.info(f"Looking for extensions in: {extensions_dir}")

            extensions = []
            # Look for EXT_*.py files in the extensions directory
            for ext_path in glob.glob(
                os.path.join(extensions_dir, "**", "EXT_*.py"), recursive=True
            ):
                ext_name = os.path.splitext(os.path.basename(ext_path))[0]
                if ext_name.startswith("EXT_"):
                    ext_name = ext_name[4:]
                logging.info(f"Found extension: {ext_name}")
                extensions.append(ext_name)

            return extensions
        except Exception as e:
            logging.error(f"Error finding extensions: {str(e)}")
            return []


class AbilityModel(
    BaseMixinModel, NameMixinModel, UpdateMixinModel, ExtensionReferenceModel
):
    class ReferenceID:
        ability_id: str = Field(..., description="Foreign key to Ability")

        class Optional:
            ability_id: Optional[str] = None

        class Search:
            ability_id: Optional[StringSearchModel] = None

    class Create(BaseModel, NameMixinModel, ExtensionModel.ReferenceID):
        pass

    class Update(
        BaseModel, NameMixinModel.Optional, ExtensionModel.ReferenceID.Optional
    ):
        pass

    class Search(
        BaseMixinModel.Search, NameMixinModel.Search, ExtensionModel.ReferenceID.Search
    ):
        pass


class AbilityReferenceModel(AbilityModel.ReferenceID):
    ability: Optional[AbilityModel] = None

    class Optional(AbilityModel.ReferenceID.Optional):
        ability: Optional[AbilityModel] = None


class AbilityNetworkModel:
    class POST(BaseModel):
        ability: AbilityModel.Create

    class PUT(BaseModel):
        ability: AbilityModel.Update

    class SEARCH(BaseModel):
        ability: AbilityModel.Search

    class ResponseSingle(BaseModel):
        ability: AbilityModel

    class ResponsePlural(BaseModel):
        abilities: List[AbilityModel]


class AbilityManager(AbstractBLLManager):
    Model = AbilityModel
    ReferenceModel = AbilityReferenceModel
    NetworkModel = AbilityNetworkModel
    DBClass = Ability

    def __init__(self, **kwargs: Any) -> None:
        # Extract parameters from kwargs
        requester_id = kwargs.get("requester_id")
        target_user_id = kwargs.get("target_user_id")
        target_team_id = kwargs.get("target_team_id")
        db = kwargs.get("db")

        # Call parent constructor
        super().__init__(
            requester_id=requester_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            db=db,
        )
