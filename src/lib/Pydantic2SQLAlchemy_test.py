# import unittest
# from datetime import datetime
# from typing import Optional

# from pydantic import Field
# from Pydantic2SQLAlchemy import (
#     MODEL_REGISTRY,
#     BaseMixinModel,
#     ImageMixinModel,
#     ModelConverter,
#     ParentMixinModel,
#     StringSearchModel,
#     UpdateMixinModel,
#     clear_registry_cache,
#     set_base_model,
# )
# from sqlalchemy import Column, String, create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import clear_mappers, registry, sessionmaker

# from database.Base import Base

# # Create a fresh registry and base for testing to avoid conflicts
# test_registry = registry()
# TestBase = declarative_base(cls=Base.__class__, name="TestBase", metadata=Base.metadata)

# # Set up in-memory SQLite for testing
# engine = create_engine("sqlite:///:memory:", echo=False)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# # Example model for testing foreign keys (must be defined before UserModel)
# class TeamModel(BaseMixinModel, ParentMixinModel):
#     model_config = {"extra": "ignore", "populate_by_name": True}
#     name: str = Field(description="Team name")
#     description: Optional[str] = Field(description="Team description")


# # Example model for testing
# class UserModel(BaseMixinModel, UpdateMixinModel, ImageMixinModel.Optional):
#     model_config = {"extra": "ignore", "populate_by_name": True}
#     email: Optional[str] = Field(description="User's email address")
#     username: Optional[str] = Field(description="User's username")
#     display_name: Optional[str] = Field(default=None, description="User's display name")
#     first_name: Optional[str] = Field(default="", description="User's first name")
#     last_name: Optional[str] = Field(default="", description="User's last name")
#     mfa_count: Optional[int] = Field(
#         default=1, description="Number of MFA verifications required"
#     )
#     active: Optional[bool] = Field(
#         default=True, description="Whether the user is active"
#     )

#     class ReferenceID:
#         team_id: str = Field(..., description="The ID of the related team")

#         class Optional:
#             team_id: Optional[str] = None

#         class Search:
#             team_id: Optional[StringSearchModel] = None


# class Pydantic2SQLAlchemyTest(unittest.TestCase):
#     @classmethod
#     def setUpClass(cls):
#         """Set up test environment once before all tests"""
#         # Clear SQLAlchemy mappers to start with a clean state
#         clear_mappers()

#         # Clear our model registry
#         clear_registry_cache()

#         # Set our TestBase as the base model for all tests
#         set_base_model(TestBase)

#         # Create tables
#         TestBase.metadata.create_all(bind=engine)

#     def setUp(self):
#         """Set up test environment before each test"""
#         # Clear the model registry before each test
#         MODEL_REGISTRY.clear()

#         # Create a session
#         self.db = SessionLocal()

#         # Pre-register Team model to ensure it's available for User's references
#         Team = ModelConverter.create_sqlalchemy_model(
#             TeamModel, tablename="teams", table_comment="Teams for collaboration"
#         )

#     def tearDown(self):
#         """Clean up after each test"""
#         self.db.close()

#         # Clean up the model registry
#         MODEL_REGISTRY.clear()

#     def test_model_conversion(self):
#         """Test basic conversion of Pydantic model to SQLAlchemy model"""
#         # Convert the User model
#         User = ModelConverter.create_sqlalchemy_model(
#             UserModel,
#             tablename="users",
#             table_comment="Core user accounts for authentication",
#         )

#         # Verify model attributes
#         self.assertEqual(User.__tablename__, "users")
#         self.assertEqual(
#             User.__table_args__["comment"], "Core user accounts for authentication"
#         )

#         # Verify columns
#         self.assertTrue(hasattr(User, "email"))
#         self.assertTrue(hasattr(User, "username"))
#         self.assertTrue(hasattr(User, "display_name"))
#         self.assertTrue(hasattr(User, "first_name"))
#         self.assertTrue(hasattr(User, "last_name"))
#         self.assertTrue(hasattr(User, "mfa_count"))
#         self.assertTrue(hasattr(User, "active"))

#         # Verify foreign key relationship
#         self.assertTrue(hasattr(User, "team_id"))
#         self.assertTrue(hasattr(User, "team"))

#         # Verify column attributes
#         email_col = User.__table__.columns["email"]
#         self.assertEqual(email_col.comment, "User's email address")
#         self.assertTrue(email_col.nullable)

