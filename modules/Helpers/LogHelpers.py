from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Logger import Logger

class LogHelpers:
    def __init__(self, **kwargs) -> None:
        self.exclude_if_in_path = kwargs.get("exclude_if_in_path", [])
    
    def paranoid(self, logger: "Logger | None", *log_msg, **kwargs):
        message = self._conc_args(*log_msg)
        if self._should_exclude(**kwargs):
            return
        if kwargs.get("force_print", False):
            print(message)
        if logger:
            logger.paranoid(message)
        else:
            # print(message)
            return

    def debug(self, logger: "Logger | None", *log_msg, **kwargs):
        message = self._conc_args(*log_msg)
        if self._should_exclude(**kwargs):
            return
        if kwargs.get("force_print", False):
            print(message)
        if logger:
            logger.debug(message)
        else:
            # print("Logger is None: ", logger)
            return
        
    def error(self, logger: "Logger | None", *log_msg, **kwargs):
        message = self._conc_args(*log_msg)
        if self._should_exclude(**kwargs):
            return
        if kwargs.get("force_print", False):
            print(message)
        if logger:
            logger.error(message)
        else:
            print(message)

    def info(self, logger: "Logger | None", *log_msg, **kwargs):
        message = self._conc_args(*log_msg)
        if self._should_exclude(**kwargs):
            return
        if kwargs.get("force_print", False):
            print(message)
        if logger is not None:
            logger.info(message)
        else:
            print(message)

    def _conc_args(self, *args) -> str:
        return " ".join(map(str, args))

    def _should_exclude(self, **kwargs) -> bool:
        """Check if the log should be excluded based on the path."""
        # Extract 'path' from kwargs, providing a default value if not present.
        # Generally only applicable to File Handlers logging which files they handle
        # to avoid endless loops when writing to a log file and logging that it's writing …
        ## TODO: Figure out a better way to handle this, because now the risk is you forget to include "path=path" when you call the LogHelper.
        path = kwargs.get('path', '')

        # Ensure path is not None and check if the log should be excluded based on the path
        if path and self.exclude_if_in_path and any(exclude in path for exclude in self.exclude_if_in_path):
            return True
        return False
