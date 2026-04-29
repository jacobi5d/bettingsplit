import json
import time
import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configuration
TARGET_URL = "https://www.actionnetwork.com/sharp-report"
COOKIE_FILE = "cookies.json"

def load_cookies(driver, filepath):
    """Loads cookies from a JSON file and adds them to the Selenium driver."""
    try:
        with open(filepath, "r") as file:
            cookies = json.load(file)
            for cookie in cookies:
                # Selenium requires the domain to match before setting cookies
                if 'domain' in cookie:
                    cookie['domain'] = cookie['domain'].replace('^\.', '.')
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    pass
        print("[+] Cookies injected successfully.")
        return True
    except FileNotFoundError:
        print(f"[-] Critical Error: {COOKIE_FILE} not found. Please export your session cookies.")
        return False

def init_driver():
    """Initializes the undetected Chrome driver."""
    options = uc.ChromeOptions()
    # options.add_argument('--headless') # Keep commented out while testing
    options.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=options)
    return driver

def scrape_sharp_report():
    driver = init_driver()
    
    # 1. Navigate to base domain first to set cookies
    print("[*] Navigating to base domain...")
    driver.get("https://www.actionnetwork.com")
    time.sleep(2)
    
    # 2. Inject Cookies to bypass login
    if not load_cookies(driver, COOKIE_FILE):
        driver.quit()
        return

    # 3. Navigate to the actual Sharp Report page
    print("[*] Navigating to the Sharp Report...")
    driver.get(TARGET_URL)
    
    try:
        # Wait for the PRO badge to confirm we are logged in and authorized
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.user-button__product-logo--pro")))
        print("[+] Login confirmed via PRO badge.")
        
        # Wait for the data table to populate
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table[role='table'] tbody tr")))
        print("[+] Data table loaded. Extracting HTML...")
        
    except TimeoutException:
        print("[-] Timeout waiting for page elements. Dumping screenshot for debugging...")
        driver.save_screenshot("timeout_debug.png")
        driver.quit()
        return

    # 4. Parse the HTML with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    # Find all rows in the table body
    rows = soup.select("table[role='table'] tbody tr")
    print(f"[*] Found {len(rows)} data rows. Parsing...")

    scraped_data = []

    for i in range(0, len(rows), 2):
        try:
            # Action Network groups data in blocks. Each game usually spans two rows (Away / Home)
            row_1 = rows[i]
            row_2 = rows[i+1] if (i+1) < len(rows) else None
            
            # Extract Teams
            teams = row_1.select(".game-info__team--desktop span")
            away_team = teams[0].text.strip() if len(teams) > 0 else "Unknown"
            home_team = teams[1].text.strip() if len(teams) > 1 else "Unknown"
            
            # Extract Opening Odds
            open_cells = row_1.select("td:nth-child(2) .sharp-report__open-cell")
            away_open = open_cells[0].text.strip() if len(open_cells) > 0 else ""
            home_open = open_cells[1].text.strip() if len(open_cells) > 1 else ""

            # Extract Current Best Odds
            current_cells = row_1.select("td:nth-child(3) .book-cell__odds span:first-child")
            away_current = current_cells[0].text.strip() if len(current_cells) > 0 else ""
            home_current = current_cells[1].text.strip() if len(current_cells) > 1 else ""

            # Extract % Bets (Column 9)
            bet_percents = row_1.select("td:nth-child(9) .sharp-report__percent div")
            away_bet_pct = bet_percents[0].text.strip() if len(bet_percents) > 0 else ""
            home_bet_pct = bet_percents[1].text.strip() if len(bet_percents) > 1 else ""

            # Extract % Money / Handle (Column 10)
            money_percents = row_1.select("td:nth-child(10) .sharp-report__percent div")
            away_money_pct = money_percents[0].text.strip() if len(money_percents) > 0 else ""
            home_money_pct = money_percents[1].text.strip() if len(money_percents) > 1 else ""

            # Calculate RLM (Reverse Line Movement) if possible
            # Simplified logic: If Money % is heavy one way, but line moves the other way.
            # You can expand this logic based on your specific RLM mathematical needs.
            
            game_data = {
                "Away_Team": away_team,
                "Home_Team": home_team,
                "Away_Open": away_open,
                "Home_Open": home_open,
                "Away_Current": away_current,
                "Home_Current": home_current,
                "Away_Bet_Pct": away_bet_pct,
                "Home_Bet_Pct": home_bet_pct,
                "Away_Handle_Pct": away_money_pct,
                "Home_Handle_Pct": home_money_pct
            }
            
            scraped_data.append(game_data)
        except Exception as e:
            print(f"[-] Error parsing a row block: {e}")
            continue

    # 5. Export the Data
    if scraped_data:
        df = pd.DataFrame(scraped_data)
        
        # Save to CSV
        df.to_csv("betting_splits.csv", index=False)
        
        # Save to JSON 
        with open("betting_splits.json", "w") as f:
            json.dump(scraped_data, f, indent=4)
            
        print(f"[+] Successfully saved {len(scraped_data)} games to JSON and CSV.")
        print(df.head())
    else:
        print("[-] No data was extracted.")

if __name__ == "__main__":
    scrape_sharp_report()
