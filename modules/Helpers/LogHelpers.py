from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Logger import Logger

class LogHelpers:
    """
    Helper class for logging messages with various log levels.

    Attributes:
        exclude_if_in_path (list): List of paths to exclude from logging.

    Example:
        Instantiate the LogHelpers class and use its methods:

        ```python
        from modules.Logger import Logger
        from log_helpers import LogHelpers

        logger = Logger()
        log_helper = LogHelpers(exclude_if_in_path=['/exclude/path'])

        log_helper.paranoid(logger, "This is a paranoid log message.")
        log_helper.debug(logger, "This is a debug log message.")
        log_helper.error(logger, "This is an error log message.", force_print=True)
        log_helper.info(logger, "This is an info log message.")
        ```

    Methods:
        paranoid(logger, *log_msg, **kwargs): Logs a paranoid message.
        debug(logger, *log_msg, **kwargs): Logs a debug message.
        error(logger, *log_msg, **kwargs): Logs an error message.
        info(logger, *log_msg, **kwargs): Logs an info message.
    """
    def __init__(self, **kwargs) -> None:
        """
        Initializes the LogHelpers instance.

        Args:
            **kwargs: Arbitrary keyword arguments. 'exclude_if_in_path' can be 
                      provided as a list of paths to exclude from logging.
        """
        self.exclude_if_in_path = kwargs.get("exclude_if_in_path", [])
    
    def paranoid(self, logger: "Logger | None", *log_msg, **kwargs):
        """
        Logs a paranoid message if conditions are met.

        Args:
            logger (Logger | None): Logger instance to log the message. 
                                    If None, the message is printed if 'force_print' is True.
            *log_msg: Variable length argument list for the log message.
            **kwargs: Arbitrary keyword arguments. 'force_print' can be provided to print the message.
        """
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
        """
        Logs a debug message if conditions are met.

        Args:
            logger (Logger | None): Logger instance to log the message. 
                                    If None, the message is printed if 'force_print' is True.
            *log_msg: Variable length argument list for the log message.
            **kwargs: Arbitrary keyword arguments. 'force_print' can be provided to print the message.
        """
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
        """
        Logs an error message if conditions are met.

        Args:
            logger (Logger | None): Logger instance to log the message. 
                                    If None, the message is printed.
            *log_msg: Variable length argument list for the log message.
            **kwargs: Arbitrary keyword arguments. 'force_print' can be provided to print the message.
        """
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
        """
        Logs an info message if conditions are met.

        Args:
            logger (Logger | None): Logger instance to log the message. 
                                    If None, the message is printed.
            *log_msg: Variable length argument list for the log message.
            **kwargs: Arbitrary keyword arguments. 'force_print' can be provided to print the message.
        """
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
        """
        Concatenates the given arguments into a single string.

        Args:
            *args: Variable length argument list to concatenate.

        Returns:
            str: Concatenated string of all arguments.
        """
        return " ".join(map(str, args))

    def _should_exclude(self, **kwargs) -> bool:
        """
        Checks if the log should be excluded based on the path.

        Args:
            **kwargs: Arbitrary keyword arguments. 'path' can be provided to check against 
                      the exclusion list.

        Returns:
            bool: True if the log should be excluded, False otherwise.
        """
        # Extract 'path' from kwargs, providing a default value if not present.
        # Generally only applicable to File Handlers logging which files they handle
        # to avoid endless loops when writing to a log file and logging that it's writing …
        ## TODO: Figure out a better way to handle this, because now the risk is you forget to include "path=path" when you call the LogHelper.
        path = kwargs.get('path', '')

        # Ensure path is not None and check if the log should be excluded based on the path
        if path and self.exclude_if_in_path and any(exclude in path for exclude in self.exclude_if_in_path):
            return True
        return False
