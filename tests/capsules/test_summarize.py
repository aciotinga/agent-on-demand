#!/usr/bin/env python3
"""Test script for the summarize-text capsule - tests all four input modes."""

import requests
import json
import sys
from pathlib import Path

# Test text to summarize
test_text = """The precipitous shift toward hybrid and remote work models has catalyzed a fundamental restructuring of the modern urban landscape, a phenomenon often referred to as the "donut effect," where economic activity migrates from dense city centers to suburban peripheries. For decades, the central business district (CBD) served as the undisputed gravitational center of metropolitan economics, supporting a vast ecosystem of transit networks, service hospitality, and retail that relied entirely on the daily influx of commuters. However, as vacancy rates in commercial skyscrapers stabilize at historically high levels, municipal governments face a dual crisis: a plummeting tax base derived from commercial property assessments and the immediate struggle to maintain public infrastructure that was designed for peak-capacity crowds that no longer materialize. This decoupling of "work" from a specific "place" forces a re-evaluation of zoning laws, challenging the rigid separation of residential and commercial sectors that characterized 20th-century urban planning.

    Beyond the immediate fiscal challenges, this transition presents a complex architectural and logistical puzzle regarding the adaptive reuse of obsolete infrastructure. While the popular solution suggests converting empty office towers into residential housing to alleviate housing shortages, the engineering reality is far more prohibitive; deep floor plates, lack of natural light, and centralized plumbing systems make retrofitting modern office buildings financially unviable for many developers without significant government subsidies. Consequently, cities are witnessing a bifurcation in real estate value, where premium, amenity-rich office spaces ("Class A") retain value, while older "Class B" and "Class C" buildings face obsolescence. This physical stagnation threatens to create "zombie towers" that blight skylines, necessitating a pivot toward mixed-use neighborhoods where amenities, housing, and workspaces are integrated into "15-minute cities" rather than segregated districts.

    Ultimately, the long-term societal implications of this decentralized model extend beyond concrete and steel, reshaping the social contract between employers and employees. While the reduction in commuting hours has objectively improved work-life balance and carbon footprints for white-collar workers, it has simultaneously exacerbated inequality for service workers whose jobs are tethered to physical locations that are seeing reduced foot traffic. Furthermore, the erosion of the "water cooler" culture threatens to diminish institutional loyalty and the distinct serendipity of in-person collaboration, forcing organizations to artificially engineer social cohesion through digital channels. Thus, the future city will not be defined by its skyline, but by its ability to pivot from a monolithic engine of production into a decentralized network of lifestyle-focused hubs that prioritize flexibility over density.
"""

# Additional test texts for batch testing
test_text_2 = """Artificial intelligence has revolutionized numerous industries, from healthcare to finance, by enabling machines to process and analyze vast amounts of data at unprecedented speeds. Machine learning algorithms can now identify patterns that would be impossible for humans to detect, leading to breakthroughs in medical diagnosis, fraud detection, and predictive analytics."""
test_text_3 = """Climate change represents one of the most pressing challenges of our time, requiring coordinated global action to reduce greenhouse gas emissions and transition to renewable energy sources. The scientific consensus is clear: human activities are the primary driver of recent climate change, and immediate action is necessary to prevent catastrophic consequences."""


def send_request(payload, test_name):
    """Send a request to the orchestrator and handle the response."""
    url = "http://localhost:8000/execute"
    
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"{'='*70}")
    print(f"Sending request to orchestrator...")
    print(f"URL: {url}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("success"):
            print("✓ SUCCESS!")
            print()
            return result
        else:
            print("✗ FAILED!")
            print(f"Error: {result.get('error', 'Unknown error')}")
            if result.get("logs"):
                print("\nContainer logs:")
                print(result["logs"])
            return None
            
    except requests.exceptions.ConnectionError:
        print("✗ ERROR: Could not connect to orchestrator.")
        print("Make sure the orchestrator is running on http://localhost:8000")
        print("Run: python -m orchestrator.main")
        return None
    except requests.exceptions.Timeout:
        print("✗ ERROR: Request timed out (capsule took too long)")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP ERROR: {e}")
        try:
            error_detail = response.json()
            print(f"Details: {json.dumps(error_detail, indent=2)}")
        except:
            print(f"Response: {response.text}")
        return None
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return None


def test_single_text():
    """Test 1: Single text summary."""
    payload = {
        "capsule": "summarize-text",
        "input": {
            "text": test_text
        }
    }
    
    result = send_request(payload, "Single Text Summary")
    if result:
        print("Summary:")
        print("-" * 70)
        print(result["output"]["summary"])
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


def test_batch_texts():
    """Test 2: Batch text summary."""
    payload = {
        "capsule": "summarize-text",
        "input": {
            "texts": [test_text, test_text_2, test_text_3]
        }
    }
    
    result = send_request(payload, "Batch Text Summary (3 texts)")
    if result:
        summaries = result["output"]["summaries"]
        print(f"Received {len(summaries)} summaries:")
        print()
        for i, summary in enumerate(summaries, 1):
            print(f"Summary {i}:")
            print("-" * 70)
            print(summary)
            print("-" * 70)
            print()
        if result.get("session_id"):
            print(f"Session ID: {result['session_id']}")
        return True
    return False


def test_single_file():
    """Test 3: Single file summary."""
    # Get the workspace root (parent of this script)
    workspace_root = Path(__file__).parent
    readme_path = workspace_root / "README.md"
    
    if not readme_path.exists():
        print(f"✗ ERROR: File not found: {readme_path}")
        return False
    
    payload = {
        "capsule": "summarize-text",
        "input": {
            "file": str(readme_path)
        }
    }
    
    result = send_request(payload, f"Single File Summary ({readme_path.name})")
    if result:
        print("Summary:")
        print("-" * 70)
        print(result["output"]["summary"])
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


def test_batch_files():
    """Test 4: Batch file summary."""
    # Get the workspace root (parent of this script)
    workspace_root = Path(__file__).parent
    orchestrator_path = workspace_root / "ORCHESTRATOR.md"
    handoff_path = workspace_root / "HANDOFF.md"
    
    if not orchestrator_path.exists():
        print(f"✗ ERROR: File not found: {orchestrator_path}")
        return False
    if not handoff_path.exists():
        print(f"✗ ERROR: File not found: {handoff_path}")
        return False
    
    payload = {
        "capsule": "summarize-text",
        "input": {
            "files": [str(orchestrator_path), str(handoff_path)]
        }
    }
    
    file_names = f"{orchestrator_path.name}, {handoff_path.name}"
    result = send_request(payload, f"Batch File Summary ({file_names})")
    if result:
        summaries = result["output"]["summaries"]
        print(f"Received {len(summaries)} summaries:")
        print()
        for i, (file_path, summary) in enumerate(zip([orchestrator_path, handoff_path], summaries), 1):
            print(f"Summary {i} ({file_path.name}):")
            print("-" * 70)
            print(summary)
            print("-" * 70)
            print()
        if result.get("session_id"):
            print(f"Session ID: {result['session_id']}")
        return True
    return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("SUMMARIZE-TEXT CAPSULE TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run all tests sequentially
    results.append(("Single Text Summary", test_single_text()))
    results.append(("Batch Text Summary", test_batch_texts()))
    results.append(("Single File Summary", test_single_file()))
    results.append(("Batch File Summary", test_batch_files()))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print("="*70)
    
    # Exit with error code if any test failed
    if not all(passed for _, passed in results):
        sys.exit(1)
