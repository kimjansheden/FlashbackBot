import codecs
import json
import os

from modules.Helpers.FileHandler import FileHandler


class FileHelpers:
    def __init__(self, file_handler: FileHandler) -> None:
        self.file_handler = file_handler

    def create_file_if_not_exist(self, filepath, what_to_write):
        """
        Ensures a file exists. If it doesn't, creates it with optional initial content.

        Args:
            filepath (str): The path to the file.
            what_to_write (str): Initial content to write if the file is created.
        """
        # Check if the file exists
        if not self.file_handler.exists(filepath):
            # We know here that the file doesn't exist. Therefore we can safely use mode="w" without risking any unwanted overwrites.
            self.file_handler.write(path=filepath, data=what_to_write, mode="w")

    def create_directory_if_not_exist(self, directory_path):
        """
        Ensures a directory exists. If it doesn't, creates it.

        Args:
            directory_path (str): The path to the directory.
        """
        if not self.file_handler.exists(directory_path):
            self.file_handler.makedirs(directory_path)
            print(f"Directory '{directory_path}' was created.")
        else:
            print(f"Directory '{directory_path}' already exists.")

    def read_file(self, filepath):
        """
        Reads the content of a file and returns it.

        Args:
            filepath (str): The path to the file.

        Returns:
            str: The content of the file.
        """
        return self.file_handler.read(filepath)

    def check_bom(self, filepath):
        """
        Checks if a file starts with a Byte Order Mark (BOM).

        Args:
            filepath (str): The path to the file.
        """
        content = self.file_handler.read(filepath, mode="rb")
        first_bytes = content[:3]
        if first_bytes == codecs.BOM_UTF8:
            print(f"BOM found in file {filepath}")
        else:
            print(f"No BOM found in file {filepath}")

    def write_file(self, filepath, what_to_write):
        """
        Writes the specified content to a file.

        Args:
            filepath (str): The path to the file to be written.
            what_to_write (Any): The content to write to the file. Will be converted to string before writing.

        Returns:
            none: Writes the content to the file.
        """
        self.file_handler.write(filepath, str(what_to_write))

    def read_json_file(self, filepath):
        """
        Reads a JSON file and returns its content. Creates the file if it doesn't already exist.

        Args:
            filepath (str): The path to the JSON file.

        Returns:
            dict: The content of the JSON file.
        """
        # Create the file if it doesn't already exist
        self.create_file_if_not_exist(filepath=filepath, what_to_write=r"{}")

        content = self.file_handler.read(filepath)

        # Check if the file is empty
        # If empty, return empty dict
        if self.file_handler.get_size(filepath) == 0:
            return {}

        # If not empty, read the file and load the json data
        existing_data = json.loads(content)

        return existing_data

    def update_json_file(self, filepath, new_data: dict, overwrite=False, deep_merge=False):
        """
        Updates a JSON file with new data. If 'overwrite' is set to True, it replaces the entire content of the file
        with 'new_data'. If 'overwrite' is False, it merges 'new_data' into the existing content of the file.
        In merge mode, if a key from 'new_data' already exists, its value will be updated. If a key does not exist,
        it will be added to the file. Returns True if the operation was successful, False otherwise.

        Args:
            filepath (str): The path to the JSON file.
            new_data (dict): The new data to be written to the JSON file.
            overwrite (bool, optional): Determines the mode of operation.
                                        If True, the entire JSON file is overwritten with 'new_data'.
                                        If False, 'new_data' is merged into the existing content of the JSON file.
                                        Default is False.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        if overwrite:
            try:
                # Write the new dict to the JSON file
                content = json.dumps(new_data, indent=4, ensure_ascii=False)
                self.file_handler.write(filepath, content)
                return True
            except Exception as e:
                print(f"Error updating JSON file: {e}")
                return False
        else:
            try:
                # Read existing data from JSON file. Create the file if it doesn't already exist
                existing_data = self.read_json_file(filepath)

                # Update existing data with the new data
                if deep_merge:
                    existing_data = self.deep_merge_dict(existing_data, new_data)
                else:
                    existing_data.update(new_data)

                # Write back the updated dict to the JSON file
                content = json.dumps(existing_data, indent=4, ensure_ascii=False)
                self.file_handler.write(filepath, content)
                return True
            except:
                return False

    def deep_merge_dict(self, original, new):
        """
        Deeply merges two dictionaries. New values from 'new' will be combined with
        existing values in 'original'. In case of conflicts, values from 'new' will overwrite those in 'original'.

        Args:
            original (dict): The original dictionary to merge into.
            new (dict): The new dictionary with values to merge into 'original'.

        Returns:
            dict: The merged dictionary.
        """
        for key, value in new.items():
            if key in original:
                if isinstance(original[key], dict) and isinstance(value, dict):
                    self.deep_merge_dict(original[key], value)
                else:
                    original[key] = value
            else:
                original[key] = value
        return original
    
    def get_base_path(self, abspath: str, levels_to_go_up: int) -> str:
        """
        Determines the base path by navigating up a specified number of directory levels from a valid absolute path,
        or returns a predefined base path in lowercase depending on the environment variable `BASE_PATH`.

        This function calculates a new path by moving up the specified number of levels from `abspath` if `BASE_PATH` is set to
        "LOCAL" or not set. If `BASE_PATH` is set to any other value, the function returns this predefined value in lowercase,
        as specified, without any modifications or path navigation.

        Parameters:
        - abspath (str): The starting absolute path, which should be a valid filesystem path. Must not be None.
            If you want to start where the current script is, use `os.path.abspath(__file__)`.
        - levels_to_go_up (int): The number of directory levels to navigate up from the `abspath`. If `levels_to_go_up` is 0,
        the function returns the directory containing the file, not the file path itself.

        Returns:
        - str: The calculated base path after navigating up the specified number of levels, or the exact value of `BASE_PATH`
        in lowercase if it is set to a value other than "LOCAL".

        Raises:
        - ValueError: If `abspath` is None, which means that a valid absolute path is required as input.
        - ValueError: If `levels_to_go_up` is negative, which means that the number of levels to go up cannot be negative.

        Examples:
        - Given an `abspath` of "/home/user/project/src/module" and `levels_to_go_up` of 2, the function would return
        "/home/user/project" if `BASE_PATH` is "LOCAL" or not set.
        - If `BASE_PATH` is set to "/fixed/path", that value in lowercase is returned regardless of the other parameters.

        Note:
        - This function is environment-aware and will behave differently based on the value of the `BASE_PATH` environment
        variable. This design allows for flexible path determination in different running contexts (e.g., local development
        vs. deployment).
        """
        if levels_to_go_up < 0:
            raise ValueError("The number of levels to go up cannot be negative")
        if abspath is None:
            raise ValueError("The absolute path cannot be None")
        base_path = os.getenv("BASE_PATH")
        if base_path == "LOCAL" or base_path is None:
            if levels_to_go_up == 0:
                return os.path.dirname(abspath) if os.path.isfile(abspath) else abspath
            for _ in range(levels_to_go_up):
                abspath = os.path.dirname(abspath)
            return abspath
        else:
            return f"/{base_path.lower()}"