#         mfa_col = User.__table__.columns["mfa_count"]
#         self.assertEqual(mfa_col.default.arg, 1)

#         # Create a sample user
#         user = User(
#             email="test@example.com", username="testuser", display_name="Test User"
#         )

#         # Check attribute access
#         self.assertEqual(user.email, "test@example.com")
#         self.assertEqual(user.username, "testuser")
#         self.assertEqual(user.display_name, "Test User")

#     def test_reference_handling(self):
#         """Test handling of reference IDs and relationships"""
#         # Convert User model (Team is already created in setUp)
#         User = ModelConverter.create_sqlalchemy_model(
#             UserModel, tablename="users", table_comment="User accounts"
#         )

#         # Verify team reference
#         self.assertTrue(hasattr(User, "team_id"))
#         self.assertTrue(hasattr(User, "team"))

#         # Verify Team is in the registry
#         self.assertIn("Team", MODEL_REGISTRY)

#         # Create a team and user in database
#         Team = MODEL_REGISTRY["Team"]
#         team = Team(name="Test Team", description="A test team")
#         self.db.add(team)
#         self.db.flush()

#         user = User(email="team@example.com", username="teamuser", team_id=team.id)
#         self.db.add(user)
#         self.db.commit()

#         # Query and check relationships
#         retrieved_user = (
#             self.db.query(User).filter(User.email == "team@example.com").first()
#         )
#         self.assertEqual(retrieved_user.team_id, team.id)

#     def test_reference_mixin_creation(self):
#         """Test creation of reference mixins"""
#         # Team model is already created in setUp
#         Team = MODEL_REGISTRY["Team"]

#         # Verify team is registered
#         self.assertIn("Team", MODEL_REGISTRY)

#         # Create a reference mixin
#         TeamRefMixin = ModelConverter.create_reference_mixin("Team", Team)

#         # Test the mixin
#         self.assertTrue(hasattr(TeamRefMixin, "team_id"))
#         self.assertTrue(hasattr(TeamRefMixin, "team"))

#         # Test the Optional inner class
#         self.assertTrue(hasattr(TeamRefMixin, "Optional"))

#         # Create a model using the mixin
#         class Project(TestBase, TeamRefMixin):
#             __tablename__ = "projects"
#             id = Column(String, primary_key=True)
#             name = Column(String, nullable=False)

#         # Verify the attributes
#         self.assertTrue(hasattr(Project, "team_id"))
#         self.assertTrue(hasattr(Project, "team"))

#         # Test Optional mixin
#         class OptionalTeamProject(TestBase, TeamRefMixin.Optional):
#             __tablename__ = "optional_team_projects"
#             id = Column(String, primary_key=True)
#             name = Column(String, nullable=False)

#         # Verify the attributes
#         self.assertTrue(hasattr(OptionalTeamProject, "team_id"))
#         self.assertTrue(hasattr(OptionalTeamProject, "team"))

#     def test_conversion_between_models(self):
#         """Test conversion between Pydantic and SQLAlchemy instances"""
#         # We already have Team registered in setUp

#         # Create User model
#         User = ModelConverter.create_sqlalchemy_model(UserModel)

#         # Create a SQLAlchemy instance
#         sa_user = User(
#             id="12345",
#             email="convert@example.com",
#             username="convertuser",
#             display_name="Test Display",
#             created_at=datetime.now(),
#         )

#         # Convert to Pydantic
#         pydantic_user = ModelConverter.sqlalchemy_to_pydantic(sa_user, UserModel)

#         # Verify conversion
#         self.assertEqual(pydantic_user.id, "12345")
#         self.assertEqual(pydantic_user.email, "convert@example.com")
#         self.assertEqual(pydantic_user.username, "convertuser")
#         self.assertEqual(pydantic_user.display_name, "Test Display")

#         # Modify Pydantic model
#         pydantic_user.display_name = "Converted User"

#         # Convert back to dict for SQLAlchemy
#         user_dict = ModelConverter.pydantic_to_dict(pydantic_user)

#         # Verify dict
#         self.assertEqual(user_dict["display_name"], "Converted User")
#         self.assertEqual(user_dict["email"], "convert@example.com")


# if __name__ == "__main__":
#     unittest.main()
