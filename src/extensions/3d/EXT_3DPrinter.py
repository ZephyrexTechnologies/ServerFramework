import logging
from typing import Any, Dict, List, Optional

from extensions.AbstractExtension import AbstractExtension, ExtensionDependency
from extensions.calendar.bambu_lab import BambuLabProvider
from extensions.calendar.creality_cloud import CrealityCloudProvider
from extensions.calendar.prusa_connect import PrusaConnectProvider


class EXT_3DPrinter(AbstractExtension):
    """
    3D Printer extension for AGInfrastructure.
    Currently supports PrusaConnect, Bambu Lab, and Creality Cloud.
    """

    # Extension metadata
    name = "3d_printer"
    description = "3D Printer extension for monitoring and controlling 3D printers"

    # Dependencies
    dependencies = [
        ExtensionDependency(name="oauth", optional=True),
    ]

    def __init__(
        self,
        printer_platform: str = "prusa",
        api_key: str = "",
        access_token: str = "",
        printer_ip: str = "",
        **kwargs,
    ):
        """
        Initialize the 3D printer extension.
        """
        self.printer_platform = printer_platform.lower()
        self.access_token = access_token
        self.printer_ip = printer_ip

        # Initialize base class
        super().__init__(api_key=api_key, **kwargs)

    def _initialize_extension(self) -> None:
        """
        Initialize the 3D printer extension with the appropriate provider.
        """
        try:
            if self.printer_platform == "prusa":
                self.provider = PrusaConnectProvider(
                    api_key=self.api_key,
                    access_token=self.access_token,
                    printer_ip=self.printer_ip,
                    agent_name=self.agent_name,
                    ApiClient=self.ApiClient,
                    conversation_name=self.conversation_name,
                    extension_id=self.name,
                )
            elif self.printer_platform == "bambu":
                self.provider = BambuLabProvider(
                    api_key=self.api_key,
                    access_token=self.access_token,
                    printer_ip=self.printer_ip,
                    agent_name=self.agent_name,
                    ApiClient=self.ApiClient,
                    conversation_name=self.conversation_name,
                    extension_id=self.name,
                    **self.settings,
                )
            elif self.printer_platform == "creality":
                self.provider = CrealityCloudProvider(
                    api_key=self.api_key,
                    access_token=self.access_token,
                    printer_ip=self.printer_ip,
                    agent_name=self.agent_name,
                    ApiClient=self.ApiClient,
                    conversation_name=self.conversation_name,
                    extension_id=self.name,
                    **self.settings,
                )
            else:
                logging.error(f"Unsupported printer platform: {self.printer_platform}")
                self.provider = None
        except Exception as e:
            logging.error(f"Error initializing 3D printer provider: {str(e)}")
            self.provider = None

        # Set up commands mapping to provider methods
        if self.provider:
            self.commands = self.provider.commands
        else:
            # Provide placeholder commands that warn about missing provider
            self.commands = {
                f"Get {self.printer_platform.upper()} Printer Status": self._no_provider_warning,
                f"Start {self.printer_platform.upper()} Print Job": self._no_provider_warning,
                f"Pause {self.printer_platform.upper()} Print Job": self._no_provider_warning,
                f"Resume {self.printer_platform.upper()} Print Job": self._no_provider_warning,
                f"Cancel {self.printer_platform.upper()} Print Job": self._no_provider_warning,
                f"Upload {self.printer_platform.upper()} Model": self._no_provider_warning,
            }

    async def _no_provider_warning(self, *args, **kwargs) -> str:
        """
        Warning message when a provider is not available.
        """
        return f"No 3D printer provider available for {self.printer_platform}. Please check your configuration."

    async def get_printer_status(self) -> Dict[str, Any]:
        """
        Get the current status of the 3D printer.
        """
        if self.provider:
            return await self.provider.get_printer_status()
        return await self._no_provider_warning()

    async def start_print_job(
        self, model_id: str, print_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Start a print job with the specified model.
        """
        if self.provider:
            return await self.provider.start_print_job(model_id, print_settings)
        return await self._no_provider_warning()

    async def pause_print_job(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Pause the current print job.
        """
        if self.provider:
            return await self.provider.pause_print_job(job_id)
        return await self._no_provider_warning()

    async def resume_print_job(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Resume the current print job.
        """
        if self.provider:
            return await self.provider.resume_print_job(job_id)
        return await self._no_provider_warning()

    async def cancel_print_job(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel the current print job.
        """
        if self.provider:
            return await self.provider.cancel_print_job(job_id)
        return await self._no_provider_warning()

    async def upload_model(
        self, file_path: str, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a 3D model file to the printer.
        """
        if self.provider:
            return await self.provider.upload_model(file_path, model_name)
        return await self._no_provider_warning()

    async def get_print_jobs(
        self, limit: int = 10, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of print jobs with their status.
        """
        if self.provider:
            return await self.provider.get_print_jobs(limit, status)
        return await self._no_provider_warning()

    async def get_printer_temperature(self) -> Dict[str, Any]:
        """
        Get the current temperature readings from the printer.
        """
        if self.provider:
            return await self.provider.get_printer_temperature()
        return await self._no_provider_warning()

    async def set_printer_temperature(
        self, hotend_temp: Optional[int] = None, bed_temp: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Set target temperatures for the printer.
        """
        if self.provider:
            return await self.provider.set_printer_temperature(hotend_temp, bed_temp)
        return await self._no_provider_warning()
