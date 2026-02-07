#!/usr/bin/env python3
"""Test script for a simple workflow that uses web-context to identify the best 3D modeling program 
for 3D printing, then uses find-download-link to find its download link."""

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
        response = requests.post(url, json=payload, timeout=600)  # Longer timeout for workflow
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
        print("✗ ERROR: Request timed out (workflow took too long)")
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


def test_3d_modeling_workflow():
    """Test workflow: Identify best 3D modeling program for 3D printing, then find download link."""
    
    # Define the workflow
    workflow = {
        "name": "find-3d-modeling-program",
        "description": "Identify the best 3D modeling program for 3D printing and find its download link",
        "steps": [
            {
                "capsule": "web-context",
                "translator": None,
                "translator_instructions": None
            },
            {
                "capsule": "find-download-link",
                "translator": "translator",
                "translator_instructions": {
                    "target_capsule": "find-download-link",
                    "mapping": {
                        "query": "final_summary"
                    },
                    "instructions": "Extract the name of the best 3D modeling program for 3D printing from the final_summary. Create a query string that includes the program name and indicates we want to find the download link for it. For example, if the summary mentions 'Blender' or 'Fusion 360', create a query like 'download Blender' or 'download Fusion 360'."
                }
            }
        ]
    }
    
    # Create payload for workflow capsule
    payload = {
        "capsule": "workflow",
        "input": {
            "workflow": json.dumps(workflow),
            "initial_input": {
                "research_goal": "What is the best program to 3D model stuff for 3D printing?"
            }
        }
    }
    
    result = send_request(payload, "3D Modeling Program Research and Download Link Workflow")
    
    if result:
        output = result["output"]
        print("Workflow Result:")
        print("-" * 70)
        
        # Display workflow execution summary
        if output.get("success"):
            print(f"✓ Workflow completed successfully")
            print(f"Steps executed: {output.get('steps_executed', 0)}")
        else:
            print(f"✗ Workflow failed: {output.get('error', 'Unknown error')}")
        
        # Display step results
        if output.get("step_results"):
            print("\nStep Results:")
            print("-" * 70)
            for step_result in output["step_results"]:
                step_index = step_result.get("step_index", -1)
                capsule = step_result.get("capsule", "unknown")
                success = step_result.get("success", False)
                
                print(f"\nStep {step_index + 1}: {capsule}")
                print(f"  Status: {'✓ Success' if success else '✗ Failed'}")
                
                if step_result.get("error"):
                    print(f"  Error: {step_result['error']}")
                
                if success and step_result.get("output"):
                    step_output = step_result["output"]
                    
                    if capsule == "web-context":
                        if step_output.get("final_summary"):
                            summary = step_output["final_summary"]
                            # Truncate if too long
                            if len(summary) > 500:
                                print(f"  Summary (truncated): {summary[:500]}...")
                            else:
                                print(f"  Summary: {summary}")
                        if step_output.get("visited_urls"):
                            print(f"  Visited URLs: {len(step_output['visited_urls'])}")
                    
                    elif capsule == "find-download-link":
                        print(f"  Found: {step_output.get('found', False)}")
                        if step_output.get("url"):
                            print(f"  Download URL: {step_output['url']}")
                        if step_output.get("reasoning"):
                            print(f"  Reasoning: {step_output['reasoning']}")
                        if step_output.get("metadata"):
                            metadata = step_output["metadata"]
                            if metadata.get("file_size_mb"):
                                print(f"  File Size: {metadata['file_size_mb']} MB")
        
        # Display final output
        if output.get("final_output"):
            print("\nFinal Output:")
            print("-" * 70)
            final_output = output["final_output"]
            print(json.dumps(final_output, indent=2))
        
        print("-" * 70)
        if result.get("session_id"):
            print(f"\nSession ID: {result['session_id']}")
        
        return output.get("success", False)
    
    return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("SIMPLE WORKFLOW TEST SUITE")
    print("="*70)
    print("This test creates a workflow that:")
    print("  1. Uses web-context to identify the best 3D modeling program for 3D printing")
    print("  2. Uses find-download-link to find the download link for that program")
    print("="*70)
    
    # Run the test
    passed = test_3d_modeling_workflow()
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    status = "✓ PASSED" if passed else "✗ FAILED"
    print(f"{status}: 3D Modeling Program Research and Download Link Workflow")
    print("="*70)
    
    # Exit with error code if test failed
    if not passed:
        sys.exit(1)
