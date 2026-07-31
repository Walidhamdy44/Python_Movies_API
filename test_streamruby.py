"""Test with longer wait and interaction."""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import re

options = Options()
options.add_argument('--headless=new')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option('excludeSwitches', ['enable-automation'])
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')

driver = webdriver.Chrome(options=options)

# Remove webdriver flag
driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
    'source': '''
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = {runtime: {}};
    '''
})

try:
    url = "https://audinifer.com/f/4seb5wokb9jv_h"
    print(f"Loading: {url}")
    driver.get(url)
    
    # Wait longer
    print("Waiting 10 seconds...")
    time.sleep(10)
    
    # Scroll
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    
    html = driver.page_source
    
    # Search for CDN links
    patterns = [
        r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+',
        r'https?://[^"\'<>\s]+\.mp4\?[^"\'<>\s]+',
    ]
    
    print("\n=== Searching for CDN links ===")
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            print(f"  ✓ {m[:100]}")
    
    # Check for btn-gr with href
    soup = BeautifulSoup(html, 'html.parser')
    print("\n=== Download buttons ===")
    for a in soup.find_all('a', class_=re.compile('btn')):
        href = a.get('href', '')
        classes = ' '.join(a.get('class', []))
        if href and not href.startswith('#') and not href.startswith('javascript'):
            print(f"  {classes}: {href[:80]}")
    
    # Try clicking any visible download button
    print("\n=== Trying to click download ===")
    try:
        btns = driver.find_elements(By.CSS_SELECTOR, 'a.btn-gr, a.submit-btn, button.g-recaptcha')
        for btn in btns:
            if btn.is_displayed():
                href = btn.get_attribute('href')
                print(f"  Found button: {href[:80] if href else 'no href'}")
                
                if href and 'premilkyway' in href:
                    print(f"\n✓✓✓ DIRECT LINK: {href}")
                    break
    except Exception as e:
        print(f"  Error: {e}")

finally:
    driver.quit()
