from typing import Union
from dropbox.exceptions import ApiError
from dropbox.files import FileMetadata, WriteMode

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Helpers.DropboxFileHandler.DropboxFileHandler import DropboxFileHandler


class DropboxFileAppender:
    """
    Manages appending content to files stored in Dropbox or in a local cache.

    Attributes:
        handler (DropboxFileHandler): The handler responsible for managing Dropbox operations and associated utilities.
        dbx_client: The Dropbox client obtained from the handler.
        log_helper: A logging helper obtained from the handler for logging activities.
        lock: A threading lock from the handler to manage concurrent access.
        cache (dict): A local cache for file contents managed by the handler.
        reader: The file reader object from the handler for reading file content.
        writer: The file writer object from the handler for writing file content.
    """

    def __init__(self, handler: "DropboxFileHandler"):
        self.handler = handler
        self.dbx_client = handler.get_client()
        self.log_helper = handler.log_helper
        self.lock = handler.lock
        self.cache = handler.cache
        self.reader = self.handler.get_reader()
        self.writer = self.handler.get_writer()

    def append(self, path: str, new_content: Union[str, bytes], mode: str = "w"):
        """
        Appends new content to a file at the specified path. The method first checks if caching is enabled, and appends to cache; otherwise, it appends directly to Dropbox.

        Args:
            path (str): The path of the file in Dropbox.
            new_content (Union[str, bytes]): The content to append to the file.
            mode (str): The file access mode, defaults to 'w' which indicates write mode.
        """
        if self.handler.use_cache:
            self._append_to_cache(path, new_content, mode)
        else:
            self._append_to_dropbox(path, new_content, mode)

    def _append_to_dropbox(self, path, new_content: Union[str, bytes], mode: str = "w"):
        logger = self.handler.get_logger()
        self.log_helper.debug(
            logger, f"Attempting to read {path} from Dropbox", path=path
        )
        try:
            updated_content = self._combine_content_to_bytes(path, new_content, mode)

            self.log_helper.debug(
                logger,
                f"Attempting to append updated content to {path} in Dropbox. In reality, we overwrite the old file with the new content",
                path=path,
            )
            # Upload the updated content, overwriting the existing file
            self.dbx_client.files_upload(
                updated_content, path, mode=WriteMode.overwrite
            )
            self.handler.num_calls += 1
            self.log_helper.info(
                logger, f"Appended content to {path} in Dropbox.", path=path
            )
        except ApiError as error:
            if error.error.is_path() and error.error.get_path().is_not_found():
                self.writer.create_new_file(path, new_content)
            else:
                raise
        except FileNotFoundError as error:
            self.writer.create_new_file(path, new_content)
        except Exception as error:
            # Handle other errors
            self.log_helper.info(
                logger,
                f"Could not append content to {path} in Dropbox: {error}",
                path=path,
            )

    def _combine_content_to_bytes(self, path, new_content, mode) -> bytes:
        """
        Combines new content with existing content from Dropbox, ensuring both are in bytes format.

        Args:
            path (str): The path of the file in Dropbox.
            new_content (Union[str, bytes]): The new content to be appended.
            mode (str): The file access mode.

        Returns:
            bytes: The combined content in bytes format.
        """
        logger = self.handler.get_logger()
        # Attempt to retrieve the existing file from Dropbox
        existing_content = self.reader.read_from_dropbox(path, mode)

        # Check if the new content is text or binary
        # If text, encode it to bytes before appending it
        # If binary, just append it
        # This is because the Dropbox API only accepts bytes
        if isinstance(new_content, str):
            self.log_helper.debug(
                logger,
                f"New Content is text. Attempting to encode it to bytes before appending it",
                path=path,
            )
            new_content = new_content.encode("utf-8")
        if isinstance(existing_content, str):
            self.log_helper.debug(
                logger,
                f"Existing Content is text. Attempting to encode it to bytes before appending it",
                path=path,
            )
            existing_content = existing_content.encode("utf-8")
        updated_content = existing_content + new_content

        return updated_content

    def _append_to_cache(
        self, path: str, new_content: Union[str, bytes], mode: str = "w"
    ):
        """
        Appends new content to a file in the local cache, managing thread-safe access and handling potential errors.

        Args:
            path (str): The path of the file in the local cache.
            new_content (Union[str, bytes]): The content to append.
            mode (str): The file access mode.
        """
        logger = self.handler.get_logger()
        try:
            # Attempt to retrieve the existing content from cache first
            existing_content = self.reader.read_from_cache(path, mode)

            new_content = self._coherent_types(new_content, existing_content, path)

            # Combine the contents
            updated_content = existing_content + new_content

            self.log_helper.debug(
                logger,
                f"Attempting to write updated content to {path} in cache",
                path=path,
            )
            # Update the cache with the combined content
            if self.lock.locked():
                self.cache[path] = updated_content
            else:
                with self.lock:
                    self.cache[path] = updated_content
            self.log_helper.debug(
                logger, f"Updated content cached for {path}.", path=path
            )
        except ApiError as error:
            if error.error.is_path() and error.error.get_path().is_not_found():
                # If the file neither exists in cache or Dropbox, start with the new content
                self.log_helper.debug(
                    logger,
                    f"File {path} does not exist either in cache or Dropbox. Attempting to create it with new content",
                    path=path,
                )
                with self.lock:
                    self.cache[path] = new_content if isinstance(new_content, str) else new_content.decode("utf-8")  # type: ignore
            else:
                self.log_helper.debug(
                    logger,
                    f"Could not append content to {path} in cache: {error}",
                    path=path,
                )
                raise
        except ValueError as error:
            self.log_helper.debug(
                logger,
                f"Could not append content to {path} in cache: {error}",
                path=path,
            )
            raise

        # Ensure the updated content is written to cache
        self.log_helper.debug(
            logger,
            f"Attempting to write updated content to cache",
            path=path,
        )
        self.writer.write(path, self.cache[path])

    def _coherent_types(
        self,
        new_content: Union[str, bytes],
        existing_content: Union[str, bytes],
        path: str,
    ):
        """
        Ensures that the new content and existing content have coherent types (both str or both bytes) before appending.

        Args:
            new_content (Union[str, bytes]): The new content to append.
            existing_content (Union[str, bytes]): The existing content in the file.
            path (str): The file path.

        Returns:
            Union[str, bytes]: The new content converted to the same type as existing content if necessary.
        """
        logger = self.handler.get_logger()
        # Ensure both contents are in the same format
        if isinstance(existing_content, str) and isinstance(new_content, bytes):
            return new_content.decode("utf-8")  # Convert bytes to string
        elif isinstance(existing_content, bytes) and isinstance(new_content, str):
            return new_content.encode("utf-8")  # Convert string to bytes
        elif not isinstance(existing_content, (str, bytes)) or not isinstance(
            new_content, (str, bytes)
        ):
            head = 20
            self.log_helper.debug(
                logger,
                f"Unexpected types for content: existing_content type: {type(existing_content)}, new_content type: {type(new_content)}.\nFirst {head} rows of the files:\nexisting_content: {existing_content[:head]}\nnew_content: {new_content[:head]}",
                path=path,
            )
            return new_content
        else:
            return new_content
