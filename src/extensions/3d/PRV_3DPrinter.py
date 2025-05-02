from abc import abstractmethod
from typing import Any, Dict, List, Optional

from extensions.AbstractProvider import AbstractProvider


class Abstract3DPrinterProvider(AbstractProvider):
    """
    Abstract base class for all 3D printer service extensions.
    """

    def __init__(
        self,
        api_key: str = "",
        api_uri: str = "",
        access_token: str = "",
        printer_ip: str = "",
        extension_id: Optional[str] = None,
        agent_name: str = "",
        ApiClient: Optional[Any] = None,
        conversation_name: Optional[str] = None,
        wait_between_requests: int = 1,
        wait_after_failure: int = 3,
        **kwargs,
    ):
        """
        Initialize the 3D printer provider with configuration parameters.
        """
        self.access_token = access_token
        self.printer_ip = printer_ip
        self.agent_name = agent_name
        self.ApiClient = ApiClient
        self.conversation_name = conversation_name

        super().__init__(
            api_key=api_key,
            api_uri=api_uri,
            extension_id=extension_id,
            wait_between_requests=wait_between_requests,
            wait_after_failure=wait_after_failure,
            **kwargs,
        )

        # Set up common 3D printer commands that all providers need to implement
        self.commands = {
            f"Get {self.get_platform_name()} Printer Status": self.get_printer_status,
            f"Start {self.get_platform_name()} Print Job": self.start_print_job,
            f"Pause {self.get_platform_name()} Print Job": self.pause_print_job,
            f"Resume {self.get_platform_name()} Print Job": self.resume_print_job,
            f"Cancel {self.get_platform_name()} Print Job": self.cancel_print_job,
            f"Upload {self.get_platform_name()} Model": self.upload_model,
            f"Get {self.get_platform_name()} Print Jobs": self.get_print_jobs,
            f"Get {self.get_platform_name()} Temperature": self.get_printer_temperature,
            f"Set {self.get_platform_name()} Temperature": self.set_printer_temperature,
        }

    @abstractmethod
    async def get_printer_status(self) -> Dict[str, Any]:
        """
        Get the current status of the 3D printer.
        Returns information such as printer state, current job, and completion percentage.
        """
        pass

    @abstractmethod
    async def start_print_job(
        self, model_id: str, print_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Start a print job with the specified model.
        Print settings can include temperature, layer height, infill, etc.
        """
        pass

    @abstractmethod
    async def pause_print_job(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Pause the current print job.
        If job_id is not provided, pause the active print job.
        """
        pass

    @abstractmethod
    async def resume_print_job(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Resume the current print job.
        If job_id is not provided, resume the paused print job.
        """
        pass

    @abstractmethod
    async def cancel_print_job(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel the current print job.
        If job_id is not provided, cancel the active print job.
        """
        pass

    @abstractmethod
    async def upload_model(
        self, file_path: str, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a 3D model file to the printer.
        Acceptable formats typically include STL, GCODE, 3MF, etc.
        """
        pass

    @abstractmethod
    async def get_print_jobs(
        self, limit: int = 10, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of print jobs with their status.
        Can filter by status (e.g., 'printing', 'completed', 'failed').
        """
        pass

    @abstractmethod
    async def get_printer_temperature(self) -> Dict[str, Any]:
        """
        Get the current temperature readings from the printer.
        Typically includes hotend and bed temperatures (current and target).
        """
        pass

    @abstractmethod
    async def set_printer_temperature(
        self, hotend_temp: Optional[int] = None, bed_temp: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Set target temperatures for the printer.
        Can set hotend and/or bed temperature.
        """
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """
        Get the name of the 3D printer platform this provider interacts with.
        """
        pass

    @staticmethod
    def services() -> List[str]:
        """
        Return a list of services provided by this provider.
        """
        return ["3d_printing", "manufacturing", "rapid_prototyping"]

    def get_extension_info(self) -> Dict[str, Any]:
        """
        Get information about the 3D printer extension.
        """
        return {
            "name": "3D Printer",
            "platform": self.get_platform_name(),
            "description": f"3D Printer extension for {self.get_platform_name()}",
        }
