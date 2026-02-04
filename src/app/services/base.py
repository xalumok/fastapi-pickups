"""Base service class with common functionality."""

import logging
from abc import ABC
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseService(ABC):
    """
    Base service class providing common functionality for all services.

    Services encapsulate business logic and coordinate between
    repositories, external APIs, and other services.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the service with a database session.

        Args:
            db: SQLAlchemy async session for database operations.
        """
        self._db = db
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def db(self) -> AsyncSession:
        """Get the database session."""
        return self._db

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger
