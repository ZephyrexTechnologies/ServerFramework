import inspect
import logging

from database.Base import Base, get_session
from lib.Environment import env

logging.basicConfig(
    level=env("LOG_LEVEL"),
    format=env("LOG_FORMAT"),
)


def seed():
    """
    Generic seeding function that populates the database based on seed_list attributes.
    """
    logging.info(f"Seeding {env('DATABASE_NAME')}.db...")

    session = get_session()
    try:
        # Get all model classes with critical ones first
        models_to_seed = get_all_models()
        logging.info(f"Found {len(models_to_seed)} model classes to check for seeding")

        # Process each model class
        for model_class in models_to_seed:
            seed_model(model_class, session)

        session.commit()
        logging.info("Database seeding completed successfully.")
    except Exception as e:
        session.rollback()
        logging.error(f"Error during database seeding: {str(e)}")
        raise
    finally:
        session.close()


def get_all_models():
    """
    Dynamically find all SQLAlchemy model classes that inherit from Base.
    Ensures critical models (Team, User, UserTeam) are processed first.
    """
    from database.DB_Auth import Team, User, UserTeam

    # Priority models that must be processed first
    priority_models = [Team, User, UserTeam]

    # Get all SQLAlchemy models that inherit from Base
    models = []
    for subclass in Base.__subclasses__():
        if subclass not in priority_models:
            models.append(subclass)
        # Also include further subclasses
        for sub_subclass in subclass.__subclasses__():
            if sub_subclass not in models and sub_subclass not in priority_models:
                models.append(sub_subclass)

    # Return priority models first, then the rest sorted by table name
    return priority_models + sorted(
        models, key=lambda m: getattr(m, "__tablename__", "")
    )


def seed_model(model_class, session):
    """Helper function to seed a specific model class."""
    class_name = model_class.__name__

    # Check if class has seed_list attribute
    if not hasattr(model_class, "seed_list"):
        return

    # Handle seed_list that is a callable
    seed_list = model_class.seed_list
    if callable(seed_list) and not inspect.isclass(seed_list):
        try:
            seed_list = seed_list()
        except Exception as e:
            logging.error(
                f"Error calling seed_list function for {class_name}: {str(e)}"
            )
            return

    if not seed_list:
        return

    logging.info(f"Seeding {class_name} table...")

    # Process each seed item
    for item in seed_list:
        # Check if the item already exists
        exists = False
        try:
            if hasattr(model_class, "exists"):
                # Determine the field to check for existence
                check_field = next(
                    (k for k in ["name", "id", "email"] if k in item), None
                )
                if check_field:
                    exists = model_class.exists(
                        env("SYSTEM_ID"), db=session, **{check_field: item[check_field]}
                    )
            elif hasattr(model_class, "get"):
                # Alternative existence check if 'exists' is not available
                check_field = next(
                    (k for k in ["name", "id", "email"] if k in item), None
                )
                if check_field:
                    result = model_class.get(
                        env("SYSTEM_ID"), db=session, **{check_field: item[check_field]}
                    )
                    exists = result is not None
            else:
                # Fallback to a direct query
                check_field = next(
                    (k for k in ["name", "id", "email"] if k in item), None
                )
                if check_field:
                    field_value = item[check_field]
                    query = session.query(model_class).filter(
                        getattr(model_class, check_field) == field_value
                    )
                    exists = query.first() is not None
        except Exception as e:
            logging.error(f"Error checking existence for {class_name}: {str(e)}")
            continue

        if not exists:
            try:
                # Create the item
                if hasattr(model_class, "create"):
                    model_class.create(
                        env("SYSTEM_ID"), db=session, return_type="db", **item
                    )
                    logging.info(
                        f"Created {class_name} item: {item.get('name', str(item))}"
                    )
                else:
                    # Fallback to direct SQLAlchemy creation
                    new_instance = model_class(**item)
                    session.add(new_instance)
                    session.flush()
                    logging.info(
                        f"Created {class_name} item: {item.get('name', str(item))}"
                    )
            except Exception as e:
                logging.error(f"Error creating {class_name} item: {str(e)}")
                continue
