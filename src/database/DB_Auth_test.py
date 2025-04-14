# import pytest
# from sdk.conftest import generate_test_email
# from sqlalchemy.orm import Session

# from database.DB_Auth import *


# @pytest.mark.db
# class TestUserAuth:

#     def test_create_user(self, db_session: Session):
#         """Test creating a new user"""
#         user = User.create(
#             email=generate_test_email(), db=db_session, requester_id="test_id"
#         )
#         assert user is not None

#     def test_user_exists(self, db_session: Session):
#         """Test checking if a user exists"""
#         user_email = generate_test_email()
#         user = User.create(email=user_email, db=db_session, requester_id="test_id")
#         user = User.exists(requester_id="test_requester_id", email=user_email)
#         assert user is True

#     def test_get_user_via_email(self, db_session: Session):
#         """Test getting a user by email"""
#         user_email = generate_test_email()
#         User.create(email=user_email, db=db_session, requester_id="test_id")
#         user = User.get(requester_id="test_id", email=user_email)
#         assert user is not None
#         assert user["email"] == user_email

#     def test_get_user_via_id(self, db_session: Session):
#         user_email = generate_test_email()
#         user_id = User.create(email=user_email, db=db_session, requester_id="test_id")[
#             "id"
#         ]
#         user = User.get(requester_id="test_id", id=user_id)
#         assert user is not None
#         assert user["id"] == user_id

#     def test_update_user(self, db_session: Session):
#         user_email = generate_test_email()
#         User.create(
#             email=user_email, db=db_session, requester_id="test_id", first_name="Bob"
#         )
#         user = User.get(requester_id="test_id", email=user_email)
#         assert user["first_name"] == "Bob"
#         User.update(
#             requester_id="test_id",
#             email=user_email,
#             new_properties={"first_name": "Jeff"},
#         )
#         user = User.get(requester_id="test_id", email=user_email)
#         assert user["first_name"] == "Jeff"

#     def test_delete_user(self, db_session: Session):
#         user_email = generate_test_email()
#         user_creation = User.create(
#             email=user_email, db=db_session, requester_id="deletion_requester_id"
#         )
#         user = User.get(requester_id="deletion_testing", email=user_email)
#         User.delete(requester_id="deletion_requester_id", id=user["id"])
#         user = User.get(requester_id="deletion_testing", email=user_email)
#         assert user["deleted_at"] is not None


# @pytest.mark.db
# class TestTeamAuth:
#     def test_create_team(self, db_session: Session):
#         team = Team.create(
#             requester_id,
#             db=db_session,
#             name="Test Team",
#         )
#         assert team is not None

#     def test_team_exists(self, db_session: Session):
#         company_name = "Test Team"
#         team = Team.create(
#             db_session,
#             name=company_name,
#         )
#         company_exists = Team.exists(requester_id="test_id", id=team.id)
#         assert company_exists is True

#     def test_get_team(self, db_session: Session):
#         company_name = "Test Team"
#         new_company = Team.create(
#             db_session,
#             name=company_name,
#         )
#         get_company = Team.get(requester_id="test_id", id=new_company.id)
#         assert get_company.id == new_company.id

#     def test_update_team(self, db_session: Session):
#         company_name = "Test Team"
#         team = Team.create(
#             db_session,
#             name=company_name,
#         )
#         team_id = team.id
#         Team.update(
#             requester_id="test_id",
#             id=team_id,
#             new_properties={"name": "Updated Team Name"},
#         )
#         updated_company = Team.get(requester_id="test_id", id=team_id)
#         assert updated_company.name == "Updated Team Name"

#     def test_delete_team(self, db_session: Session):
#         company_name = "Test Team"
#         team = Team.create(
#             db_session,
#             name=company_name,
#         )
#         team_id = team.id
#         Team.delete(requester_id="test_id", id=team_id)
#         team = Team.get(requester_id="test_id", id=team_id)
#         assert team["deleted_at"] is not None
