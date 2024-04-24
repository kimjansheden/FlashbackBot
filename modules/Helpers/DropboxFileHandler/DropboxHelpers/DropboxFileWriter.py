from requests.exceptions import ConnectionError
from typing import Optional, Union
from dropbox.exceptions import ApiError
from dropbox.files import (
    WriteMode,
    UploadSessionStartResult,
    CommitInfo,
    UploadSessionCursor,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Helpers.DropboxFileHandler.DropboxFileHandler import (
        DropboxFileHandler,
        DropboxFileAppender,
    )


class DropboxFileWriter:
    """
    Manages writing and uploading files to Dropbox or caching them locally, based on the specified handler's settings.

    Attributes:
        handler (DropboxFileHandler): The handler responsible for managing Dropbox operations and associated utilities.
        dbx_client: The Dropbox client obtained from the handler.
        log_helper: A logging helper obtained from the handler for logging activities.
        lock: A threading lock from the handler to manage concurrent access.
        cache (dict): A local cache for file contents managed by the handler.
        appender (DropboxFileAppender | None): A utility to handle file appending if required.
    """

    def __init__(self, handler: "DropboxFileHandler"):
        self.handler = handler
        self.dbx_client = handler.get_client()
        self.log_helper = handler.log_helper
        self.lock = handler.lock
        self.cache = handler.cache
        self.appender: "DropboxFileAppender | None" = None
        self.large_file_limit = 150 * 1024 * 1024

    def write(self, path: str, data: Union[str, bytes], mode: str = "w"):
        """
        Writes data to Dropbox or caches it locally, supporting different write modes.

        This method handles direct uploads to Dropbox or writes to a local cache, depending on the current configuration. For more details, see the docstrings of the super class.

        Raises:
            FileExistsError: If mode 'x' is used and the file already exists.
            ApiError: For Dropbox API-related errors during file operations.
            FileNotFoundError: If there's an error indicating the file could not be found and cannot be created.
        """
        if "a" in mode:
            if self.appender is None:
                self.appender = self.handler.get_appender()
            self.appender.append(path, data, mode)
            return

        # If "x" is in mode, the file should be written to only if it doesn't already exist.
        # For overwrite behavior, "w" should be used.
        if "x" in mode:
            self.log_helper.debug(
                self.handler.get_logger(),
                "x mode detected. Checking if file exists.",
            )
            if self.handler.exists(path):
                raise FileExistsError(
                    f"File {path} already exists. Use 'w' in mode to overwrite."
                )

        if self.handler.use_cache:
            self._write_to_cache(path, data, mode)
        else:
            self._write_to_dropbox(path, data, mode)

    def create_new_file(self, path: str, new_content: str | bytes):
        """
        Creates a new file in Dropbox with the given content if the file does not already exist.

        Args:
            path (str): The Dropbox path where the file will be created.
            new_content (Union[str, bytes]): The content to populate the new file with.

        Notes:
            Encodes string data to bytes before uploading if necessary.
        """
        logger = self.handler.get_logger()
        self.log_helper.debug(
            logger,
            f"File {path} does not exist in Dropbox. Attempting to create it with {new_content}",
            path=path,
        )
        # If the file does not exist, start with the new content
        self.dbx_client.files_upload(
            (
                new_content.encode("utf-8")
                if isinstance(new_content, str)
                else new_content
            ),
            path,
            mode=WriteMode.add,
        )
        self.handler.num_calls += 1
        self.log_helper.info(
            logger,
            f"Created new file {path} in Dropbox with appended content.",
            path=path,
        )

    def _write_to_dropbox(self, path: str, data: Union[str, bytes], mode: str = "w"):
        """
        Handles writing data to Dropbox, either by directly uploading or by initiating a chunked upload session for large files.

        Args:
            path (str): The file path in Dropbox.
            data (Union[str, bytes]): The data to write.
            mode (str): The file access mode.

        Notes:
            Handles large files by uploading in chunks.
        """
        logger = self.handler.get_logger()
        data_size = len(data.encode("utf-8") if isinstance(data, str) else data)
        data_size_to_display, unit = self.handler.convert_size_to_display(data_size)
        self.log_helper.debug(
            logger,
            f"Attempting to upload {path} with size {data_size_to_display:.2f} {unit} to Dropbox.",
            path=path,
        )
        # files_upload has a limit of 150 mb. If data_size is above that limit, create an upload session with files_upload_session_start
        # and upload the data with files_upload_session_append. This is more efficient than uploading the data in chunks.
        # files_upload_session_finish is used to finalize the upload session.
        if data_size > self.large_file_limit:
            self._upload_in_chunks(path, data, data_size, mode)
        else:
            self._upload_regular(path, data, data_size, mode)

    def _write_to_cache(self, path, data, mode: str = "w"):
        """
        Writes data to the local cache.

        Args:
            path (str): The file path in the local cache.
            data (Union[str, bytes]): The data to cache.
            mode (str): The file access mode.

        Notes:
            Thread safety is ensured by checking and possibly locking the threading lock.
        """
        logger = self.handler.get_logger()
        if self.lock.locked():
            self.cache[path] = data
        else:
            with self.lock:
                self.cache[path] = data
        self.log_helper.debug(
            logger,
            f"File {path} cached for future writing to Dropbox.",
            path=path,
        )

    def _upload_in_chunks(
        self, path: str, data: Union[str, bytes], data_size: int, mode: str = "w"
    ):
        """
        Handles the upload of large files in chunks.

        Args:
            path (str): The file path in Dropbox.
            data (Union[str, bytes]): The data to upload.
            data_size (int): The size of the data in bytes.
            mode (str): The file access mode.

        Notes:
            Uploads the data in chunks of 4 MB to efficiently handle large files that exceed the standard upload limit of 150 MB.
        """
        logger = self.handler.get_logger()
        chunk_size = 4 * 1024 * 1024  # 4 MB chunk size
        self.log_helper.debug(
            logger, f"Data size {data_size} exceeds the allowed {self.large_file_limit}. Uploading data in chunks."
        )
        # Make sure data is bytes
        data = (
            data.encode("utf-8")
            if isinstance(data, str)
            else data
        )
        try:
            # Start an upload session with the first chunk of data
            sess_result: Optional[UploadSessionStartResult] = (
                self.dbx_client.files_upload_session_start(
                    data[:chunk_size]  # First chunk of data
                )
            )
            # Initialize the cursor with the session ID and the size of the uploaded chunk
            if isinstance(sess_result, UploadSessionStartResult):
                cursor = UploadSessionCursor(
                    session_id=sess_result.session_id,
                    offset=len(data[:chunk_size]),
                )
                # Loop through the rest of `data` in `chunk_size` pieces using `files_upload_session_append_v2`
                for i in range(chunk_size, len(data), chunk_size):
                    next_chunk = data[i : i + chunk_size]
                    self.dbx_client.files_upload_session_append_v2(next_chunk, cursor)
                    cursor.offset += len(
                        next_chunk
                    )  # Update the cursor offset after each upload

                # Prepare the commit with the destination path and mode to overwrite
                commit = CommitInfo(path=path, mode=WriteMode.overwrite)
                # Finish the upload session with an empty byte string (since all data was already uploaded)
                self.dbx_client.files_upload_session_finish(b"", cursor, commit)
                self.handler.num_calls += 1
                self.log_helper.debug(logger, f"Wrote {path} to Dropbox in chunks.")
        except ApiError as e:
            self.log_helper.debug(
                logger, f"Failed to write {path} to Dropbox in chunks: {e}"
            )

    def _upload_regular(
        self, path: str, data: Union[str, bytes], data_size: int, mode: str = "w"
    ):
        """
        Uploads regular-sized files directly to Dropbox without chunking.

        Args:
            path (str): The path of the file in Dropbox.
            data (Union[str, bytes]): The data to upload. If string, it will be encoded to UTF-8 bytes.
            data_size (int): The size of the data in bytes.
            mode (str): The file access mode, which determines how the file is handled.

        Raises:
            ApiError: If Dropbox returns an API-related error not associated with the path of the file or other upload issues.
            FileNotFoundError: If a non-path related error occurs indicating the file could not be found, and thus cannot be created.
        """
        logger = self.handler.get_logger()
        try:
            self.dbx_client.files_upload(
                data.encode("utf-8") if isinstance(data, str) else data,
                path,
                mode=WriteMode.overwrite,
            )
            self.handler.num_calls += 1
            self.log_helper.debug(
                logger,
                f"File {path} written to Dropbox.",
                path=path,
            )
        except ApiError as error:
            if error.error.is_path() and error.error.get_path().is_not_found():
                self.create_new_file(path, data)
            else:
                self.log_helper.debug(
                    logger,
                    f"Could not write file {path} to Dropbox: {error}",
                    path=path,
                )
                raise
        except FileNotFoundError as error:
            self.create_new_file(path, data)
        except ConnectionError as error:
            if "The write operation timed out" in str(error):
                self.log_helper.debug(
                    logger,
                    f"Could not write file {path} to Dropbox due to a timeout error: {error}\nLowering size limit and trying to upload in chunks",
                    path=path,
                )
                current_size_display, unit = self.handler.convert_size_to_display(
                    data_size
                )
                self.large_file_limit = self.calculate_new_size_limit(
                    current_size_display, unit, subtract_size_mb=5
                )
                self._upload_in_chunks(path, data, data_size, mode)
            else:
                self.log_helper.debug(
                    logger,
                    f"Could not write file {path} to Dropbox due to a connection error (not a timeout error): {error}",
                    path=path,
                )

    def calculate_new_size_limit(
        self, current_size_display: float, unit: str, subtract_size_mb: float
    ) -> int:
        """
        Calculate a new size limit by subtracting a certain size in MB from the given size.

        Args:
            current_size_display (float): The current file size as displayed (in the unit provided).
            unit (str): The unit of the current size ('MB' in this case).
            subtract_size_mb (float): The size in MB to subtract from the current size.

        Returns:
            int: The new size limit in bytes.

        Example usage: Calculate new size limit by subtracting 5 MB from 35.72 MB
            current_size_display = 35.72  # The size in MB
            unit = "MB"  # The unit of the current size
            subtract_size_mb = 5  # The amount to subtract in MB
            new_size_limit = calculate_new_size_limit(current_size_display, unit, subtract_size_mb)

            print(f"New size limit: {new_size_limit} bytes")
        """
        if unit == "KB":
            size_in_bytes = current_size_display * 1024
        elif unit == "MB":
            size_in_bytes = current_size_display * 1024**2
        elif unit == "GB":
            size_in_bytes = current_size_display * 1024**3
        else:
            raise ValueError("Unknown unit for size display")

        subtract_bytes = subtract_size_mb * 1024**2
        new_size_limit = int(size_in_bytes - subtract_bytes)
        return new_size_limit
