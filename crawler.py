import requests
from bs4 import BeautifulSoup
import re
import json

class JokeCrawler:
    def __init__(self):
        self.jokes = {}
        self.base_url = "https://benyehuda.org/read/"
        
    def extract_jokes(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        content = soup.find('div', {'class': 'maintext-prose-body'})
        if not content:
            print("Warning: Could not find maintext-prose-body div")
            return
        
        print(f"Found main content div")
        
        # Find all paragraphs
        paragraphs = content.find_all('p')
        print(f"Found {len(paragraphs)} paragraphs")
        
        # Find first joke number to start sequence
        first_number = None
        current_number = None
        current_joke_text = []
        
        for i, p in enumerate(paragraphs):
            text = p.get_text().strip()
            if not text:
                if current_number and current_joke_text:
                    current_joke_text.append("")  # Keep empty lines between paragraphs
                continue
            
            # Check if paragraph starts with a number
            match = re.match(r'^\s*(\d+)\s*(.*)', text)
            if match:
                number = int(match.group(1))
                
                # If this is our first number, store it
                if first_number is None:
                    first_number = number
                    current_number = number
                
                # If this is the next number in sequence
                if number == current_number:
                    # Save previous joke if exists
                    if current_joke_text:
                        self.jokes[str(current_number-1)] = '\n'.join(current_joke_text)
                        current_joke_text = []
                    
                    # Start new joke
                    current_number = number + 1
                    current_joke_text = [match.group(2).strip()]
                    print(f"Found joke {number} in paragraph {i}")
                else:
                    # If not a sequence number, just add to current joke
                    current_joke_text.append(text)
            else:
                # If no number, add to current joke if we have one
                if current_number:
                    current_joke_text.append(text)
        
        # Save last joke
        if current_joke_text:
            self.jokes[str(current_number-1)] = '\n'.join(current_joke_text)

    def crawl_page(self, url):
        try:
            print(f"\nFetching {url}")
            response = requests.get(url)
            if response.status_code == 200:
                print(f"Successfully fetched page, content length: {len(response.text)}")
                self.extract_jokes(response.text)
                print(f"Current total jokes: {len(self.jokes)}")
            else:
                print(f"Failed to fetch {url}: {response.status_code}")
        except Exception as e:
            print(f"Error crawling {url}: {e}")

    def crawl_all_pages(self, page_ids):
        for page_id in page_ids:
            url = f"{self.base_url}{page_id}"
            print(f"\n{'='*50}\nCrawling page {page_id}")
            self.crawl_page(url)

    def save_jokes(self, filename="jokes.json"):
        print(f"\nSaving {len(self.jokes)} jokes to {filename}")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.jokes, f, ensure_ascii=False, indent=2)
        print("Save completed")

# List of page IDs from your links
page_ids = [
    "28896", "8027", "6797", "6273", "6661", "28907", "3710", "3469", 
    "6338", "28919", "31611", "7774", "6468", "5179", "3140", "7255",
    "4137", "3425", "7643", "4587", "2252", "1452", "3749", "3821",
    "3394", "1482", "2388", "153", "38174", "13943", "25845", "4028",
    "2576", "6931", "22424", "3073", "7968", "29114", "29113"
]

# Run the crawler
crawler = JokeCrawler()
crawler.crawl_all_pages(page_ids)
crawler.save_jokes() 