#!/usr/bin/env python3
"""Quick test script for the summarize-text capsule."""

import requests
import json
import sys

# Test text to summarize
test_text = """The precipitous shift toward hybrid and remote work models has catalyzed a fundamental restructuring of the modern urban landscape, a phenomenon often referred to as the "donut effect," where economic activity migrates from dense city centers to suburban peripheries. For decades, the central business district (CBD) served as the undisputed gravitational center of metropolitan economics, supporting a vast ecosystem of transit networks, service hospitality, and retail that relied entirely on the daily influx of commuters. However, as vacancy rates in commercial skyscrapers stabilize at historically high levels, municipal governments face a dual crisis: a plummeting tax base derived from commercial property assessments and the immediate struggle to maintain public infrastructure that was designed for peak-capacity crowds that no longer materialize. This decoupling of "work" from a specific "place" forces a re-evaluation of zoning laws, challenging the rigid separation of residential and commercial sectors that characterized 20th-century urban planning.

    Beyond the immediate fiscal challenges, this transition presents a complex architectural and logistical puzzle regarding the adaptive reuse of obsolete infrastructure. While the popular solution suggests converting empty office towers into residential housing to alleviate housing shortages, the engineering reality is far more prohibitive; deep floor plates, lack of natural light, and centralized plumbing systems make retrofitting modern office buildings financially unviable for many developers without significant government subsidies. Consequently, cities are witnessing a bifurcation in real estate value, where premium, amenity-rich office spaces ("Class A") retain value, while older "Class B" and "Class C" buildings face obsolescence. This physical stagnation threatens to create "zombie towers" that blight skylines, necessitating a pivot toward mixed-use neighborhoods where amenities, housing, and workspaces are integrated into "15-minute cities" rather than segregated districts.

    Ultimately, the long-term societal implications of this decentralized model extend beyond concrete and steel, reshaping the social contract between employers and employees. While the reduction in commuting hours has objectively improved work-life balance and carbon footprints for white-collar workers, it has simultaneously exacerbated inequality for service workers whose jobs are tethered to physical locations that are seeing reduced foot traffic. Furthermore, the erosion of the "water cooler" culture threatens to diminish institutional loyalty and the distinct serendipity of in-person collaboration, forcing organizations to artificially engineer social cohesion through digital channels. Thus, the future city will not be defined by its skyline, but by its ability to pivot from a monolithic engine of production into a decentralized network of lifestyle-focused hubs that prioritize flexibility over density.
"""

def test_summarize_text(text):
    """Test the summarize-text capsule with the given text."""
    url = "http://localhost:8000/execute"
    
    payload = {
        "capsule": "summarize-text",
        "input": {
            "text": text
        }
    }
    
    print("Sending request to orchestrator...")
    print(f"URL: {url}")
    print(f"Text length: {len(text)} characters")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("success"):
            print("✓ SUCCESS!")
            print()
            print("Summary:")
            print("-" * 50)
            print(result["output"]["summary"])
            print("-" * 50)
            if result.get("session_id"):
                print(f"\nSession ID: {result['session_id']}")
        else:
            print("✗ FAILED!")
            print(f"Error: {result.get('error', 'Unknown error')}")
            if result.get("logs"):
                print("\nContainer logs:")
                print(result["logs"])
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print("✗ ERROR: Could not connect to orchestrator.")
        print("Make sure the orchestrator is running on http://localhost:8000")
        print("Run: python -m orchestrator.main")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("✗ ERROR: Request timed out (capsule took too long)")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP ERROR: {e}")
        try:
            error_detail = response.json()
            print(f"Details: {json.dumps(error_detail, indent=2)}")
        except:
            print(f"Response: {response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Use command line argument if provided, otherwise use default test text
    if len(sys.argv) > 1:
        test_text = " ".join(sys.argv[1:])
    
    test_summarize_text(test_text)
