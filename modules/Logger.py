from datetime import datetime, timezone
import os

from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.FileHelpers import FileHelpers
from modules.Helpers.LocalFileHandler import LocalFileHandler


class Logger:
    """Custom Logger Class for logging messages to both file and console.
    
    Provides methods to log messages at various levels including INFO, ERROR, DEBUG, and PARANOID. Each log level corresponds to an integer value that determines the verbosity of the logs:
    
    - NONE = 0: No logs are output.
    - INFO = 1: Standard information messages.
    - ERROR = 1: Error messages (same level as INFO).
    - DEBUG = 2: Detailed debugging information.
    - PARANOID = 3: Extremely detailed tracing for diagnostic purposes.

    Usage example:
        scraper_logger = Logger.create_logger("ScraperLogger", "scraper_log.log", Logger.DEBUG)
        act_logger = Logger.create_logger("ActLogger", "act_log.log", Logger.DEBUG)

    Returns:
        Logger: A logger instance.
    """

    LOG_LEVELS = {
        "NONE": 0,
        "INFO": 1,
        "ERROR": 1,  # Same level as INFO
        "DEBUG": 2,
        "PARANOID": 3,
    }

    def __init__(
        self,
        logger_name="Logger",
        file_name="log.log",
        log_level: str | int = LOG_LEVELS["INFO"],
        file_handler: FileHandler = LocalFileHandler(),
    ):
        """Initialize the Logger instance."""
        if isinstance(log_level, str):
            log_level_int = self._get_log_level(log_level)
        else:
            log_level_int = log_level
        self.log_level = log_level_int
        self.logger_name = logger_name
        self.file_handler = file_handler
        self.file_helper = FileHelpers(self.file_handler)
        self.script_dir = self.file_helper.get_base_path(os.path.abspath(__file__), 2)
        self.log_path = os.path.join(self.script_dir, file_name)

    def _write_to_file(self, message):
        """Write a message to the log file."""
        self.file_handler.write(self.log_path, mode="a", data=message + "\n")

    def _write_to_console(self, message):
        """Write a message to the console."""
        print(message)

    def _get_timestamp(self):
        """Get the current timestamp."""
        return datetime.now(timezone.utc).astimezone(None).strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _get_log_level(cls, log_level_str):
        """Convert a log level string to its numeric value."""
        return cls.LOG_LEVELS.get(log_level_str, cls.LOG_LEVELS["INFO"])

    def _format_message(self, level_name, message):
        """Format the log message."""
        timestamp = self._get_timestamp()
        return f"{timestamp} - {self.logger_name} - {level_name} - {message}"

    def log(self, level_name: str, message):
        """Log a message if the given log level is high enough."""
        level = self._get_log_level(level_name)
        if level <= self.log_level:
            formatted_message = self._format_message(level_name, message)
            self._write_to_file(formatted_message)
            self._write_to_console(formatted_message)

    def info(self, *args, **kwargs):
        """Logs an info message with multiple arguments concatenated."""
        message = self._conc_args(*args)
        self.log("INFO", message, **kwargs)

    def error(self, *args, **kwargs):
        """Logs an error message with multiple arguments concatenated."""
        message = self._conc_args(*args)
        self.log("ERROR", message, **kwargs)

    def debug(self, *args, **kwargs):
        """Logs a debug message with multiple arguments concatenated."""
        message = self._conc_args(*args)
        self.log("DEBUG", message, **kwargs)

    def paranoid(self, *args, **kwargs):
        """Logs a paranoid message with multiple arguments concatenated."""
        message = self._conc_args(*args)
        self.log("PARANOID", message, **kwargs)

    def change_log_level(self, new_log_level: int):
        """Change the log level of the logger.
        Log levels are:

        NONE = 0
        INFO = 1
        ERROR = 1
        DEBUG = 2
        PARANOID = 3

        Args:
            new_log_level (int): The new log level.

        Returns:
            None

        Raises:
            ValueError: If the new log level is not valid.
        """
        self.check_valid_log_level(new_log_level)

        self.log_level = new_log_level
        self.info(f"Log level changed to {self.log_level}")

    def _conc_args(self, *args):
        return " ".join(map(str, args))

    @classmethod
    def check_valid_log_level(cls, new_log_level: int):
        if new_log_level not in cls.LOG_LEVELS.values():
            raise ValueError("Invalid log level")
