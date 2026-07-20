import pytest
from sqlalchemy.orm import Session

from src.models.database import sync_engine


@pytest.fixture
def db_session():
    """Session bound to a transaction that always rolls back — tests never dirty the dev DB."""
    connection = sync_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
