#!/usr/bin/env python3
"""Test script for the find-download-link capsule - tests link retrieval functionality."""

import requests
import json
import sys
from pathlib import Path


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


def test_minecraft_server_jar():
    """Test 1: Find the latest Minecraft server jar."""
    payload = {
        "capsule": "find-download-link",
        "input": {
            "query": "find the latest minecraft server jar",
            "required_extension": ".jar"
        }
    }
    
    result = send_request(payload, "Find Latest Minecraft Server JAR")
    if result:
        output = result["output"]
        print("Result:")
        print("-" * 70)
        print(f"Found: {output.get('found', False)}")
        if output.get("url"):
            print(f"URL: {output['url']}")
        if output.get("metadata"):
            metadata = output["metadata"]
            print(f"Content Type: {metadata.get('content_type', 'N/A')}")
            print(f"File Size: {metadata.get('file_size_mb', 0)} MB")
            print(f"Status Code: {metadata.get('status_code', 'N/A')}")
        if output.get("reasoning"):
            print(f"Reasoning: {output['reasoning']}")
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


def test_minecraft_server_jar_with_domain():
    """Test 2: Find the latest Minecraft server jar with domain hint."""
    payload = {
        "capsule": "find-download-link",
        "input": {
            "query": "find the latest minecraft server jar",
            "required_extension": ".jar",
            "domain_hint": "minecraft.net"
        }
    }
    
    result = send_request(payload, "Find Latest Minecraft Server JAR (with domain hint)")
    if result:
        output = result["output"]
        print("Result:")
        print("-" * 70)
        print(f"Found: {output.get('found', False)}")
        if output.get("url"):
            print(f"URL: {output['url']}")
        if output.get("metadata"):
            metadata = output["metadata"]
            print(f"Content Type: {metadata.get('content_type', 'N/A')}")
            print(f"File Size: {metadata.get('file_size_mb', 0)} MB")
            print(f"Status Code: {metadata.get('status_code', 'N/A')}")
        if output.get("reasoning"):
            print(f"Reasoning: {output['reasoning']}")
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


def test_simple_query():
    """Test 3: Simple query without extension requirement."""
    payload = {
        "capsule": "find-download-link",
        "input": {
            "query": "find the latest minecraft server jar"
        }
    }
    
    result = send_request(payload, "Find Latest Minecraft Server JAR (simple query)")
    if result:
        output = result["output"]
        print("Result:")
        print("-" * 70)
        print(f"Found: {output.get('found', False)}")
        if output.get("url"):
            print(f"URL: {output['url']}")
        if output.get("metadata"):
            metadata = output["metadata"]
            print(f"Content Type: {metadata.get('content_type', 'N/A')}")
            print(f"File Size: {metadata.get('file_size_mb', 0)} MB")
            print(f"Status Code: {metadata.get('status_code', 'N/A')}")
        if output.get("reasoning"):
            print(f"Reasoning: {output['reasoning']}")
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("FIND-DOWNLOAD-LINK CAPSULE TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run all tests sequentially
    results.append(("Find Latest Minecraft Server JAR", test_minecraft_server_jar()))
    results.append(("Find Latest Minecraft Server JAR (with domain hint)", test_minecraft_server_jar_with_domain()))
    results.append(("Find Latest Minecraft Server JAR (simple query)", test_simple_query()))
    
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
