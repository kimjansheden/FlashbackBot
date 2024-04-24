from abc import ABC, abstractmethod
from re import A
from typing import Union
from modules.Helpers.LogHelpers import LogHelpers


class FileHandler(ABC):
    def __init__(self) -> None:
        self.log_helper = LogHelpers()

    @abstractmethod
    def read(self, path: str, mode: str = "r") -> str | bytes:
        """
        Reads content from a file. Returns a string for text mode or bytes for binary mode.

        Args:
            path (str): The path to the file.
            mode (str): The mode in which to open the file. Defaults to "r" (text mode).

        Returns:
            str | bytes: The content of the file as a string in text mode, or bytes in binary mode.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        pass

    @abstractmethod
    def write(self, path: str, data: str | bytes, mode: str = "w") -> None:
        """
        Writes data to a file. Supports different modes including text and binary.

        This method can write both text and binary data to a file. The mode parameter determines how the file is opened and written to. For text data, use modes like
        'w' (write text, overwrite existing), 'a' (append text). For binary data, use
        'wb' (write binary, overwrite existing), 'ab' (append binary).

        Args:
            path (str): The path to the file.
            data (str | bytes): The data to write to the file. Can be either a
                                      string (text) or bytes (binary).
            mode (str): The mode in which to open the file. Defaults to "w" for writing
                        in text mode. Include 'b' in the mode (e.g., 'wb') to write
                        binary data.

                            'w' - Overwrite the existing file or create if it does not exist.

                            'a' - Append to the existing file or create if it does not exist.

                            'x' - Create the file only if it does not already exist. If it does exist, raises FileExistsError. So this mode will NOT overwrite existing files, only create new ones.
                            
                            'b' - Write binary data.

        Examples:
            # 1. We want to create a config file with default values only if it doesn't already exist. If it exists, we don't want to overwrite the existing file with the default values. We then use mode 'x'.
            config_file_path = 'config.json'
            config_data = '{"key1": "value1", "key2": "value2"}'
            file_handler.write(config_file_path, config_data, mode='x')

            # 2. We want to append some text to an existing file.
            existing_file_path = 'existing_file.txt'
            file_handler.write(existing_file_path, 'New text to append', mode='a')

        Raises:
            FileExistsError: If mode 'x' is used and the file already exists.
            FileNotFoundError: If there's an error indicating the file could not be found and cannot be created.

        Returns:
            None
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> None:
        """
        Deletes a file.

        Args:
            path (str): The path to the file to be deleted.

        Returns:
            None

        Raises:
            FileNotFoundError: If the file does not exist or cannot be deleted.
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Checks if a path exists.

        Args:
            path (str): The path to the file.

        Returns:
            bool: True if the path exists, False otherwise.
        """
        pass

    @abstractmethod
    def makedirs(self, path: str) -> None:
        """
        Creates a directory.

        Args:
            path (str): The path to the directory.

        Returns:
            None
        """
        pass

    @abstractmethod
    def get_size(self, path: str) -> int:
        """Returns the size of the file in bytes."""
        pass

    @abstractmethod
    def init(self, helper) -> None:
        """
        Initializes the file handler.

        Returns:
            None
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Perform necessary cleanup, default does nothing."""
        pass

    @abstractmethod
    def get_or_refresh_token(self) -> str:
        """
        Returns the access token or refreshes the access token if necessary.

        Returns:
            str: The access token.
        """
        pass
