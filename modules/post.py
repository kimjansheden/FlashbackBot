from datetime import datetime
import os
import pickle
from typing import Optional
from venv import logger

from regex import E
from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.PostHelpers import PostHelpers
from modules.Logger import Logger
from modules.scraper import Scraper
from .Helpers.Helpers import Helpers
from .Notifier import Notifier
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class Post:
    """This class is responsible for logging in to Flashback and posting the answers generated by the language model."""

    def __init__(
        self, helper: Helpers, notifier: Notifier, file_handler: FileHandler
    ) -> None:
        self.helper = helper
        self.notifier = notifier
        self.scraper = Scraper(helper, file_handler)
        self.driver: Optional[webdriver.Chrome] = None
        self.config = self.helper.config
        self.flashback_url = os.getenv("FLASHBACK_URL", "https://www.flashback.org/")
        self.config = self.helper.config
        self.log_level = self.config["Logging"]["post_log_level"]
        self.logger = Logger(
            "Post Logger", "post_log.log", self.log_level, file_handler=file_handler
        )
        self.post_helper = PostHelpers(self.helper, self.logger)

        # LOAD PATHS
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 2
        )
        self.posts_dir = os.path.join(self.script_dir, "posts")
        self.session_path = os.path.join(self.script_dir, "session.pkl")
        self.pending_path = os.path.join(self.posts_dir, "pending.json")
        self.post_status_json_path = os.path.join(self.posts_dir, "post_status.json")
        self.post_history_json_path = os.path.join(self.posts_dir, "post_history.json")

        # Get the needed variables from the config file
        self.username = os.getenv("USERNAME")
        self.password = os.getenv("PASSWORD")

    def post(self, approved_id: str, approved_post):
        """
        Handles the posting of an approved reply on a web forum using a browser driver.

        Locks further posting activities, retrieves and constructs necessary data like the reply URL and message,
        and automates the web interaction needed to submit the post using a browser driver.

        Parameters:
        - approved_id (int): The ID of the approved post that will be used for follow-up actions.
        - approved_post (dict): A dictionary containing the approved message and metadata, including the original post's unique ID.

        Returns:
        - bool: True if the post was successfully submitted, False if an error occurred or no driver was found.
        """

        # Locking for further posting while this post is being posted
        self.helper.update_config("Misc", {"post_lock": "True"})

        answer_to_post = approved_post["generated_answer"]

        # Get the unique ID we need to quote the right post
        unique_id = approved_post["original_post"]["unique_id"]

        # Construct the Reply URL
        reply_url = self._construct_reply_url(unique_id)

        if self.driver is None:
            self.logger.info("No Driver found, can't post")
            return False
        try:
            self.driver.get(reply_url)

            # Check and accept cookies if needed
            self._accept_cookies_if_prompted()

            # Wait for the reply form to load
            time.sleep(2)  # Adjust sleep time as necessary

            # Fill in the form with Javascript (because ChromeDriver doesn't support BMP)
            text_area = self.driver.find_element(By.ID, "vB_Editor_001_textarea")
            script = """
            var existingText = arguments[0].value;
            arguments[0].value = existingText + arguments[1];
            """
            self.driver.execute_script(script, text_area, answer_to_post)

            # Submit the form
            # Replace 'submit_button_selector' with the actual selector for the submit button
            submit_button = self.driver.find_element(By.ID, "vB_Editor_001_save")
            submit_button.click()

            # Wait for the post to be processed
            time.sleep(2)  # Adjust sleep time as necessary

            self.driver.quit()
            self._after_posting(approved_id)
            return True
        except Exception as e:
            self.logger.error(f"Error posting: {e}")
            self.driver.quit()
            self.helper.update_config("Misc", {"post_lock": "False"})
            return False

    def login(self):
        """Return True if logged in and False if not logged in. If False, then something has gone wrong, because after this function has completed running, either an older logged in session will have been restored or a new logged in session will have started."""

        success = False

        if self.helper.file_handler.exists(self.session_path):
            success: bool = self._restore_session()

        if not success:
            success: bool = self._create_new_session()
            if success:
                success = self._check_login_status()

        return success

    def _construct_reply_url(self, unique_id):
        return f"https://www.flashback.org/newreply.php?do=newreply&p={unique_id}"

    def _after_posting(self, approved_id: str):
        """Performs various tasks after successful posting.

        Args:
            approved_id (str): The ID of the approved post.
        """
        self.notifier.delete_notification(approved_id)

        time_of_post = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.post_helper.move_post_to_history(
            approved_id, time_of_post, self.pending_path, self.post_history_json_path
        )

        self.helper.save_time_of_last_post(time_of_post)

        # Clears the waiting time
        self.helper.file_helper.update_json_file(
            self.post_status_json_path, {}, overwrite=True
        )

        # Unlocking the post lock
        self.helper.update_config("Misc", {"post_lock": "False"})

    def _create_new_session(self):
        """Creates a new session and logs in."""
        try:
            self.driver = self.scraper.setup_driver(headless=True)
            if self.driver is not None and self.flashback_url is not None:
                self.driver.get(self.flashback_url)

            # Wait for the consent button to be visible and click it
            consent_button = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "button.css-1ysvf99")
                )
            )
            consent_button.click()

            # Find and click the login button
            login_button = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "a[href='/login.php']")
                )
            )
            self.logger.debug("login_button", login_button)
            login_button.click()

            # Wait for the login page elements to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "vb_login_username"))
            )

            # Locate the username and password fields and the submit button
            username_field = self.driver.find_element(By.NAME, "vb_login_username")
            password_field = self.driver.find_element(By.NAME, "vb_login_password")
            submit_button = self.driver.find_element(
                By.CSS_SELECTOR, ".btn.btn-primary.btn-sm.btn-block"
            )

            # Input the username and password and submit the form
            username_field.send_keys(self.username)
            password_field.send_keys(self.password)
            submit_button.click()

            # Save the session after logging in
            cookies = self.driver.get_cookies()
            self.logger.debug("Cookies:", cookies)
            pickled_cookies = pickle.dumps(cookies)
            self.helper.file_handler.write(
                os.path.join(self.script_dir, "session.pkl"), pickled_cookies, mode="wb"
            )
            self.logger.info(
                f"New logged in session successfully created and saved to {self.session_path}"
            )
            return True
        except Exception as e:
            self.logger.info(f"Failed to create a new logged in session. Reason: {e}")
            if self.driver is not None:
                self.logger.debug(f"Current URL: {self.driver.current_url}")
                self.logger.debug(f"Page title: {self.driver.title}")
                try:
                    self.driver.save_screenshot("screenshot.png")
                except Exception as e:
                    self.logger.debug(f"Failed to save screenshot. Reason: {e}")
            return False

    def _restore_session(self):
        """Restores a saved session."""
        try:
            self.driver = self.scraper.setup_driver(headless=True)
            if self.flashback_url is not None:
                self.driver.get(self.flashback_url)
            session_data_bytes = self.helper.file_handler.read(
                self.session_path, mode="rb"
            )
            if session_data_bytes is None:
                raise FileNotFoundError(f"Session file {self.session_path} not found.")

            # Deserialize the session data from bytes
            # Ensure that session_data_bytes is a bytes-like object before deserialization
            if not isinstance(session_data_bytes, bytes):
                raise ValueError(
                    "Session data must be bytes-like object for deserialization with pickle.loads."
                )
            cookies = pickle.loads(session_data_bytes)
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            self.driver.refresh()
            success = self._check_login_status()
            if success:
                print("Existing logged in session successfully restored")
            return success
        except Exception as e:
            print(f"Failed to restore an existing logged in session. Reason: {e}")
            return False

    def _check_login_status(self):
        """Checks if the login menu is visible, indicating a successful login."""
        try:
            # Wait for the account menu to be visible
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "a.dropdown-toggle[data-toggle='dropdown'][role='button']",
                    )
                )
            )
            # If the above line doesn't throw an exception, the menu is visible
            self.logger.info("Login check succeeded. Bot is logged in.")
            return True
        except Exception as e:
            # If there is an exception, the menu is not visible
            self.logger.info(f"Login check failed. Reason: {e}")
            return False

    def _accept_cookies_if_prompted(self):
        try:
            # Wait for the consent button to become visible
            consent_button = WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "button.css-1ysvf99")
                )
            )
            consent_button.click()
            self.logger.debug("Accepted cookies.")
        except TimeoutException:
            # If the consent button is not visible within 5 seconds, assume it's not needed
            self.logger.debug("No consent button appeared.")
