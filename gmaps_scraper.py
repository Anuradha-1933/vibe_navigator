# scraper.py
# A multi-platform scraper for the Vibe Navigator project.
#
# Usage:
#   For Google Maps:
#   python scraper.py gmaps "Cafes in Delhi" --limit 10
#
#   For Reddit:
#   python scraper.py reddit "Best quiet parks in Bangalore" --limit 5
#
# It will produce a unified CSV file ready for your AI pipeline.

import sys
import time
import pandas as pd
import praw
import argparse
from tqdm import tqdm

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Configuration ---
# Number of reviews to attempt to scrape per Google Maps location.
GMAPS_REVIEWS_PER_LOCATION = 25
# Default output filename
OUTPUT_FILENAME = "vibe_navigator_data.csv"

# --- Reddit API Credentials (REPLACE WITH YOURS) ---
# IMPORTANT: Fill these in to use the Reddit scraper.
REDDIT_CLIENT_ID = "aY1L7dYWw5NqzTBrvyhAXA"
REDDIT_CLIENT_SECRET = "S_KG1oENtWWaRyR4CUzHMmTSc4EW0Q"
REDDIT_USER_AGENT = "ResidentBlackberry42"

# --- Helper Functions ---

def setup_driver():
    """Sets up the Selenium WebDriver for Chrome."""
    print("INFO: Setting up Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode for efficiency
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    options.add_argument('log-level=3') # Suppress console noise
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def scroll_element(driver, element, scrolls=5):
    """Scrolls a specific element on the page to load more content."""
    for _ in range(scrolls):
        try:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", element)
            time.sleep(1.2) # Wait for content to load
        except Exception:
            break

def save_to_csv(data, filename):
    """Saves the collected data to a CSV file."""
    if not data:
        print("WARNING: No data was collected. CSV file will not be created.")
        return
    
    df = pd.DataFrame(data)
    # Standardize column order
    columns = [
        'source', 'query', 'location_name', 'review_text', 'review_author', 
        'location_rating', 'location_address', 'url'
    ]
    df = df.reindex(columns=columns)
    
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"\nSUCCESS: Data saved to {filename}. Total records: {len(df)}")


# --- Google Maps Scraper ---

