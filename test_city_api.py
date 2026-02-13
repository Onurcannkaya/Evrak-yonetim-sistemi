import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = "https://kentrehberi.sivas.bel.tr"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://kentrehberi.sivas.bel.tr/"
}

def test_endpoint(path, params=None):
    url = f"{base_url}/{path}"
    print(f"\n--- Testing {url} ---")
    try:
        r = requests.get(url, headers=headers, params=params, verify=False, timeout=10)
        print(f"Status: {r.status_code}")
        try:
            data = r.json()
            if isinstance(data, list):
                print(f"Result type: List (len={len(data)})")
                print("First 3 items:")
                for item in data[:3]:
                    print(json.dumps(item, ensure_ascii=False))
            elif isinstance(data, dict):
                print(f"Result type: Dict (keys={list(data.keys())})")
            else:
                print(f"Result: {str(data)[:200]}")
            return data
        except json.JSONDecodeError:
            print(f"Response not JSON: {r.text[:200]}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# 1. Get Mahalle List
# Correct endpoint from JS analysis: /api/abs/mahalle-listesi
mahalleler = test_endpoint("api/abs/mahalle-listesi")

# 2. Find 'Kandemir' and get its ID
kandemir_id = None
if mahalleler and isinstance(mahalleler, list):
    print(f"Total Neighborhoods: {len(mahalleler)}")
    all_names = []
    for m in mahalleler:
        # JSON keys: no, ad, mahalleAdi, uavtKodu
        name = m.get('ad', '').upper()
        all_names.append(name)
        
        if 'KANDEMİR' in name or 'KANDEMIR' in name:
            print(f"\nFOUND KANDEMİR: {m}")
            # 'no' field seems to be the ID based on "no": "39778"
            kandemir_id = m.get('no')
            break
            
    if not kandemir_id:
        print("ALL NAMES FOUND:")
        print(all_names)

# 3. Test Ada for Kandemir (if ID found)
if kandemir_id:
    # Endpoint: /api/abs/ada-parsel-ara (POST)
    # Payload deduced from JS: {adaNo: t...}
    # Likely: mahalleId, adaNo, parselNo. BUT check if keys match exactly the JS variables or standard naming.
    # JS snippet: body:JSON.stringify({adaNo:t, parselNo:a, mahalleId:r}) (Hypothetical but likely)
    
    url = f"{base_url}/api/abs/ada-parsel-ara"
    
    # Try multiple payload variations if one fails? 
    # Let's start with standard camelCase
    payload = {
        "mahalleId": int(kandemir_id), # Try integer
        "adaNo": 153,
        "parselNo": 93
    }
    
    print(f"\n--- Testing POST {url} ---")
    print(f"Payload: {json.dumps(payload)}")
    
    try:
        r = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
        print(f"Status: {r.status_code}")
        try:
            print(r.json())
        except:
            print(r.text[:500])
            
        # If 400/500, try sending ID as string
        if r.status_code != 200:
             print("\nRetrying with ID as string...")
             payload["mahalleId"] = str(kandemir_id)
             r = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
             print(f"Status: {r.status_code}")
             print(r.text[:500])

    except Exception as e:
        print(f"Error: {e}")
else:
    print("\nKandemir not found in API. Testing Ada/Parsel search without neighborhood filter...")
    
    # Test if API accepts search without mahalleId
    url = f"{base_url}/api/abs/ada-parsel-ara"
    
    # Try with just Ada and Parsel
    payload = {
        "adaNo": 153,
        "parselNo": 93
    }
    
    print(f"\n--- Testing POST {url} (No Mahalle) ---")
    print(f"Payload: {json.dumps(payload)}")
    
    try:
        r = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
        print(f"Status: {r.status_code}")
        try:
            result = r.json()
            print("Response:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except:
            print(r.text[:500])
    except Exception as e:
        print(f"Error: {e}")
