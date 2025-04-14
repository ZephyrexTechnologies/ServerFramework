import logging
from enum import Enum
from os import makedirs, path

from sqlalchemy import UUID, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base, sessionmaker

from lib.Environment import env

Operation = Enum("Operation", ["CREATE", "READ", "UPDATE", "DELETE"])


def setup_sqlite_for_regex(engine):
    """
    Register the REGEXP function with SQLite.

    This should be called after creating the SQLite engine.
    """
    import re
    import sqlite3

    def regexp(expr, item):
        if item is None:
            return False
        try:
            reg = re.compile(expr)
            return reg.search(item) is not None
        except Exception:
            return False

    # Register the function
    sqlite3.Connection.create_function("REGEXP", 2, regexp)

    # For SQLAlchemy, we need to register it with the engine's connect event
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.create_function("REGEXP", 2, regexp)


DEFAULT_USER = env("DEFAULT_USER")
try:
    DATABASE_TYPE = env("DATABASE_TYPE")
    DATABASE_NAME = env("DATABASE_NAME")
    PK_TYPE = UUID if DATABASE_TYPE != "sqlite" else String

    if DATABASE_TYPE != "sqlite":
        # PostgreSQL connection setup
        DATABASE_USER = env("DATABASE_USER")
        DATABASE_PASSWORD = env("DATABASE_PASSWORD")
        DATABASE_HOST = env("DATABASE_HOST")
        DATABASE_PORT = env("DATABASE_PORT")
        DATABASE_SSL = env("DATABASE_SSL")

        if DATABASE_SSL == "disable":
            LOGIN_URI = f"{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
        else:
            LOGIN_URI = f"{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}?sslmode={DATABASE_SSL}"

        DATABASE_URI = f"postgresql://{LOGIN_URI}"

    else:
        # SQLite connection setup with file check
        db_file = f"{DATABASE_NAME}.db"
        DATABASE_URI = f"sqlite:///{db_file}"

        # Ensure the parent directory exists
        db_dir = path.dirname(path.abspath(db_file))
        try:
            if not path.exists(db_dir):
                makedirs(db_dir)
                logging.info(f"Created directory path: {db_dir}")
        except Exception as e:
            logging.error(f"Error creating directory path: {e}")
            raise

        # Check if the database file exists
        if not path.exists(db_file):
            try:
                # Create an empty file
                open(db_file, "a").close()
                logging.info(f"Created new SQLite database file: {db_file}")
            except Exception as e:
                logging.error(f"Error creating SQLite database file: {e}")
                raise

    # Create engine with connection pool settings
    engine = create_engine(DATABASE_URI, pool_size=40, max_overflow=-1)

    if DATABASE_TYPE == "sqlite":
        import re
        import sqlite3

        def regexp(expr, item):
            if item is None:
                return False
            try:
                reg = re.compile(expr)
                return reg.search(item) is not None
            except Exception:
                return False

        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            dbapi_connection.create_function("REGEXP", 2, regexp)

    # Test the connection
    connection = engine.connect()
    connection.close()

    # Create base class for declarative models
    Base = declarative_base()

    # Create session factory
    Session = sessionmaker(bind=engine)

    logging.info("Successfully connected to database")

except Exception as e:
    logging.error(f"Error connecting to database: {e}")
    Base = None
    engine = None
    Session = None


def get_session():
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()
    return session
