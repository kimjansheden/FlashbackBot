import sys
from modules.Helpers.Helpers import Helpers
from modules.scraper import Scraper


def main(url, save_to_path):
    helper = Helpers()
    scraper = Scraper(helper)
    scraper.scrape_single_page(url, save_to_path)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        url = sys.argv[1]
        save_to_path = sys.argv[2]
    else:
        print(f"Usage: python {sys.argv[0]} <url> <save_to_path>")
        sys.exit(1)
    main(url, save_to_path)
