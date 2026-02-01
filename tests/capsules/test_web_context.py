#!/usr/bin/env python3
"""Test script for the web-context capsule - tests web research functionality."""

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


def test_simple_research():
    """Test 1: Simple research query about Python programming."""
    payload = {
        "capsule": "web-context",
        "input": {
            "research_goal": "Why did silver go down in price so much over the last couple days?"
        }
    }
    
    result = send_request(payload, "Research Python 3.12 Features")
    if result:
        output = result["output"]
        print("Result:")
        print("-" * 70)
        if output.get("final_summary"):
            summary = output["final_summary"]
            # Truncate if too long
            if len(summary) > 500:
                print(f"Final Summary (truncated): {summary[:500]}...")
            else:
                print(f"Final Summary: {summary}")
        if output.get("visited_urls"):
            print(f"\nVisited URLs ({len(output['visited_urls'])}):")
            for i, url in enumerate(output["visited_urls"], 1):
                print(f"  {i}. {url}")
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


def test_research_with_max_steps():
    """Test 2: Research query with limited max_steps."""
    payload = {
        "capsule": "web-context",
        "input": {
            "research_goal": "What is the difference between REST and GraphQL APIs?",
            "max_steps": 5
        }
    }
    
    result = send_request(payload, "Research REST vs GraphQL (limited steps)")
    if result:
        output = result["output"]
        print("Result:")
        print("-" * 70)
        if output.get("final_summary"):
            summary = output["final_summary"]
            # Truncate if too long
            if len(summary) > 500:
                print(f"Final Summary (truncated): {summary[:500]}...")
            else:
                print(f"Final Summary: {summary}")
        if output.get("visited_urls"):
            print(f"\nVisited URLs ({len(output['visited_urls'])}):")
            for i, url in enumerate(output["visited_urls"], 1):
                print(f"  {i}. {url}")
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


def test_technical_research():
    """Test 3: Technical research query about a specific technology."""
    payload = {
        "capsule": "web-context",
        "input": {
            "research_goal": "What are the main advantages of using Docker containers?"
        }
    }
    
    result = send_request(payload, "Research Docker Container Advantages")
    if result:
        output = result["output"]
        print("Result:")
        print("-" * 70)
        if output.get("final_summary"):
            summary = output["final_summary"]
            # Truncate if too long
            if len(summary) > 500:
                print(f"Final Summary (truncated): {summary[:500]}...")
            else:
                print(f"Final Summary: {summary}")
        if output.get("visited_urls"):
            print(f"\nVisited URLs ({len(output['visited_urls'])}):")
            for i, url in enumerate(output["visited_urls"], 1):
                print(f"  {i}. {url}")
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        return True
    return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("WEB-CONTEXT CAPSULE TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run all tests sequentially
    results.append(("Research Python 3.12 Features", test_simple_research()))
    results.append(("Research REST vs GraphQL (limited steps)", test_research_with_max_steps()))
    results.append(("Research Docker Container Advantages", test_technical_research()))
    
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
