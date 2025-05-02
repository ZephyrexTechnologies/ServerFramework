from unittest.mock import MagicMock, call, patch

import pytest
from StaticSeedManager import get_all_models, seed, seed_model

from database.Base import Base


# Mock classes for testing
class MockBase:
    __subclasses__ = MagicMock()


# Mock precedence models
class MockTeam:
    __tablename__ = "team"
    seed_list = [{"id": "team1", "name": "Team 1"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockUser:
    __tablename__ = "user"
    seed_list = [{"id": "user1", "name": "User 1", "email": "user1@example.com"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockUserTeam:
    __tablename__ = "user_team"
    seed_list = [{"id": "userteam1", "user_id": "user1", "team_id": "team1"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockExtension:
    __tablename__ = "extension"
    seed_list = [{"id": "ext1", "name": "Extension 1"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockProvider:
    __tablename__ = "provider"
    seed_list = [{"id": "provider1", "name": "Provider 1"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockProviderInstance:
    __tablename__ = "provider_instance"
    __name__ = "ProviderInstance"
    seed_list = [
        {"id": "instance1", "_provider_name": "Provider 1", "name": "Instance 1"}
    ]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockProviderExtension:
    __tablename__ = "provider_extension"
    seed_list = [{"id": "provext1", "name": "Provider Extension 1"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModel1:
    __tablename__ = "model1"
    seed_list = [{"id": "model1_1", "name": "Model 1"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModel2:
    __tablename__ = "model2"
    # No seed_list attribute


class MockModel3:
    __tablename__ = "model3"
    seed_list = []  # Empty seed list


class MockModel4:
    __tablename__ = "model4"

    @classmethod
    def seed_list(cls):
        return [{"id": "model4_1", "name": "Model 4"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModel5:
    __tablename__ = "model5"
    seed_list = [{"id": "model5_1", "name": "Model 5"}]

    # No exists method

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModel6:
    __tablename__ = "model6"
    seed_list = [{"name": "Model 6"}]  # No ID

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModel7:
    __tablename__ = "model7"
    seed_list = [{"id": "model7_1", "name": "Model 7"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        # This one already exists
        return True

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModel8:
    __tablename__ = "model8"
    seed_list = [{"id": "model8_1", "name": "Model 8"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        raise Exception("Error in exists")

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModel9:
    __tablename__ = "model9"
    seed_list = [{"id": "model9_1", "name": "Model 9"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        raise Exception("Error in create")


# Add a tracking variable
mock_instantiation_tracker = {"count": 0}


class MockModelNoCreateMethod:
    __tablename__ = "model_no_create"
    seed_list = [{"id": "model_no_create_1", "name": "Model No Create"}]

    def __init__(self, **kwargs):
        # Track instantiation
        mock_instantiation_tracker["count"] += 1
        print(f"MockModelNoCreateMethod instantiated with: {kwargs}")

        # Store all kwargs as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False


class MockModelCallableRaisingException:
    __tablename__ = "model_callable_exception"

    @classmethod
    def seed_list(cls):
        raise Exception("Error in seed_list")

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModelWithGetSeedList:
    __tablename__ = "model_with_get_seed_list"

    @classmethod
    def get_seed_list(cls):
        return [{"id": "dynamic_seed_1", "name": "Dynamic Seed Item"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModelWithGetSeedListError:
    __tablename__ = "model_get_seed_list_error"

    @classmethod
    def get_seed_list(cls):
        raise Exception("Error in get_seed_list")

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


class MockModelWithSeedId:
    __tablename__ = "model_with_seed_id"
    seed_id = "CUSTOM_SEED_ID"
    seed_list = [{"id": "custom_seed_1", "name": "Custom Seed ID Item"}]

    @classmethod
    def exists(cls, requester_id, db, **kwargs):
        return False

    @classmethod
    def create(cls, requester_id, db, return_type, **kwargs):
        return MagicMock()


@pytest.fixture
def mock_session():
    session = MagicMock()

    # Create a better tracking mechanism for add method
    def tracked_add(obj):
        print(f"session.add called with: {obj.__class__.__name__}")
        session._added_objects = getattr(session, "_added_objects", []) + [obj]

    session.add = MagicMock(side_effect=tracked_add)
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()

    def tracked_flush():
        print("session.flush called")

    session.flush = MagicMock(side_effect=tracked_flush)
    return session


@pytest.fixture
def mock_env():
    return {
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "%(levelname)s: %(message)s",
        "DATABASE_NAME": "test_db",
        "ROOT_ID": "root_id",
        "SYSTEM_ID": "system_id",
        "CUSTOM_SEED_ID": "custom_seed_id",
    }


class TestGetAllModels:
    @patch("database.DB_Auth.Team", MockTeam)
    @patch("database.DB_Auth.User", MockUser)
    @patch("database.DB_Auth.UserTeam", MockUserTeam)
    @patch("database.DB_Extensions.Extension", MockExtension)
    @patch("database.DB_Providers.Provider", MockProvider)
    @patch("database.DB_Providers.ProviderInstance", MockProviderInstance)
    @patch("database.DB_Providers.ProviderExtension", MockProviderExtension)
    @patch.object(Base, "__subclasses__")
    def test_get_all_models_order(self, mock_subclasses):
        # Setup
        mock_subclasses.return_value = [MockModel1, MockModel2]
        MockModel1.__subclasses__ = MagicMock(return_value=[])
        MockModel2.__subclasses__ = MagicMock(return_value=[])

        # Execute
        models = get_all_models()

        # Verify
        assert len(models) >= 9  # 7 precedence models + 2 additional models
        assert models[0] == MockTeam
        assert models[1] == MockUser
        assert models[2] == MockUserTeam
        assert models[3] == MockExtension
        assert models[4] == MockProvider
        assert models[5] == MockProviderInstance
        assert models[6] == MockProviderExtension
        assert MockModel1 in models
        assert MockModel2 in models

    @patch("database.DB_Auth.Team", MockTeam)
    @patch("database.DB_Auth.User", MockUser)
    @patch("database.DB_Auth.UserTeam", MockUserTeam)
    @patch("database.DB_Extensions.Extension", MockExtension)
    @patch("database.DB_Providers.Provider", MockProvider)
    @patch("database.DB_Providers.ProviderInstance", MockProviderInstance)
    @patch("database.DB_Providers.ProviderExtension", MockProviderExtension)
    @patch.object(Base, "__subclasses__")
    def test_get_all_models_with_subclasses(self, mock_subclasses):
        # Setup
        mock_subclasses.return_value = [MockModel1]
        MockModel1.__subclasses__ = MagicMock(return_value=[MockModel2])

        # Execute
        models = get_all_models()

        # Verify
        assert len(models) == 9  # 7 precedence models + 1 model + 1 submodel
        assert models[0] == MockTeam
        assert models[1] == MockUser
        assert models[2] == MockUserTeam
        assert MockModel1 in models
        assert MockModel2 in models

    @patch("database.DB_Auth.Team", MockTeam)
    @patch("database.DB_Auth.User", MockUser)
    @patch("database.DB_Auth.UserTeam", MockUserTeam)
    @patch("database.DB_Extensions.Extension", MockExtension)
    @patch("database.DB_Providers.Provider", MockProvider)
    @patch("database.DB_Providers.ProviderInstance", MockProviderInstance)
    @patch("database.DB_Providers.ProviderExtension", MockProviderExtension)
    @patch.object(Base, "__subclasses__")
    def test_get_all_models_sorting(self, mock_subclasses):
        # Setup - intentionally unsorted
        mock_subclasses.return_value = [MockModel2, MockModel1]
        MockModel1.__subclasses__ = MagicMock(return_value=[])
        MockModel2.__subclasses__ = MagicMock(return_value=[])

        # Execute
        models = get_all_models()

        # Verify sorted order (after precedence models)
        assert models[7:] == [MockModel1, MockModel2]  # Sorted by tablename


class TestSeedModel:
    @patch("logging.info")
    @patch("logging.error")
    @patch("logging.warning")
    @patch("StaticSeedManager.env")
    def test_seed_model_no_seed_list(
        self, mock_env, mock_warning, mock_error, mock_info, mock_session
    ):
        # Test with a model that has no seed_list attribute
        seed_model(MockModel2, mock_session)

        # The implementation logs for all models, even without seed_list
        mock_info.assert_any_call("Processing seeding for MockModel2...")
        mock_error.assert_not_called()
        mock_warning.assert_not_called()

    @patch("logging.info")
    @patch("StaticSeedManager.env")
    def test_seed_model_empty_seed_list(self, mock_env, mock_info, mock_session):
        # Test with a model that has an empty seed_list
        seed_model(MockModel3, mock_session)

        # No creation should occur, but processing is logged
        mock_session.add.assert_not_called()
        mock_info.assert_any_call("Processing seeding for MockModel3...")
        mock_info.assert_any_call("No seed items for MockModel3")

    @patch("logging.info")
    @patch("StaticSeedManager.env")
    def test_seed_model_callable_seed_list(self, mock_env, mock_info, mock_session):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Test with a model that has a callable seed_list
        seed_model(MockModel4, mock_session)

        # Verify exact messages from the implementation
        mock_info.assert_any_call("Processing seeding for MockModel4...")
        mock_info.assert_any_call(
            "Called seed_list function for MockModel4, got 1 items"
        )
        mock_info.assert_any_call("Seeding MockModel4 table with 1 items...")
        mock_info.assert_any_call("Created MockModel4 item: Model 4")
        mock_info.assert_any_call("Created 1 items for MockModel4")

    @patch("logging.info")
    @patch("logging.warning")
    @patch("StaticSeedManager.env")
    def test_seed_model_no_exists_method(
        self, mock_env, mock_warning, mock_info, mock_session
    ):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Test with a model that has no exists method
        seed_model(MockModel5, mock_session)

        # Should warn about missing exists method
        mock_warning.assert_called_with(
            "Model MockModel5 does not have an 'exists' method. Skipping existence check."
        )
        mock_info.assert_any_call("Created MockModel5 item: Model 5")

    @patch("logging.info")
    @patch("StaticSeedManager.env")
    def test_seed_model_no_id_field(self, mock_env, mock_info, mock_session):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Test with a model that has no id field in seed data
        seed_model(MockModel6, mock_session)

        # Should check existence by name
        mock_info.assert_any_call("Created MockModel6 item: Model 6")

    @patch("logging.info")
    @patch("StaticSeedManager.env")
    def test_seed_model_existing_item(self, mock_env, mock_info, mock_session):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Test with a model where the item already exists
        seed_model(MockModel7, mock_session)

        # Should not create
        assert not any(
            "Created MockModel7" in str(call) for call in mock_info.call_args_list
        )
        mock_info.assert_any_call("Created 0 items for MockModel7")

    @patch("logging.info")
    @patch("logging.error")
    @patch("StaticSeedManager.env")
    def test_seed_model_exists_exception(
        self, mock_env, mock_error, mock_info, mock_session
    ):
        # Setup env mock
        mock_env.side_effect = lambda key: (
            "root_id" if key == "ROOT_ID" else "system_id"
        )

        # Test with a model where exists throws an exception
        seed_model(MockModel8, mock_session)

        # Should log error
        mock_error.assert_called_with(
            "Error checking existence for MockModel8 with id=model8_1: Error in exists"
        )

    @patch("logging.info")
    @patch("logging.error")
    @patch("StaticSeedManager.env")
    def test_seed_model_create_exception(
        self, mock_env, mock_error, mock_info, mock_session
    ):
        # Setup env mock
        mock_env.side_effect = lambda key: (
            "root_id" if key == "ROOT_ID" else "system_id"
        )

        # Test with a model where create throws an exception
        seed_model(MockModel9, mock_session)

        # Should log error
        mock_error.assert_called_with("Error creating MockModel9 item: Error in create")

    @patch("logging.info")
    @patch("logging.error")
    @patch("logging.warning")
    @patch("StaticSeedManager.env")
    def test_seed_model_no_create_method(
        self, mock_env, mock_warning, mock_error, mock_info, mock_session
    ):
        # Reset tracker
        mock_instantiation_tracker["count"] = 0

        # Setup env mock to return appropriate values
        mock_env.side_effect = lambda key: (
            "root_id" if key == "ROOT_ID" else "system_id"
        )

        # Print current state for debugging
        print(f"\nDebugging info:")
        print(
            f"MockModelNoCreateMethod.exists: {hasattr(MockModelNoCreateMethod, 'exists')}"
        )
        print(
            f"MockModelNoCreateMethod.create: {hasattr(MockModelNoCreateMethod, 'create')}"
        )
        print(f"MockModelNoCreateMethod.seed_list: {MockModelNoCreateMethod.seed_list}")

        # Test with a model that has no create method
        seed_model(MockModelNoCreateMethod, mock_session)

        # Verify that the model was instantiated
        print(f"Model instantiated {mock_instantiation_tracker['count']} times")
        assert (
            mock_instantiation_tracker["count"] > 0
        ), "MockModelNoCreateMethod was not instantiated"

        # Verify expected behavior - either add is called or we get an error that explains why not
        if mock_session.add.call_count == 0:
            print("Warning: session.add was not called as expected!")
            print(f"mock_info calls: {mock_info.call_args_list}")
            print(f"mock_error calls: {mock_error.call_args_list}")
            print(f"mock_warning calls: {mock_warning.call_args_list}")

        # Check if instance was created but add wasn't called
        if mock_instantiation_tracker["count"] > 0 and mock_session.add.call_count == 0:
            pytest.fail(
                "MockModelNoCreateMethod was instantiated but session.add was not called"
            )

        # Should see log message, even if add wasn't called
        mock_info.assert_any_call(
            "Created MockModelNoCreateMethod item: Model No Create"
        )

    @patch("logging.info")
    @patch("logging.error")
    @patch("StaticSeedManager.env")
    def test_seed_model_callable_exception(
        self, mock_env, mock_error, mock_info, mock_session
    ):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Test with a model where seed_list callable throws an exception
        seed_model(MockModelCallableRaisingException, mock_session)

        # Should log error
        mock_error.assert_called_with(
            "Error calling seed_list function for MockModelCallableRaisingException: Error in seed_list"
        )

    @patch("logging.info")
    @patch("StaticSeedManager.env")
    def test_seed_model_with_get_seed_list(self, mock_env, mock_info, mock_session):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Test with a model that has get_seed_list method
        seed_model(MockModelWithGetSeedList, mock_session)

        # Verify the get_seed_list method was used
        mock_info.assert_any_call("Processing seeding for MockModelWithGetSeedList...")
        mock_info.assert_any_call(
            "Retrieved dynamic seed list with 1 items for MockModelWithGetSeedList"
        )
        mock_info.assert_any_call(
            "Created MockModelWithGetSeedList item: Dynamic Seed Item"
        )

    @patch("logging.info")
    @patch("logging.error")
    @patch("StaticSeedManager.env")
    def test_seed_model_with_get_seed_list_error(
        self, mock_env, mock_error, mock_info, mock_session
    ):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Test with a model where get_seed_list throws an exception
        seed_model(MockModelWithGetSeedListError, mock_session)

        # Verify error handling
        mock_error.assert_called_with(
            "Error calling get_seed_list method for MockModelWithGetSeedListError: Error in get_seed_list"
        )

    @patch("logging.info")
    @patch("StaticSeedManager.env")
    def test_seed_model_with_seed_id(self, mock_env, mock_info, mock_session):
        # Setup env mock to return custom seed ID
        mock_env.side_effect = lambda key: {
            "ROOT_ID": "root_id",
            "SYSTEM_ID": "system_id",
            "CUSTOM_SEED_ID": "custom_seed_id",
        }.get(key, "")

        # Test with a model that has a custom seed_id
        seed_model(MockModelWithSeedId, mock_session)

        # Verify the custom seed_id was used
        mock_info.assert_any_call(
            "Using CUSTOM_SEED_ID (custom_seed_id) as creator for MockModelWithSeedId"
        )
        mock_info.assert_any_call(
            "Created MockModelWithSeedId item: Custom Seed ID Item"
        )

    @patch("logging.info")
    @patch("StaticSeedManager.env")
    @patch("StaticSeedManager.get_provider_by_name")
    def test_seed_model_provider_instance_special_handling(
        self, mock_get_provider, mock_env, mock_info, mock_session
    ):
        # Setup env mock
        mock_env.return_value = "system_id"

        # Setup provider mock
        provider_mock = MagicMock()
        provider_mock.id = "provider1_id"
        mock_get_provider.return_value = provider_mock

        # Test with MockProviderInstance
        seed_model(MockProviderInstance, mock_session)

        # Verify the provider lookup was called
        mock_get_provider.assert_called_once_with(mock_session, "Provider 1")

        # Verify the expected logs were generated
        mock_info.assert_any_call("Created ProviderInstance item: Instance 1")


class TestSeed:
    @patch("StaticSeedManager.get_all_models")
    @patch("StaticSeedManager.get_session")
    @patch("StaticSeedManager.seed_model")
    @patch("StaticSeedManager.env")
    @patch("logging.info")
    def test_seed_normal_flow(
        self,
        mock_log_info,
        mock_env,
        mock_seed_model,
        mock_get_session,
        mock_get_all_models,
        mock_session,
    ):
        # Setup
        mock_env.side_effect = lambda key: {
            "DATABASE_NAME": "test_db",
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "%(levelname)s: %(message)s",
            "ROOT_ID": "root_id",
            "SYSTEM_ID": "system_id",
        }.get(key, "")
        mock_get_session.return_value = mock_session
        mock_get_all_models.return_value = [MockModel1, MockModel4]

        # Execute
        seed()

        # Verify
        mock_get_all_models.assert_called_once()
        assert mock_seed_model.call_count == 2
        mock_seed_model.assert_has_calls(
            [call(MockModel1, mock_session), call(MockModel4, mock_session)]
        )
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_log_info.assert_any_call("Seeding test_db.db...")
        mock_log_info.assert_any_call("Found 2 model classes to check for seeding")
        mock_log_info.assert_any_call("Database seeding completed successfully.")

    @patch("StaticSeedManager.get_all_models")
    @patch("StaticSeedManager.get_session")
    @patch("StaticSeedManager.env")
    @patch("logging.info")
    @patch("logging.error")
    def test_seed_exception_handling(
        self,
        mock_log_error,
        mock_log_info,
        mock_env,
        mock_get_session,
        mock_get_all_models,
        mock_session,
    ):
        # Setup
        mock_env.side_effect = lambda key: {
            "DATABASE_NAME": "test_db",
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "%(levelname)s: %(message)s",
            "ROOT_ID": "root_id",
            "SYSTEM_ID": "system_id",
        }.get(key, "")
        mock_get_session.return_value = mock_session
        mock_get_all_models.side_effect = Exception("Test exception")

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Test exception"):
            seed()

        # Verify session management
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_log_error.assert_called_with(
            "Error during database seeding: Test exception"
        )


if __name__ == "__main__":
    pytest.main(["-xvs", "StaticSeedManager_test.py"])
