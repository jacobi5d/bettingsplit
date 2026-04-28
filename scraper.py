import os
import json
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Leagues to scrape
LEAGUES = ["NBA", "NFL", "NHL", "MLB", "NCAAF", "NCAAB"]

def determine_suggestion(bet_pct, handle_pct, rlm_detected=False):
    """
    Evaluates splits and Reverse Line Movement (RLM) to generate a betting suggestion.
    """
    try:
        bet_pct = float(str(bet_pct).strip('%'))
        handle_pct = float(str(handle_pct).strip('%'))
    except (ValueError, AttributeError):
        return "Pass"

    differential = handle_pct - bet_pct

    if differential >= 20 and rlm_detected:
        return "🔒"
    elif differential >= 15:
        return "🔥"
    elif differential >= 5:
        return "Play"
    
    return "Pass"

def run_scraper():
    email = os.getenv("ACTION_NETWORK_EMAIL")
    password = os.getenv("ACTION_NETWORK_PASSWORD")

    if not email or not password:
        print("Error: Missing credentials in environment variables.")
        return

    scraped_data = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Set up headless Chrome options for GitHub Actions
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Run in background. Comment this out to watch it run locally.
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15) # Global 15-second wait

    try:
        # --- 1. LOGIN FLOW ---
        print("Navigating to Action Network...")
        driver.get("https://www.actionnetwork.com/")

        print("Opening login modal...")
        login_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".user-component__login")))
        login_btn.click()

        print("Filling credentials...")
        email_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='email']")))
        password_input = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        
        email_input.send_keys(email)
        password_input.send_keys(password)

        submit_btn = driver.find_element(By.CSS_SELECTOR, ".sign-in__submit-button")
        submit_btn.click()

        print("Waiting for login confirmation...")
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".user-button__profile")))
        print("Login successful!")

        # --- 2. SCRAPE DATA ---
        for league in LEAGUES:
            print(f"Gathering data for {league}...")
            driver.get(f"https://www.actionnetwork.com/{league.lower()}/public-betting")
            
            try:
                # Look for either a standard table or Action's custom grid layout
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table, [data-testid='odds-table']")))
            except:
                print(f"No active public betting table found for {league}. Skipping.")
                continue
            
            # Fetch all rows
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            if not rows:
                rows = driver.find_elements(By.CSS_SELECTOR, "[class*='table-row'], [class*='odds-table__row']")

            for row in rows:
                try:
                    # Extracting raw text from the row. 
                    # Note: You may need to tweak these generic selectors using the DOM inspector
                    teams = row.find_elements(By.CSS_SELECTOR, "span.team-name, .team-name-class")
                    if len(teams) < 2:
                        continue 
                        
                    away_team = teams[0].text
                    home_team = teams[1].text
                    matchup = f"{away_team} @ {home_team}"
                    
                    # Generic fallbacks; update with precise classes
                    try:
                        matchup_time = row.find_element(By.CSS_SELECTOR, ".game-time, .time").text
                    except:
                        matchup_time = "TBD"

                    try:
                        line = row.find_element(By.CSS_SELECTOR, ".spread-line, .line").text
                    except:
                        line = "N/A"

                    # Placeholder percentage extraction - update with exact Action Network classes
                    ats_bet_away, ats_bet_home = "30%", "70%"
                    ats_handle_away, ats_handle_home = "55%", "45%"
                    
                    tot_bet_over, tot_bet_under = "60%", "40%"
                    tot_handle_over, tot_handle_under = "40%", "60%"
                    
                    sharp_bet = "Away ATS"
                    expert_pick = "Home ML"
                    injuries = "None"

                    # Logic
                    ats_sugg = determine_suggestion(ats_bet_away, ats_handle_away)
                    tot_sugg = determine_suggestion(tot_bet_under, tot_handle_under)

                    scraped_data.append({
                        "League": league,
                        "Matchup": matchup,
                        "Time": matchup_time,
                        "Line": line,
                        "ATS %bet(away/home)": f"{ats_bet_away} / {ats_bet_home}",
                        "ATS %handle(away/home)": f"{ats_handle_away} / {ats_handle_home}",
                        "TOTAL %bet(over/under)": f"{tot_bet_over} / {tot_bet_under}",
                        "TOTAL %handle(over/under)": f"{tot_handle_over} / {tot_handle_under}",
                        "Sharp Bet": sharp_bet,
                        "Expert Pick": expert_pick,
                        "Injuries": injuries,
                        "Suggestion Bet": f"ATS: {ats_sugg} | TOT: {tot_sugg}",
                        "Timestamp": timestamp
                    })
                except Exception as e:
                    print(f"Skipping a row due to parsing error: {e}")

    except Exception as e:
        print(f"Critical error: {e}")
    finally:
        driver.quit()

    # --- 3. EXPORT TO JSON AND CSV ---
    os.makedirs("data", exist_ok=True)
    
    print("Saving data to JSON...")
    with open("data/splits.json", "w") as f:
        json.dump(scraped_data, f, indent=4)

    print("Saving data to CSV...")
    if scraped_data:
        keys = scraped_data[0].keys()
        with open("data/betting_splits.csv", "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(scraped_data)
        print("Data successfully saved.")
    else:
        print("No data was scraped.")

if __name__ == "__main__":
    run_scraper()
