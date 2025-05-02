import asyncio
import logging
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, TypeVar

from sqlalchemy.orm import Session

from database.Base import get_session

T = TypeVar("T", bound="AbstractService")


class AbstractService(ABC):
    """
    Abstract base class for all service components.

    Services are background tasks that run periodically, typically used for
    scheduled operations, monitoring, or other ongoing tasks that need to
    execute in the background.

    Features:
    - Configurable run interval
    - Automatic error handling and retry logic
    - Resource cleanup
    - Lifecycle management (start, stop, pause)
    """

    def __init__(
        self,
        requester_id: str,
        db: Optional[Session] = None,
        interval_seconds: int = 60,
        max_failures: int = 3,
        retry_delay_seconds: int = 5,
        service_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the service.

        Args:
            requester_id: ID of the user requesting the service
            db: Optional database session
            interval_seconds: Time between service update executions in seconds
            max_failures: Maximum number of consecutive failures before service stops
            retry_delay_seconds: Time to wait after a failure before retrying
            service_id: Optional unique identifier for the service instance. Auto-generated if None.
            **kwargs: Additional service-specific parameters
        """
        self.requester_id = requester_id
        self._db = db
        self._close_db_on_exit = db is None
        self.interval_seconds = interval_seconds
        self.max_failures = max_failures
        self.retry_delay_seconds = retry_delay_seconds
        self.failures = 0
        self.running = False
        self.paused = False
        self._last_run_time = 0
        self.service_id = service_id or str(uuid.uuid4())
        self._configure_service(**kwargs)

    def _configure_service(self, **kwargs) -> None:
        """
        Configure service-specific settings.
        Override this method in subclasses to handle initialization
        of service-specific settings.
        """
        pass

    @property
    def db(self) -> Session:
        """Property that returns an active database session, creating a new one if needed."""
        if self._db is None or not self._db.is_active:
            self._db = get_session()
            self._close_db_on_exit = True
        return self._db

    def start(self) -> None:
        """Start the service running in the background."""
        if self.running:
            logging.info(
                f"{self.__class__.__name__} ({self.service_id}) is already running"
            )
            return

        self.running = True
        self.paused = False
        logging.info(f"Started {self.__class__.__name__} ({self.service_id})")

    def stop(self) -> None:
        """Stop the service from running."""
        self.running = False
        logging.info(f"Stopped {self.__class__.__name__} ({self.service_id})")

    def pause(self) -> None:
        """Pause the service temporarily."""
        if not self.running:
            logging.warning(
                f"{self.__class__.__name__} ({self.service_id}) is not running, cannot pause"
            )
            return

        self.paused = True
        logging.info(f"Paused {self.__class__.__name__} ({self.service_id})")

    def resume(self) -> None:
        """Resume a paused service."""
        if not self.running:
            logging.warning(
                f"{self.__class__.__name__} ({self.service_id}) is not running, cannot resume"
            )
            return

        if not self.paused:
            logging.warning(
                f"{self.__class__.__name__} ({self.service_id}) is not paused, cannot resume"
            )
            return

        self.paused = False
        logging.info(f"Resumed {self.__class__.__name__} ({self.service_id})")

    def _handle_failure(self, error: Exception) -> bool:
        """
        Handle a failure and determine if retrying is appropriate.

        Args:
            error: Exception that occurred

        Returns:
            True if the operation should be retried, False otherwise

        Raises:
            Exception: If max failures reached
        """
        self.failures += 1
        logging.error(
            f"{self.__class__.__name__} ({self.service_id}) error: {str(error)}"
        )
        logging.debug(traceback.format_exc())

        if self.failures > self.max_failures:
            self.running = False
            raise Exception(
                f"{self.__class__.__name__} ({self.service_id}) Error: Too many failures. {error}"
            )

        return True

    def _reset_failures(self) -> None:
        """Reset the failure counter after a successful execution."""
        self.failures = 0

    async def run_service_loop(self) -> None:
        """
        Main service loop that runs update() at the configured interval.
        This method should be called from an event loop.
        """
        while self.running:
            try:
                current_time = time.time()

                # Skip if paused
                if self.paused:
                    await asyncio.sleep(1)  # Short sleep while paused
                    continue

                # Check if it's time to run again
                if current_time - self._last_run_time < self.interval_seconds:
                    # Sleep for a short time to avoid busy-waiting
                    await asyncio.sleep(0.1)
                    continue

                # Update last run time
                self._last_run_time = current_time

                # Run the update method
                await self.update()

                # Reset failure counter after successful execution
                self._reset_failures()

            except Exception as e:
                retry = self._handle_failure(e)
                if retry:
                    # Wait before retrying
                    await asyncio.sleep(self.retry_delay_seconds)
                else:
                    break  # Stop the service if we shouldn't retry

    @abstractmethod
    async def update(self) -> None:
        """
        Main method to perform the service's work.
        This method should be implemented by all service subclasses.
        """
        pass

    def cleanup(self) -> None:
        """
        Perform any necessary cleanup when the service is being shut down.
        Override this method in subclasses to add specific cleanup operations.
        """
        logging.info(f"Cleaning up {self.__class__.__name__} ({self.service_id})")
        self.stop()

    def __del__(self):
        """Clean up resources when the service is destroyed"""
        self.cleanup()
        if hasattr(self, "_db") and self._db is not None and self._close_db_on_exit:
            self._db.close()
            self._db = None


class ServiceRegistry:
    """
    Registry for managing service instances.

    This provides a central place to register, retrieve, and manage
    the lifecycle of service instances.
    """

    _services: Dict[str, AbstractService] = {}

    @classmethod
    def register(cls, service_id: str, service: AbstractService) -> None:
        """
        Register a service instance.

        Args:
            service_id: Unique identifier for the service
            service: Service instance to register
        """
        if service_id in cls._services:
            logging.warning(
                f"Service with ID {service_id} already registered. Overwriting."
            )
        cls._services[service_id] = service
        logging.info(f"Service {service_id} registered ({service.__class__.__name__})")

    @classmethod
    def unregister(cls, service_id: str) -> None:
        """
        Unregister a service instance.

        Args:
            service_id: Unique identifier for the service to unregister
        """
        if service_id in cls._services:
            service = cls._services.pop(service_id)
            service.cleanup()
            logging.info(
                f"Service {service_id} unregistered ({service.__class__.__name__})"
            )

    @classmethod
    def get(cls, service_id: str) -> Optional[AbstractService]:
        """
        Get a registered service instance.

        Args:
            service_id: Unique identifier for the service

        Returns:
            The service instance or None if not found
        """
        return cls._services.get(service_id)

    @classmethod
    def list(cls) -> List[str]:
        """
        Get a list of all registered service IDs.

        Returns:
            List of registered service IDs
        """
        return list(cls._services.keys())

    @classmethod
    def start_all(cls) -> None:
        """Start all registered services."""
        for service_id, service in cls._services.items():
            try:
                service.start()
                # Logging now happens within service.start()
            except Exception as e:
                logging.error(
                    f"Failed to start service {service_id} ({service.__class__.__name__}): {e}"
                )

    @classmethod
    def stop_all(cls) -> None:
        """Stop all registered services."""
        for service_id, service in cls._services.items():
            try:
                service.stop()
                # Logging now happens within service.stop()
            except Exception as e:
                logging.error(
                    f"Failed to stop service {service_id} ({service.__class__.__name__}): {e}"
                )

    @classmethod
    def cleanup_all(cls) -> None:
        """Clean up all registered services."""
        for service_id in list(cls._services.keys()):
            try:
                cls.unregister(service_id)
                # Logging happens within unregister/cleanup
            except Exception as e:
                logging.error(f"Failed to cleanup/unregister service {service_id}: {e}")
        logging.info("All services cleaned up")
