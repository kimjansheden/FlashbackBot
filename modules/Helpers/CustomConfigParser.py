import configparser
import io

class CustomConfigParser(configparser.ConfigParser):
    def __init__(self, file_handler, config_file_path):
        super().__init__()
        self.file_handler = file_handler
        self.config_file_path = config_file_path


    def update_config(self, title: str, key_value: dict):
        """
        Updates the configuration file with new key-value pairs under a given title
        without overwriting other keys in the same section.

        Args:
            title (str): The section title in the configuration file.
            key_value (dict): Dictionary containing key-value pairs to update.
        """
        config = self

        # Check if the section exists, if not create it
        if title not in config.sections():
            config.add_section(title)

        # Update only the specified key-value pairs
        for key, value in key_value.items():
            config.set(title, key, value)

        # Convert config to a string and write using the file handler
        config_str = io.StringIO()
        config.write(config_str)
        config_str.seek(0)  # Rewind the buffer to the beginning
        self.file_handler.write(self.config_file_path, config_str.read())

        # Reload the configuration to reflect the updates
        self.read(self.config_file_path)