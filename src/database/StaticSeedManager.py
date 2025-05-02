import inspect
import logging

from sqlalchemy import select

from database.Base import Base, get_session
from database.DB_Providers import Provider
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
    Uses a single ordered precedence list to ensure proper dependency ordering.
    """
    from database.DB_Auth import Team, User, UserTeam
    from database.DB_Extensions import Extension
    from database.DB_Providers import Provider, ProviderExtension, ProviderInstance

    # Define a single ordered precedence list with all models that need specific ordering
    # This ensures proper dependency handling (e.g., Extension before ProviderExtension)
    precedence_models = [
        # Core models
        Team,
        User,
        UserTeam,
        # Feature models
        Extension,  # Must come before ProviderExtension
        Provider,
        ProviderInstance,
        ProviderExtension,  # Depends on both Provider and Extension
    ]

    logging.info(
        f"Models in precedence order: {[model.__name__ for model in precedence_models]}"
    )

    # Get all other SQLAlchemy models that inherit from Base
    models = []
    for subclass in Base.__subclasses__():
        if subclass not in precedence_models:
            models.append(subclass)
        # Also include further subclasses
        for sub_subclass in subclass.__subclasses__():
            if sub_subclass not in models and sub_subclass not in precedence_models:
                models.append(sub_subclass)

    logging.debug(f"Found additional models: {[model.__name__ for model in models]}")

    # Check which models have seed lists
    seed_list_models = []
    for model in precedence_models + models:
        if hasattr(model, "seed_list"):
            seed_list = getattr(model, "seed_list")
            if callable(seed_list) and not inspect.isclass(seed_list):
                try:
                    items = seed_list()
                    seed_list_models.append(
                        (model.__name__, len(items) if items else 0)
                    )
                except Exception as e:
                    logging.error(
                        f"Error calling seed_list function for {model.__name__}: {str(e)}"
                    )
                    seed_list_models.append((model.__name__, "Error"))
            else:
                seed_list_models.append(
                    (model.__name__, len(seed_list) if seed_list else 0)
                )

    logging.info(f"Models with seed_list: {seed_list_models}")

    # Return precedence models first, then the rest sorted by table name
    return precedence_models + sorted(
        models, key=lambda m: getattr(m, "__tablename__", "")
    )


def get_provider_by_name(session, provider_name):
    """
    Helper function to look up a provider by name.
    Extracted to make testing easier.
    """
    try:
        stmt = select(Provider).where(Provider.name == provider_name)
        provider = session.execute(stmt).scalar_one_or_none()

        if provider:
            logging.info(f"Found provider {provider_name} with ID {provider.id}")
            return provider
        else:
            logging.warning(f"Provider {provider_name} not found")
            return None
    except Exception as e:
        logging.error(f"Error looking up provider {provider_name}: {str(e)}")
        return None


def seed_model(model_class, session):
    """Helper function to seed a specific model class."""
    class_name = model_class.__name__
    logging.info(f"Processing seeding for {class_name}...")

    # First check if the class has a get_seed_list method (dynamic)
    if hasattr(model_class, "get_seed_list") and callable(model_class.get_seed_list):
        try:
            seed_list = model_class.get_seed_list()
            logging.info(
                f"Retrieved dynamic seed list with {len(seed_list)} items for {class_name}"
            )
        except Exception as e:
            logging.error(
                f"Error calling get_seed_list method for {class_name}: {str(e)}"
            )
            return
    # Otherwise check for the static seed_list attribute
    elif hasattr(model_class, "seed_list"):
        # Handle seed_list that is a callable
        seed_list = model_class.seed_list
        if callable(seed_list) and not inspect.isclass(seed_list):
            try:
                seed_list = seed_list()
                logging.info(
                    f"Called seed_list function for {class_name}, got {len(seed_list)} items"
                )
            except Exception as e:
                logging.error(
                    f"Error calling seed_list function for {class_name}: {str(e)}"
                )
                return
    else:
        logging.debug(f"Model {class_name} has no seed data")
        return

    if not seed_list:
        logging.info(f"No seed items for {class_name}")
        return

    logging.info(f"Seeding {class_name} table with {len(seed_list)} items...")

    # Process each seed item
    items_created = 0
    for item in seed_list:
        # Special handling for ProviderInstance with _provider_name
        is_provider_instance = class_name == "ProviderInstance" or (
            hasattr(model_class, "__tablename__")
            and model_class.__tablename__ == "provider_instance"
        )

        if is_provider_instance and "_provider_name" in item:
            # Look up the provider by name using our helper function
            provider_name = item.pop("_provider_name")
            provider = get_provider_by_name(session, provider_name)

            if provider:
                # Found the provider, add its ID
                item["provider_id"] = str(provider.id)
            else:
                # Provider not found, skip this instance
                logging.warning(
                    f"Skipping ProviderInstance for provider {provider_name}"
                )
                continue

        # Check if the item already exists using the 'exists' method
        exists = False
        try:
            if hasattr(model_class, "exists"):
                # Determine the field to check for existence, prioritizing 'id'
                if "id" in item:
                    check_field = "id"
                else:
                    check_field = next(
                        (k for k in ["name", "email"] if k in item),
                        None,  # Check name/email if no id
                    )

                if check_field:
                    exists = model_class.exists(
                        env("ROOT_ID"), db=session, **{check_field: item[check_field]}
                    )
            else:
                logging.warning(
                    f"Model {class_name} does not have an 'exists' method. Skipping existence check."
                )

        except Exception as e:
            logging.error(
                f"Error checking existence for {class_name} with {check_field}={item.get(check_field)}: {str(e)}"
            )
            continue

        if not exists:
            try:
                # Create the item
                if hasattr(model_class, "create"):
                    # Use the model's seed_id if available, otherwise fall back to SYSTEM_ID
                    creator_id = env("SYSTEM_ID")
                    if hasattr(model_class, "seed_id"):
                        creator_id = env(model_class.seed_id)
                        logging.info(
                            f"Using {model_class.seed_id} ({creator_id}) as creator for {class_name}"
                        )

                    model_class.create(creator_id, db=session, return_type="db", **item)
                    # Use "ProviderInstance" in log message if this is a provider instance
                    display_class_name = (
                        "ProviderInstance" if is_provider_instance else class_name
                    )
                    logging.info(
                        f"Created {display_class_name} item: {item.get('name', str(item))}"
                    )
                    items_created += 1
                else:
                    # Fallback to direct SQLAlchemy creation
                    new_instance = model_class(**item)
                    session.add(new_instance)
                    session.flush()
                    # Use "ProviderInstance" in log message if this is a provider instance
                    display_class_name = (
                        "ProviderInstance" if is_provider_instance else class_name
                    )
                    logging.info(
                        f"Created {display_class_name} item: {item.get('name', str(item))}"
                    )
                    items_created += 1
            except Exception as e:
                logging.error(f"Error creating {class_name} item: {str(e)}")
                continue

    logging.info(f"Created {items_created} items for {class_name}")
