# Database Architecture Patterns

## Core Architecture

- SQLAlchemy ORM with declarative base
- Multi-database support (InfluxDB, PostgreSQL, MariaDB, MSSQL, Pinecone, Chroma and SQLite)
  - The core of the database can select between PostgresSQL, MariaDB, MongoDB, MSSQL or SQLite.
  - The vector portion of the database can either be integrated, or separate on Pincone or Chroma.
  - Optional logging using InfluxDB (in other layers, no implementation in DB files). 
- UUIDs are used as primary keys throughout (PK_TYPE denotes the actual type).
  - IDs are stored as UUIDs regardless of database type, this means either native, UNIQUEIDENTIFIER (MSSQL) or TEXT (SQLite).
- `system` denotes system tables, which should only ever be CRUD'd with the system API key.
- Session management through `get_session()` factory function.
- Database connection pooling (pool_size=40, max_overflow=-1).
- Custom SQLite regex support through function registration.
- Enumerations should be stored in the smallest data type possible (usually an int variant) for a given enum (use SqlEnum).
```python
from enum import IntEnum as PyEnum
from sqlalchemy import Enum as SqlEnum
class MFAMethodType(PyEnum):
    TOTP = 1
    EMAIL = 2
    SMS = 3

# Column definition using SqlAlchemy Enum type
method_type = Column(SqlEnum(MFAMethodType), nullable=False)
```
- All columns except primary and foreign keys should have comments explaining their function.

## Reference Mixins (Not in Mixins.py)

Every table should define both an optional and required mixin for itself (nullable vs non-nullable foreign key) - this mixin is used on other tables referencing this table. Note that these should not include column comments. For example:

```python
class UserRefBaseMixin:
    @declared_attr
    def user(cls):
        return relationship(
            User.__name__,
            backref=(pluralize(cls.__tablename__))
        )

    @declared_attr
    def user_id(cls):
        # Default behavior is required (nullable=False)
        return Column(
            PK_TYPE, 
            ForeignKey(f"{User.__tablename__}.id"), 
            index=True, 
            nullable=False
        )

class OptionalUserRefMixin(UserRefBaseMixin):
    @declared_attr
    def user_id(cls):
        return Column(
            PK_TYPE,
            ForeignKey(f"{User.__tablename__}.id"),
            index=True,
            nullable=True 
        )
```
In counterpart to the table that implements the mixin, after the class declaration usea a post-class late-binding to implement the reverse:
```python
# Define relationship after class definition to avoid circular imports
Entity.users = relationship(User.__name__, backref=singularize(Entity.__tablename__))
```

## Vector Handling (`DB_Memories.py`):
- Custom `Vector` type for embedding storage in:
  ```python
  class Vector(TypeDecorator):
      """Unified vector storage for both SQLite and PostgreSQL"""
      impl = VARCHAR if DATABASE_TYPE == "sqlite" else ARRAY(Float)
      cache_ok = True

      def process_bind_param(self, value, dialect):
          """Convert vector to storage format"""
          if value is None:
              return None

          # Convert to numpy array and ensure 1D
          if isinstance(value, np.ndarray):
              value = value.reshape(-1).tolist()
          elif isinstance(value, list):
              value = np.array(value).reshape(-1).tolist()

          # For SQLite, store as string representation
          if DATABASE_TYPE == "sqlite":
              return f'[{",".join(map(str, value))}]'

          # For PostgreSQL, return as list
          return value

      def process_result_value(self, value, dialect):
          """Convert from storage format to numpy array"""
          if value is None:
              return None

          # For SQLite, parse string representation
          if DATABASE_TYPE == "sqlite":
              try:
                  value = eval(value)
              except:
                  return None

          # Convert to 1D numpy array
          return np.array(value).reshape(-1)
  ```

## ORM Event Handling

- `@event.listens_for` for DB event registration
- Custom triggers for post-save actions
- Lifecycle hooks for entity state transitions

## Seed Data Pattern (Optional)

- Class-level `seed_list` attribute containing default records:
  ```python
  class ActivityType(Base, BaseMixin,UpdateMixin):
      __tablename__ = "activity_types"
      # ... column definitions ...
      
      seed_list = [
          {
              "id": "FFFFFFFF-FFFF-FFFF-0000-FFFFFFFFFFFF"
              "name": "Error",
              "description": "The agent has encountered an error.",
          },
          {
              "id": "FFFFFFFF-FFFF-FFFF-00FF-FFFFFFFFFFFF",
              "name": "Warning",
              "description": "The agent has encountered a warning.",
          },
          {
              "id": "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
              "name": "Thinking",
              "description": "The agent is thinking.",
          },
      ]
  ```
- Seed data invoked during database initialization
- IDs in seed data follow a specific format: 3 sections of `F` followed by a discriminator section, followed by another section of `F`.

## Column and Index Best Practices

- Every FK column should have an index
- Column naming should follow a consistent pattern:
  - `id` for primary keys
  - `[entity]_id` for foreign keys (except if there are multiple to the same table)
  - `parent_id` for self-references (in most cases)
  - Descriptive names for all other columns
- Timestamp columns should use standard names:
  - `created_at`, `updated_at`, `deleted_at`
  - `expires_at` for expirable entities
  - `[action]_at` for specific events (e.g., `last_login_at`)

## Performance Optimization Patterns

- Similarity search optimizations:
  - Vector indexing for embedding similarity
  - Custom similarity functions for database portability
  - Cross-database compatible search implementation
- Strategic use of ORM loading options:
  - Selecting specific columns with `load_only()`
  - Controlling relationship loading with `joinedload()`, `selectinload()`, or `lazyload()`
- Batch processing for bulk operations

## Domain Model Organization

- Clear domain boundaries with separate DB_[Domain].py files
- Hierarchical organization of related entities
- Consistent application of mixins across domains
- Cross-domain relationships defined with clear ownership
- Permission delegation patterns between domains