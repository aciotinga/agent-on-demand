#!/usr/bin/env python3
"""Test script for DDGS metasearch functionality."""

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException
import json
import sys


def search_duckduckgo(query, max_results=5):
    """Search using DDGS metasearch for a specific query."""
    print(f"\n{'='*70}")
    print(f"DDGS METASEARCH TEST")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Max Results: {max_results}")
    print()
    
    try:
        # Perform the search using DDGS metasearch
        results = DDGS().text(
            query=query,
            max_results=max_results,
            region='us-en',
            safesearch='moderate',
            backend='auto'
        )
        
        if not results:
            print("No results found.")
            return None
        
        print(f"✓ SUCCESS! Found {len(results)} result(s)")
        print()
        print("Results:")
        print("-" * 70)
        
        # Display results
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  URL: {result.get('href', 'N/A')}")
            print(f"  Snippet: {result.get('body', 'N/A')[:200]}...")
            print()
        
        print("-" * 70)
        
        # Optionally return results as JSON
        return results
        
    except RatelimitException as e:
        print(f"✗ ERROR: Rate limit exceeded: {e}")
        return None
    except TimeoutException as e:
        print(f"✗ ERROR: Request timed out: {e}")
        return None
    except DDGSException as e:
        print(f"✗ ERROR: DDGS search error: {e}")
        return None
    except Exception as e:
        print(f"✗ ERROR: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main test function."""
    # Default test query
    test_query = "python programming"
    
    # Allow command-line argument for custom query
    if len(sys.argv) > 1:
        test_query = " ".join(sys.argv[1:])
    
    print("\n" + "="*70)
    print("DDGS METASEARCH TEST SCRIPT")
    print("="*70)
    print(f"\nUsage: python test_duckduckgo.py [query]")
    print(f"Default query: '{test_query}'")
    
    # Run the search
    results = search_duckduckgo(test_query, max_results=5)
    
    if results:
        print("\n✓ Test completed successfully!")
        # Optionally save results to JSON
        # with open("duckduckgo_results.json", "w", encoding="utf-8") as f:
        #     json.dump(results, f, indent=2, ensure_ascii=False)
        # print("Results saved to duckduckgo_results.json")
        return 0
    else:
        print("\n✗ Test failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
