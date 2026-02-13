import requests
from bs4 import BeautifulSoup
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://kentrehberi.sivas.bel.tr/"

print(f"Analyzing {url}...")

try:
    # 1. Main Page Fetch
    response = requests.get(url, verify=False, timeout=15) # Verify=False in case of SSL issues in this env
    print(f"Status Code: {response.status_code}")
    print(f"Server Header: {response.headers.get('Server', 'Unknown')}")
    print(f"X-Powered-By: {response.headers.get('X-Powered-By', 'Unknown')}")
    
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    
    # 2. Tech Stack Detection
    keywords = {
        "Netcad": ["netcad", "keos", "belnet"],
        "ESRI": ["arcgis", "esri", "mapserver"],
        "CitySurfer": ["citysurfer"],
        "MapInfo": ["mapinfo"],
        "General Map": ["leaflet", "openlayers", "mapbox"]
    }
    
    print("\n--- Technology Detection ---")
    detected = []
    
    # Check Title
    if soup.title:
        print(f"Page Title: {soup.title.string.strip()}")
        
    # Check Scripts and Links
    scripts = [s.get('src') for s in soup.find_all('script') if s.get('src')]
        
    display_scripts = scripts[:10] # Show first 10
    print(f"Scripts found: {len(scripts)}")
    for src in display_scripts:
        print(f" - {src}")
        
    # Analyze kentrehberi.js specifically
    js_url = "https://kentrehberi.sivas.bel.tr/js/kentrehberi.js"
    print(f"\nFetching JS: {js_url}")
    try:
        r_js = requests.get(js_url, verify=False, timeout=10)
        js_content = r_js.text
        print(f"JS Length: {len(js_content)} chars")
        
        # Search for interesting strings in JS
        js_patterns = [
            r"api/[a-zA-Z0-9_/]+",
            r"/[a-zA-Z0-9_/]+\.ashx",
            r"/[a-zA-Z0-9_/]+\.svc",
            r"url\s*:\s*['\"]([^'\"]+)['\"]",
            r"layers\s*:",
            r"arcgis", r"netcad", r"geoserver"
        ]
        
        print("\n--- JS Analysis ---")
        for pattern in js_patterns:
            # Find all matches with context
            for match in re.finditer(pattern, js_content, re.IGNORECASE):
                start = max(0, match.start() - 50)
                end = min(len(js_content), match.end() + 100)
                context = js_content[start:end]
                print(f"Match '{match.group()}': ...{context}...")
    except Exception as e:
        print(f"JS Fetch Error: {e}")

except Exception as e:
    print(f"Error: {e}")
