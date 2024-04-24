from modules.Helpers.FileHandler import FileHandler
from modules.Logger import Logger
from .Helpers.Helpers import Helpers
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Chrome

import time
import random
import os
import json

SOUP_FEATURES = "html.parser"


class Scraper:
    """Parameters:
    helper (Helpers): Helper object providing configuration and utility methods.
    file_handler (FileHandler): File handler object for managing file operations.
    """

    def __init__(self, helper: Helpers, file_handler: FileHandler) -> None:
        self.helper = helper
        self.config = self.helper.config
        self.file_handler = file_handler

        # Load paths

        # Get the full path to the dir where the script is running
        # If it's running from a Docker Container, it will construct the script dir with the base path specified in the env. Otherwise, it will use the path of the script in the local machine
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 2
        )

        self.posts_dir = os.path.join(self.script_dir, "posts")
        self.forum_posts_total_path = os.path.join(self.posts_dir, "forum_posts.txt")
        self.forum_posts_total_json_path = os.path.join(
            self.posts_dir, "forum_posts.json"
        )
        self.unread_posts_json_path = os.path.join(self.posts_dir, "unread_posts.json")
        self.last_page_path = os.path.join(self.posts_dir, "last_page.txt")
        self.last_id_path = os.path.join(self.posts_dir, "last_id.txt")

        # Logger
        self.log_level = self.config["Logging"]["scraper_log_level"]
        self.logger = Logger(
            "Scraper Logger",
            "scraper_log.log",
            self.log_level,
            file_handler=file_handler,
        )

    def setup_driver(self, headless=True) -> webdriver.Chrome:
        """
        Initializes and configures a Chrome WebDriver instance with specific options for web scraping to optimize performance and prevent detection as an automated bot.

        Parameters:
        - headless (bool): If True, the Chrome browser is launched in headless mode. Defaults to True.

        Returns:
        - webdriver.Chrome: An instance of Chrome WebDriver with all configurations applied.

        Raises:
        - WebDriverException: If the Chrome WebDriver cannot be initiated on the first try, it attempts to use Chromium instead.
        """
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")  # Ensure GUI is off
        options.add_argument("--no-sandbox")  # Disable Chrome's sandboxing feature
        options.add_argument(
            "--disable-dev-shm-usage"
        )  # Don't use /dev/shm for data storage

        # Adding argument to disable the AutomationControlled flag
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Exclude the collection of enable-automation switches
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # Turn-off userAutomationExtension
        options.add_experimental_option("useAutomationExtension", False)

        try:
            # Choose Chrome Browser (First attempt)
            driver = webdriver.Chrome(options=options)
        except WebDriverException:
            self.logger.info(
                "Unable to obtain driver for Chrome using the default method; attempting to use Chromium instead..."
            )
            # Fallback to using Chromium if the first attempt fails
            chromium_path = os.getenv("CHROMIUM_PATH", "/usr/bin/chromium")
            chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
            options.binary_location = chromium_path
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(options=options, service=service)

        # Changing the property of the navigator value for webdriver to undefined
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        return driver

    def rotate_user_agent(self, driver):
        # List of User-Agents to rotate
        user_agents = self.config['Scraper']['user_agents'].split(' || ')

        user_agent = random.choice(user_agents)
        driver.execute_cdp_cmd(
            "Network.setUserAgentOverride", {"userAgent": user_agent}
        )

    def scrape(
        self, url_key: str, test_mode=False, page_number=1, mocked_html_path=None
    ) -> dict:
        """Scrapes a specified Flashback forum thread for new posts and processes them according to specified conditions.

        This function operates in a loop to navigate through forum pages, extract posts, and manage state across retries in case of failures or errors. It supports both normal operation and a test mode where it can use mocked HTML content for scraping. It:

        1. Checks if there are any new posts.
        2. Appends any new posts to the total posts and the unread posts.
        3. Returns the new posts to the bot for its decisions.

        The forum thread to be scraped is determined by the URL provided through the 'url_key' parameter.

        Args:
            url_key str: The name of the key in your config file or environment variable that holds the URL you want to scrape from.
                     This should be the URL of any forum thread from Flashback, formatted as 'https://www.flashback.org/your_thread'.
            test_mode (bool, optional): If True, uses mocked HTML from a given file path for scraping instead of live web pages. Defaults to False.
            page_number (int, optional): The starting page number from which scraping begins. Defaults to 1.
            mocked_html_path (str, optional): The file path to mocked HTML content used when test_mode is True.

        Returns:
            dict: A dictionary containing the new posts that were not previously scraped. Each key in the dictionary represents a post ID from the forum thread, and each value is another dictionary with details about the post, structured as follows:
                {
                    'unique_id': str - The unique identifier for the post on the forum's server.
                    'username': str - The username of the user who made the post.
                    'quote': {
                        'quoted_user': list[str] - A list of usernames who were quoted in this post.
                        'quoted_post': list[str] - A list of the actual text that was quoted from other posts.
                    },
                    'post': str - The text of the post after quotes have been removed.
                }

                Example:
                {
                    '42349': {
                        'unique_id': 'post12345',
                        'username': 'user123',
                        'quote': {
                            'quoted_user': ['user456'],
                            'quoted_post': ['This is an example of a quoted text.']
                        },
                        'post': 'This is the content of the post, following the quoted text.'
                    }
                }

        Notes:
        - The function uses an external webdriver for navigating the web and BeautifulSoup for parsing HTML content.
        - It incorporates error handling and retries for robustness against network issues or site access problems.
        - In test mode, scraped data is not appended to persistent storage but is instead returned directly for testing purposes.
        """
        self.logger.debug("Starting scraper...")
        unread_posts = (
            {}
        )  # Initialize unread_posts at the start to avoid UnboundLocalError

        forum_url = os.getenv(url_key.upper())
        self.logger.debug("Forum URL: " + str(forum_url))
        timeout_time = self.config.getint("Time", "scrape_timeout_time", fallback=300)

        outer_retry_count = 0  # Initialize an outer retry counter
        outer_max_allowed_retries = 1
        max_retries_msg = "Maximum number of retries reached. Restarting script..."

        while True:  # Outer loop to restart the scraping process
            # If we've restarted the script the max allowed times, we should be at the last page, so quit the script
            if outer_retry_count > outer_max_allowed_retries:
                self.logger.debug(
                    "Maximum number of restarts reached. Quitting script..."
                )
                break

            # Setup the driver
            self.logger.debug("Setting up driver …")
            driver = self.setup_driver()

            # ----------------------------------------------------------------------------------
            # DO THE SCRAPING
            # ----------------------------------------------------------------------------------

            if not test_mode:
                # Read the last page number from a file
                page_number = self._get_last_page_number(page_number)

            self.logger.debug(f"{forum_url}p{page_number}")
            driver.get(f"{forum_url}p{page_number}")

            # Wait for 3 seconds until finding the element
            wait = WebDriverWait(driver, 3)

            # Initialize a retry counters
            retry_count = 0
            post_ids_retry_count = 0
            max_allowed_retries = 1

            while True:
                # Wait 3.5 on the webpage before trying anything
                time.sleep(3.5)
                self.logger.info(f"Scraping page {page_number}")
                try:
                    # Rotate User-Agent
                    self.rotate_user_agent(driver)

                    # Check if we got a 503 error
                    if (
                        "<title>503 Service Temporarily Unavailable</title>"
                        in driver.page_source
                    ):
                        self.logger.debug(
                            "503 error detected, waiting 60 seconds before retrying..."
                        )
                        time.sleep(60)
                        continue

                    # Get the page source and create a BeautifulSoup object
                    soup = self._get_page_source(mocked_html_path, driver)

                    # Get the forum posts from where we left off (last_page)
                    (
                        post_ids_visual,
                        user_elements,
                        posts_elements,
                        post_ids_unique,
                        quotes_to_users_map,
                    ) = self._get_posts(soup)

                    # Check so post_ids are loaded
                    if len(post_ids_visual) == 0:
                        self.logger.debug("post_ids failed to load correctly.")
                        if (
                            post_ids_retry_count == max_allowed_retries
                        ):  # If we've retried the max, break the loop
                            self.logger.debug(max_retries_msg)
                            outer_retry_count += 1
                            break
                        self.logger.debug(
                            f"Waiting {timeout_time/60} minutes before retrying..."
                        )
                        time.sleep(timeout_time)
                        post_ids_retry_count += 1  # Increment the retry counter
                        continue
                    elif len(post_ids_visual) > 0:
                        post_ids_retry_count = 0  # Reset the retry counter
                    else:
                        raise ValueError(
                            "Unexpected error occurred while checking post_ids."
                        )

                    new_posts = self._create_dicts(
                        post_ids_visual,
                        user_elements,
                        posts_elements,
                        post_ids_unique,
                        quotes_to_users_map,
                    )

                    if test_mode:
                        driver.quit()
                        self._handle_mocked_html_path(mocked_html_path, new_posts)
                        return new_posts
                    new_posts, new_posts_json = self._remove_keys(new_posts)

                    unread_posts = self._save_files(new_posts_json, new_posts)

                    # Try to find the "next" button
                    try:
                        next_button = wait.until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "li.next a")
                            )
                        )
                    except TimeoutException as e:
                        self.logger.debug(
                            f"Could not find the next page element on page {page_number}: {e}"
                        )
                        if (
                            retry_count == max_allowed_retries
                        ):  # If we've retried the max, break the loop
                            self.logger.debug(max_retries_msg)
                            outer_retry_count += 1
                            break
                        self.logger.debug(
                            f"Waiting {timeout_time/60} minutes before retrying..."
                        )
                        time.sleep(timeout_time)
                        retry_count += 1  # Increment the retry counter
                        continue

                    outer_retry_count, page_number, retry_count = (
                        self._navigate_to_next_page_and_reset_counters(
                            next_button, driver, page_number
                        )
                    )

                except WebDriverException as e:
                    self.logger.debug(
                        f"A network error occurred on page {page_number}: {e}"
                    )
                    if (
                        retry_count == max_allowed_retries
                    ):  # If we've retried the max, break the loop
                        self.logger.debug(max_retries_msg)
                        outer_retry_count += 1
                        break
                    time.sleep(60)  # Wait for 60 seconds before trying again
                    retry_count += 1  # Increment the retry counter
                    continue
                except Exception as e:
                    self.logger.debug(f"An error occurred on page {page_number}: {e}")
                    break

            driver.quit()
        self.logger.debug("Closing scraper...")
        return unread_posts

    def scrape_single_page(self, url, save_to_file_path):
        driver = self.setup_driver()
        driver.get(url)
        time.sleep(5)

        # Get the page source
        page_source = driver.page_source

        driver.quit()

        # Parse the HTML content
        soup = BeautifulSoup(page_source, SOUP_FEATURES)

        # Convert the content to a string and specify UTF-8 as the encoding
        page_content = soup.prettify()

        # Write the content to the file with UTF-8 encoding
        self.file_handler.write(
            save_to_file_path, page_content, "w"
        )  # Might have to add encoding='utf-8'

        self.logger.info(f"The page has been saved in {save_to_file_path}")

    def extract_quotes(self, posts_elements):
        """Extracts quotes and their associated users from posts.

        Args:
            posts_elements: A list of BeautifulSoup objects that represent the posts.

        Returns:
            A tuple containing lists of quoted_posts, quoted_users, and a map of quotes to users.
        """
        quoted_posts = []
        quoted_users = []
        quotes_to_users_map = []
        for post in posts_elements:
            post_quotes = []
            post_quoted_users = []
            post_quotes_to_users = {}

            # Find all quotes in this post
            quotes_in_post = post.find_all("div", class_="alt2 post-bbcode-quote")

            for quote in quotes_in_post:
                post_quoted_user_elements = quote.select("strong")

                # Extracting text from each <strong> tag
                post_quoted_users_text = ",".join(
                    user.text.strip() for user in post_quoted_user_elements
                )
                post_quoted_users.append(post_quoted_users_text)

                # Remove all empty div elements within each quote
                for empty_div in quote.find_all("div", class_=""):
                    empty_div.extract()

                # Extract text of the quote and associate it with users
                quote_text = quote.text.strip()
                post_quotes.append(quote_text)
                post_quotes_to_users[quote_text] = post_quoted_users_text

            # Add post_quotes to the main list
            quoted_posts.append(post_quotes)
            quoted_users.append(post_quoted_users)
            quotes_to_users_map.append(post_quotes_to_users)

        self.logger.debug(f"quoted_posts: {quoted_posts}")
        self.logger.debug(f"quoted_users: {quoted_users}")
        self.logger.debug(f"quotes_to_users_map: {quotes_to_users_map}")
        return quoted_posts, quoted_users, quotes_to_users_map

    def _get_last_page_number(self, original_page_number: int):
        self.logger.debug(
            f"Attempting to read last page number from {self.last_page_path}"
        )
        try:
            new_page_number = int(self.file_handler.read(self.last_page_path, mode="r"))
            return new_page_number
        except FileNotFoundError:
            return original_page_number

    def _get_page_source(self, mocked_html_path, driver):
        if mocked_html_path is not None:
            mocked_html = self.helper.file_helper.read_file(mocked_html_path)
            return BeautifulSoup(mocked_html, SOUP_FEATURES)
        else:
            return BeautifulSoup(driver.page_source, SOUP_FEATURES)

    def _get_posts(self, soup):
        # Save one list with all posts per page with the quotes intact and one where the quotes will be stripped
        posts_elements = soup.select("div.post_message")
        posts_elements_with_quotes = [
            BeautifulSoup(str(element), SOUP_FEATURES) for element in posts_elements
        ]

        user_elements = soup.select("a.post-user-username")
        post_ids_visual = soup.select(
            "div.pull-right strong"
        )  # These are IDs you see together with the post. It represents the current number of posts in the actual thread. So if a post e.g. has an ID of #42349 it means that it's post number 42349 in the actual thread
        # quoted_users = soup.select("div.alt2.post-bbcode-quote strong")

        post_divs = soup.select("div.post")
        post_ids_unique = [
            post.get("data-postid") for post in post_divs
        ]  # These are the unique IDs on the forum's server

        quoted_posts, quoted_users, quotes_to_users_map = self.extract_quotes(
            posts_elements
        )

        # Extract the texts from the strong tags (post_ids)
        post_ids_visual = [tag.text.strip() for tag in post_ids_visual]

        # Strip the usernames of their whitespaces
        user_elements = [tag.text.strip() for tag in user_elements]

        # Remove content in .post-bbcode-quote-wrapper in each post_element
        for index, post_element in enumerate(posts_elements, start=1):
            self.logger.debug(
                f"Stripping post_element quote {index} of {len(posts_elements)}"
            )
            for quote in post_element.select(".post-bbcode-quote-wrapper"):
                quote.extract()

        # Get the remaining text
        self.logger.debug("Getting remaining posts elements")
        posts_elements = [
            post_element.get_text().strip() for post_element in posts_elements
        ]

        # Print what we've got
        self.logger.debug(
            len(post_ids_visual),
            len(quoted_users),
            len(quotes_to_users_map),
            len(user_elements),
            len(posts_elements),
        )

        return (
            post_ids_visual,
            user_elements,
            posts_elements,
            post_ids_unique,
            quotes_to_users_map,
        )

    def _create_dicts(
        self,
        post_ids_visual,
        user_elements,
        posts_elements,
        post_ids_unique,
        quotes_to_users_map,
    ):
        self.logger.debug("Starting to create dicts.")
        new_posts = {}
        for index, (
            post_id,
            user_element,
            post_element,
            unique_id,
            quotes_to_users,
        ) in enumerate(
            zip(
                post_ids_visual,
                user_elements,
                posts_elements,
                post_ids_unique,
                quotes_to_users_map,
            ),
            start=1,
        ):
            self.logger.debug(f"Creating dict {index} of {len(post_ids_visual)}")
            quoted_users_list = list(quotes_to_users.values())
            quoted_posts_list = list(quotes_to_users.keys())

            new_posts[post_id] = {
                "unique_id": unique_id,
                "username": user_element,
                "quote": {
                    "quoted_user": quoted_users_list,
                    "quoted_post": quoted_posts_list,
                },
                "post": post_element,
            }
            self.logger.debug(
                f"Finished creating dict {index} of {len(post_ids_visual)}"
            )

        return new_posts

    def _remove_keys(self, new_posts):
        # Get the last id previously scraped/seen by the bot
        last_id = self.file_handler.read(self.last_id_path, "r")

        # If the new post id is less than or equal to the last seen id, then the bot has already seen this post and it can be removed from new_posts. Otherwise it will remain.
        keys_to_remove = []

        # Get the keys to be removed
        for post_id in new_posts.keys():
            if int(post_id) <= int(last_id):
                keys_to_remove.append(post_id)

        # Remove the keys from the dictionary
        for key in keys_to_remove:
            new_posts.pop(key)

        new_posts_json = json.dumps(new_posts, indent=4, ensure_ascii=False)
        self.logger.debug(new_posts_json)

        return new_posts, new_posts_json

    def _handle_mocked_html_path(self, mocked_html_path, new_posts):
        if mocked_html_path is not None:
            # Save the results
            mocked_html_results = (
                mocked_html_path.rsplit(".html", 1)[0] + "_results.json"
            )
            self.helper.file_helper.update_json_file(
                mocked_html_results, new_posts, overwrite=True
            )

    def _save_files(self, new_posts_json, new_posts):
        # Now we have a dict new_posts that only contains posts that are neither in the list of saved posts nor seen by the bot before.

        # Now we save (append) these
        #   - first to the total posts (save both forum_posts.txt and forum_posts.json for the time being)
        self.file_handler.write(self.forum_posts_total_path, new_posts_json, mode="a")

        # Update forum_posts.json
        self.helper.file_helper.update_json_file(
            self.forum_posts_total_json_path, new_posts
        )

        #   - last id to last_id.txt
        if new_posts:
            highest_id = max([int(key) for key in new_posts.keys()])
            self.file_handler.write(self.last_id_path, mode="w", data=str(highest_id))
        else:
            # Handle the case when new_posts is empty, e.g. log an error message
            self.logger.debug("new_posts is empty!")

        #   - and to unread_posts.json

        # Update unread_posts.json
        self.helper.file_helper.update_json_file(self.unread_posts_json_path, new_posts)

        # Loads the complete file of unread posts (the old + the eventual newly retrieved)
        unread_posts_file = self.file_handler.read(self.unread_posts_json_path, "r")
        unread_posts = json.loads(unread_posts_file)

        # Then we repeat this until we get to the last page. Then we have everything saved, so we never need to re-scrape anything if it would freeze. Now we return unread_posts to the bot to make decisions. Once it has processed all unread posts and made the decisions, then it clears unread_posts.json. So it will be filled up again when there are new posts on the forum.

        return unread_posts

    def _navigate_to_next_page_and_reset_counters(
        self, next_button, driver, org_page_number: int
    ):
        # Get the URL of the next page
        next_page_url = next_button.get_attribute("href")

        # Wait 4.5 seconds before scrolling down 700px
        time.sleep(4.5)
        driver.execute_script("window.scrollTo(0, 700)")

        # Wait 2 seconds before clicking a link
        time.sleep(2)
        # Navigate to the next page
        driver.get(next_page_url)

        # We have successfully navigated to the next page, so reset the outer retry counter
        outer_retry_count = 0
        new_page_number = org_page_number + 1  # Change to the next page
        retry_count = 0  # Reset the retry counter after a successful page load

        # Save the current page number to a file
        self.file_handler.write(self.last_page_path, str(new_page_number), "w")

        return outer_retry_count, new_page_number, retry_count