def scrape_gmaps(query, limit):
    """Main function to scrape Google Maps."""
    driver = setup_driver()
    results = []
    
    try:
        print(f"INFO: Searching Google Maps for: '{query}'")
        search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        driver.get(search_url)
        
        wait = WebDriverWait(driver, 10)
        feed_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]')))
        
        print("INFO: Scrolling results to find locations...")
        scroll_element(driver, feed_element, scrolls=(limit // 5) + 2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        location_links = soup.select('a[href^="https://www.google.com/maps/place/"]')
        urls = list(dict.fromkeys([link['href'] for link in location_links if link.get('aria-label')]))
        
        print(f"INFO: Found {len(urls)} unique locations. Scraping top {limit}...")
        
        for url in tqdm(urls[:limit], desc="Scraping G-Maps Locations"):
            location_data = scrape_gmaps_location(driver, url, query)
            if location_data:
                results.extend(location_data)
            time.sleep(1) # Be a good citizen

    except TimeoutException:
        print("ERROR: Could not find results panel. Page might have changed or no results found.")
    finally:
        print("INFO: Closing WebDriver.")
        driver.quit()
        
    return results

def scrape_gmaps_location(driver, url, query):
    """Scrapes reviews from a single Google Maps location page."""
    driver.get(url)
    wait = WebDriverWait(driver, 15)
    
    try:
        title_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'h1')))
        location_name = title_element.text
    except TimeoutException:
        print(f"WARNING: Skipping location due to timeout on title: {url}")
        return []

    # Get basic info
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    address = soup.select_one('button[data-item-id="address"] .Io6YTe')
    rating = soup.select_one('div.F7nice span[aria-hidden="true"]')
    
    # Click the "Reviews" tab
    try:
        reviews_button = driver.find_element(By.XPATH, '//button[contains(@aria-label, "Reviews for") or contains(@aria-label, "reviews")]')
        driver.execute_script("arguments[0].click();", reviews_button)
    except NoSuchElementException:
        # Some places have reviews on the main page, no tab needed.
        pass

    # Wait for reviews panel and scroll it
    try:
        reviews_panel_selector = 'div.m6QErb.DxyBCb.kA9K6e.li8Ydd.dS8AEf'
        reviews_panel = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, reviews_panel_selector)))
        num_scrolls = (GMAPS_REVIEWS_PER_LOCATION // 8) + 1
        scroll_element(driver, reviews_panel, scrolls=num_scrolls)
    except TimeoutException:
        pass # No dedicated review panel, reviews might be on the main page.

    # Parse all loaded reviews
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    review_elements = soup.select('div.jftiEf.fontBodyMedium')
    
    reviews_data = []
    for review_el in review_elements[:GMAPS_REVIEWS_PER_LOCATION]:
        author_el = review_el.select_one('.d4r55')
        text_el = review_el.select_one('.MyEned .wiI7pd')
        
        if author_el and text_el:
            reviews_data.append({
                'source': 'Google Maps',
                'query': query,
                'location_name': location_name,
                'review_text': text_el.text.strip(),
                'review_author': author_el.text.strip(),
                'location_rating': rating.text.strip() if rating else 'N/A',
                'location_address': address.text.strip() if address else 'N/A',
                'url': url
            })
            
    return reviews_data

# --- Reddit Scraper ---

def scrape_reddit(query, limit):
    """Main function to scrape Reddit for opinions."""
    if REDDIT_CLIENT_ID == "YOUR_CLIENT_ID" or REDDIT_CLIENT_SECRET == "YOUR_CLIENT_SECRET":
        print("ERROR: Reddit API credentials are not set. Please edit the script and add them.")
        sys.exit(1)

    print("INFO: Initializing Reddit API (PRAW)...")
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

    # Simple logic to guess a subreddit from the query (e.g., "Cafes in Delhi" -> r/delhi)
    query_parts = query.lower().split(" in ")
    subreddit_name = "all" # Default to searching all of Reddit
    if len(query_parts) > 1:
        subreddit_name = query_parts[-1].replace(" ", "")
    
    print(f"INFO: Searching subreddit 'r/{subreddit_name}' for query: '{query}'")
    
    try:
        subreddit = reddit.subreddit(subreddit_name)
        submissions = list(subreddit.search(query, limit=limit, sort="relevance"))
    except Exception as e:
        print(f"ERROR: Could not access subreddit 'r/{subreddit_name}'. It may not exist. Trying 'r/all'. Error: {e}")
        subreddit = reddit.subreddit("all")
        submissions = list(subreddit.search(query, limit=limit, sort="relevance"))
        
    results = []
    for submission in tqdm(submissions, desc="Scraping Reddit Posts"):
        submission.comments.replace_more(limit=0)  # Remove "load more comments" links
        for comment in submission.comments.list()[:20]: # Get top 20 comments
            if isinstance(comment, praw.models.Comment) and comment.body and comment.author and len(comment.body) > 50:
                results.append({
                    'source': 'Reddit',
                    'query': query,
                    'location_name': submission.title, # Using post title as a proxy for location/topic
                    'review_text': comment.body,
                    'review_author': comment.author.name,
                    'location_rating': f"{submission.score} upvotes",
                    'location_address': f"r/{subreddit_name}", # Subreddit as address
                    'url': f"https://reddit.com{submission.permalink}"
                })
                
    return results

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Vibe Navigator: A multi-platform scraper for location reviews and opinions.")
    parser.add_argument("platform", choices=['gmaps', 'reddit'], help="The platform to scrape from.")
    parser.add_argument("query", type=str, help="The search query, e.g., 'Cafes in Delhi'.")
    parser.add_argument("--limit", type=int, default=10, help="Max number of locations (gmaps) or posts (reddit) to scrape.")
    parser.add_argument("--output", type=str, default=OUTPUT_FILENAME, help="The name of the output CSV file.")
    
    args = parser.parse_args()
    
    print(f"--- Vibe Navigator Scraper ---")
    print(f"Platform: {args.platform}")
    print(f"Query: {args.query}")
    print(f"Limit: {args.limit}")
    print("----------------------------\n")
    
    results = []
    if args.platform == 'gmaps':
        results = scrape_gmaps(args.query, args.limit)
    elif args.platform == 'reddit':
        results = scrape_reddit(args.query, args.limit)
    
    save_to_csv(results, args.output)

if __name__ == '__main__':
    main()