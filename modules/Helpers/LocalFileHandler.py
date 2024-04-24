from modules.Helpers.FileHandler import FileHandler
import os


class LocalFileHandler(FileHandler):
    def init(self, helper) -> None:
        pass
    def read(self, path, mode='r'):
        """Reads content from a file. Supports binary mode for BOM check."""
        try:
            with open(path, mode) as file:
                return file.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"The file {path} does not exist.")

    def write(self, path, data, mode='w'):
        """Writes data to a file. Supports different modes."""
        with open(path, mode) as file:
            file.write(data)

    def delete(self, path):
        """Deletes a file."""
        try:
            os.remove(path)
        except FileNotFoundError:
            print(f"The file {path} does not exist, cannot delete.")

    def exists(self, path):
        """Checks if a file exists."""
        return os.path.exists(path)
    
    def get_size(self, path: str) -> int:
        """Returns the size of the file in bytes."""
        try:
            return os.path.getsize(path)
        except OSError:
            # Handle the error or re-raise as appropriate
            return 0  # Or raise an exception
        
    def makedirs(self, path: str) -> None:
        os.makedirs(path)

    def cleanup(self):
        pass

    def get_or_refresh_token(self):
        return ""