"""Test free reCAPTCHA bypass using DrissionPage."""
from DrissionPage import ChromiumPage, ChromiumOptions
import time
import re

# Based on https://github.com/sarperavci/GoogleRecaptchaBypass

def solve_recaptcha(page):
    """Try to solve reCAPTCHA by clicking checkbox."""
    try:
        # Find reCAPTCHA iframe
        iframe = page.ele('xpath://iframe[contains(@src, "recaptcha") and contains(@src, "anchor")]', timeout=5)
        if not iframe:
            print("No reCAPTCHA iframe found")
            return False
        
        # Switch to iframe and click checkbox
        iframe_page = page.get_frame(iframe)
        checkbox = iframe_page.ele('#recaptcha-anchor', timeout=5)
        if checkbox:
            checkbox.click()
            time.sleep(3)
            
            # Check if solved
            if 'recaptcha-checkbox-checked' in (checkbox.attr('class') or ''):
                print("✓ reCAPTCHA solved!")
                return True
        
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

# Setup
co = ChromiumOptions()
co.headless(True)
co.set_argument('--no-sandbox')
co.set_argument('--disable-dev-shm-usage')

page = ChromiumPage(co)

try:
    url = "https://audinifer.com/f/4seb5wokb9jv_h"
    print(f"Loading: {url}")
    page.get(url)
    time.sleep(3)
    
    print(f"Title: {page.title}")
    
    # Try to solve captcha
    print("\nAttempting to solve reCAPTCHA...")
    if solve_recaptcha(page):
        time.sleep(3)
        
        # Look for download link
        html = page.html
        matches = re.findall(r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*', html)
        if matches:
            print(f"\n✓ DIRECT LINK: {matches[0][:100]}")
        else:
            print("No direct link found after solving captcha")
    else:
        print("Could not solve captcha automatically")

finally:
    page.quit()
