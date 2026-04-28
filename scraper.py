import os
import csv
import time
from playwright.sync_api import sync_playwright

# Retrieve credentials from GitHub Secrets (passed as environment variables)
EMAIL = os.environ.get("ACTION_NETWORK_EMAIL")
PASSWORD = os.environ.get("ACTION_NETWORK_PASSWORD")

SPORTS = ["nba", "nhl", "mlb"]

def run():
    with sync_playwright() as p:
        # Launch browser in headless mode (required for GitHub Actions)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # --- STEP 1: LOGIN ---
        print("Navigating to login page...")
        page.goto("https://www.actionnetwork.com/login")
        
        # NOTE: You must update these selectors based on the actual live website
        page.fill("input[type='email']", EMAIL)
        page.fill("input[type='password']", PASSWORD)
        page.click("button[type='submit']")
        
        print("Waiting for login to complete...")
        # Wait for an element that only appears after logging in, or wait for network idle
        page.wait_for_load_state("domcontentloaded")
        time.sleep(3) # Extra buffer for Pro authorization to load

        all_data = []

        # --- STEP 2: SCRAPE EACH SPORT ---
        for sport in SPORTS:
            print(f"Scraping data for {sport.upper()}...")
            # Navigate to the specific sport's pro/public betting splits page
            page.goto(f"https://www.actionnetwork.com/{sport}/public-betting")
            page.wait_for_load_state("networkidle")
            time.sleep(2) # Allow data tables to populate

            # Extract rows from the betting table
            # Update the selector '.betting-table-row' to match Action Network's actual CSS classes
            rows = page.query_selector_all(".betting-table-row")
            
            for row in rows:
                try:
                    # These are placeholder selectors. You will need to inspect the webpage 
                    # and replace these with the actual classes (e.g., '.team-name', '.handle-pct')
                    matchup = row.query_selector(".matchup-class").inner_text() if row.query_selector(".matchup-class") else "Unknown"
                    
                    # Collecting the metrics based on your custom preferences
                    pct_bets_ats = row.query_selector(".bets-ats-class").inner_text() if row.query_selector(".bets-ats-class") else "N/A"
                    pct_handle_ats = row.query_selector(".handle-ats-class").inner_text() if row.query_selector(".handle-ats-class") else "N/A"
                    
                    pct_bets_total = row.query_selector(".bets-total-class").inner_text() if row.query_selector(".bets-total-class") else "N/A"
                    pct_handle_total = row.query_selector(".handle-total-class").inner_text() if row.query_selector(".handle-total-class") else "N/A"
                    
                    line_movement = row.query_selector(".line-movement-class").inner_text() if row.query_selector(".line-movement-class") else "N/A"
                    
                    # Logic for RLM (Reverse Line Movement) and Suggestions (Lock/Fire/Pass)
                    # This would typically be calculated based on comparing handle vs line movement
                    rlm = "Yes" if ("specific rlm indicator" in page.content()) else "No"
                    
                    suggestion = "PASS"
                    rationale = "Default"
                    
                    # Example logic for applying your lock/fire symbols
                    if int(pct_handle_ats.strip('%') or 0) > 80 and int(pct_bets_ats.strip('%') or 0) < 40:
                        suggestion = "🔒 LOCK"
                        rationale = "Sharp money heavy on ATS with low public bet % (RLM indicator)"
                    elif int(pct_handle_ats.strip('%') or 0) > 70:
                        suggestion = "🔥 FIRE"
                        rationale = "Strong sharp handle"
                        
                    all_data.append({
                        "Sport": sport.upper(),
                        "Matchup": matchup,
                        "% Bets ATS": pct_bets_ats,
                        "% Handle ATS": pct_handle_ats,
                        "% Bets Total": pct_bets_total,
                        "% Handle Total": pct_handle_total,
                        "Line Movement": line_movement,
                        "RLM": rlm,
                        "Suggestion": suggestion,
                        "Rationale": rationale
                    })
                except Exception as e:
                    print(f"Error parsing a row in {sport}: {e}")

        # --- STEP 3: SAVE TO CSV ---
        print("Saving data to CSV...")
        keys = all_data[0].keys() if all_data else ["Sport", "Matchup", "% Bets ATS", "% Handle ATS", "% Bets Total", "% Handle Total", "Line Movement", "RLM", "Suggestion", "Rationale"]
        
        with open('betting_splits.csv', 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(all_data)
            
        print("Scraping completed successfully!")
        browser.close()

if __name__ == "__main__":
    if not EMAIL or not PASSWORD:
        print("ERROR: Credentials not found. Please set GitHub Secrets.")
    else:
        run()
