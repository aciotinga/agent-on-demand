"""Workflow execution logic for the workflow capsule."""

import json
import os
import sys
import struct
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
import time

# #region agent log
LOG_PATH = Path("/io/debug.log")
def _log(hypothesis_id, location, message, data=None):
    log_entry = {
        "runId": "workflow_debug",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000)
    }
    log_line = json.dumps(log_entry) + "\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(log_line)
    except Exception:
        pass
    # Also log to stderr for container logs
    print(f"[DEBUG] {hypothesis_id}:{location} - {message} | {json.dumps(data)}", file=sys.stderr, flush=True)
# #endregion


def load_workflow(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    """Load workflow definition from JSON string or file.
    
    Args:
        workflow_data: Input data containing either 'workflow' (JSON string) or 'workflow_file' (file path)
        
    Returns:
        Parsed workflow definition dictionary
    """
    if 'workflow' in workflow_data:
        # Workflow is provided as JSON string
        try:
            return json.loads(workflow_data['workflow'])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in workflow field: {e}")
    
    elif 'workflow_file' in workflow_data:
        # Workflow is provided as file path
        workflow_path = Path(workflow_data['workflow_file'])
        
        # Check if it's an absolute path or relative to /io/input
        if not workflow_path.is_absolute():
            workflow_path = Path("/io/input") / workflow_path
        
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")
        
        with open(workflow_path, 'r') as f:
            return json.load(f)
    
    else:
        raise ValueError("Either 'workflow' or 'workflow_file' must be provided")


def validate_workflow(workflow: Dict[str, Any]) -> None:
    """Validate workflow structure.
    
    Args:
        workflow: Workflow definition dictionary
        
    Raises:
        ValueError: If workflow structure is invalid
    """
    if 'steps' not in workflow:
        raise ValueError("Workflow must contain 'steps' array")
    
    if not isinstance(workflow['steps'], list):
        raise ValueError("Workflow 'steps' must be an array")
    
    if len(workflow['steps']) == 0:
        raise ValueError("Workflow must have at least one step")
    
    for i, step in enumerate(workflow['steps']):
        if not isinstance(step, dict):
            raise ValueError(f"Step {i} must be a dictionary")
        
        if 'capsule' not in step:
            raise ValueError(f"Step {i} must have a 'capsule' field")
        
        if not isinstance(step['capsule'], str):
            raise ValueError(f"Step {i} 'capsule' must be a string")
        
        # Validate translator fields if present
        if 'translator' in step and step['translator'] is not None:
            if not isinstance(step['translator'], str):
                raise ValueError(f"Step {i} 'translator' must be a string or null")
            
            if 'translator_instructions' not in step or step['translator_instructions'] is None:
                raise ValueError(f"Step {i} has translator but no translator_instructions")
            
            if not isinstance(step['translator_instructions'], dict):
                raise ValueError(f"Step {i} 'translator_instructions' must be a dictionary")
            
            if 'target_capsule' not in step['translator_instructions']:
                raise ValueError(f"Step {i} translator_instructions must have 'target_capsule' field")


def get_orchestrator_url() -> str:
    """Get orchestrator URL from environment variable.
    
    Returns:
        Orchestrator URL (defaults to http://host.docker.internal:8000)
    """
    # #region agent log
    _log("A", "get_orchestrator_url:entry", "Getting orchestrator URL", {"env_var": os.environ.get('ORCHESTRATOR_URL')})
    # #endregion
    url = os.environ.get('ORCHESTRATOR_URL', 'http://host.docker.internal:8000')
    
    # On Windows Docker Desktop, host.docker.internal should work, but if it doesn't,
    # try using the gateway IP. However, the real issue might be that the orchestrator
    # needs to be accessible. Since other capsules work, the URL should be correct.
    # The timeout might be due to the orchestrator being busy or network latency.
    
    # #region agent log
    _log("A", "get_orchestrator_url:exit", "Orchestrator URL determined", {"url": url})
    # #endregion
    return url


def execute_capsule_via_orchestrator(
    capsule_name: str,
    input_data: Dict[str, Any],
    orchestrator_url: str
) -> Dict[str, Any]:
    """Execute a capsule via the orchestrator HTTP API.
    
    Args:
        capsule_name: Name of the capsule to execute
        input_data: Input data for the capsule
        orchestrator_url: Base URL of the orchestrator
        
    Returns:
        Dictionary with 'success', 'output', 'files', and optionally 'error' keys
    """
    # #region agent log
    _log("B", "execute_capsule_via_orchestrator:entry", "Executing capsule via orchestrator", {"capsule": capsule_name, "orchestrator_url": orchestrator_url})
    # #endregion
    url = f"{orchestrator_url}/execute"
    payload = {
        "capsule": capsule_name,
        "input": input_data
    }
    
    # #region agent log
    _log("B", "execute_capsule_via_orchestrator:before_request", "About to send HTTP POST request", {"url": url, "capsule": capsule_name})
    print(f"[DEBUG] execute_capsule_via_orchestrator: Preparing to call {url} for {capsule_name}", file=sys.stderr, flush=True)
    # #endregion
    
    # Test if we can resolve the hostname
    try:
        import socket
        hostname = url.split("://")[1].split(":")[0].split("/")[0]
        port = int(url.split(":")[2].split("/")[0]) if ":" in url.split("://")[1] else 8000
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:dns_test", "Testing DNS resolution", {"hostname": hostname, "port": port})
        # #endregion
        print(f"[DEBUG] Testing DNS resolution for {hostname}...", file=sys.stderr, flush=True)
        socket.gethostbyname(hostname)
        print(f"[DEBUG] DNS resolution successful for {hostname}", file=sys.stderr, flush=True)
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:dns_success", "DNS resolution successful", {"hostname": hostname})
        # #endregion
    except Exception as e:
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:dns_failed", "DNS resolution failed", {"hostname": hostname, "error": str(e)})
        # #endregion
        print(f"[DEBUG] WARNING: DNS resolution failed for {hostname}: {e}", file=sys.stderr, flush=True)
        # Continue anyway - might still work
    
    try:
        request_start = time.time()
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:request_start", "HTTP request started", {"timestamp": request_start, "url": url, "capsule": capsule_name})
        print(f"[DEBUG] About to make HTTP POST to {url} for capsule {capsule_name}", file=sys.stderr, flush=True)
        # #endregion
        
        # Try with very short timeout first to see if connection can be established
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:before_connect", "About to establish connection", {"url": url})
        print(f"[DEBUG] Establishing connection to {url}...", file=sys.stderr, flush=True)
        # #endregion
        
        try:
            # Use very short connect timeout to fail fast if connection can't be established
            response = requests.post(url, json=payload, timeout=(5, 3600))  # 5s connect, 3600s read
            request_end = time.time()
            # #region agent log
            _log("B", "execute_capsule_via_orchestrator:request_complete", "HTTP request completed", {"duration_seconds": request_end - request_start, "status_code": response.status_code})
            print(f"[DEBUG] HTTP request completed in {request_end - request_start:.2f}s, status={response.status_code}", file=sys.stderr, flush=True)
            # #endregion
            response.raise_for_status()
            result = response.json()
            # #region agent log
            _log("B", "execute_capsule_via_orchestrator:success", "Capsule execution successful", {"capsule": capsule_name, "result_success": result.get("success")})
            # #endregion
            return result
        except requests.exceptions.ConnectTimeout as e:
            # #region agent log
            _log("B", "execute_capsule_via_orchestrator:connect_timeout", "Connection timeout - cannot reach orchestrator", {"error": str(e), "url": url})
            # #endregion
            print(f"[DEBUG] Connection timeout - cannot reach orchestrator at {url}", file=sys.stderr, flush=True)
            raise
    except requests.exceptions.ConnectionError as e:
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:connection_error", "Connection error", {"error": str(e), "url": url})
        # #endregion
        return {
            "success": False,
            "error": f"Failed to execute capsule {capsule_name}: Connection error - {str(e)}"
        }
    except requests.exceptions.Timeout as e:
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:timeout", "Request timeout", {"error": str(e), "url": url})
        # #endregion
        return {
            "success": False,
            "error": f"Failed to execute capsule {capsule_name}: Timeout - {str(e)}"
        }
    except requests.exceptions.RequestException as e:
        # #region agent log
        _log("B", "execute_capsule_via_orchestrator:request_exception", "Request exception", {"error": str(e), "url": url, "error_type": type(e).__name__})
        # #endregion
        return {
            "success": False,
            "error": f"Failed to execute capsule {capsule_name}: {str(e)}"
        }


def execute_translator(
    source_output: Dict[str, Any],
    target_capsule: str,
    translator_name: str,
    translator_instructions: Dict[str, Any],
    orchestrator_url: str
) -> Dict[str, Any]:
    """Execute translator capsule to transform output to input.
    
    Args:
        source_output: Output from previous capsule
        target_capsule: Name of target capsule
        translator_name: Name of translator capsule to use
        translator_instructions: Instructions for translation
        orchestrator_url: Base URL of the orchestrator
        
    Returns:
        Transformed input data for target capsule
    """
    # #region agent log
    _log("D", "execute_translator:entry", "Executing translator", {"translator_name": translator_name, "target_capsule": target_capsule, "orchestrator_url": orchestrator_url})
    # #endregion
    translator_input = {
        "source_output": source_output,
        "target_capsule": target_capsule,
        "mapping": translator_instructions.get('mapping'),
        "instructions": translator_instructions.get('instructions')
    }
    
    # #region agent log
    _log("D", "execute_translator:before_call", "About to call translator capsule", {"translator_name": translator_name})
    # #endregion
    result = execute_capsule_via_orchestrator(
        translator_name,
        translator_input,
        orchestrator_url
    )
    # #region agent log
    _log("D", "execute_translator:after_call", "Translator capsule call completed", {"success": result.get('success'), "has_error": bool(result.get('error'))})
    # #endregion
    
    if not result.get('success'):
        # #region agent log
        _log("D", "execute_translator:failure", "Translator failed", {"error": result.get('error')})
        # #endregion
        raise RuntimeError(f"Translator failed: {result.get('error', 'Unknown error')}")
    
    # #region agent log
    _log("D", "execute_translator:success", "Translator completed successfully", {})
    # #endregion
    return result.get('output', {})


def execute(input_data: dict) -> dict:
    """Execute a workflow defined in the input data.
    
    Args:
        input_data: Dictionary containing:
            - workflow: JSON string of workflow definition, OR
            - workflow_file: Path to workflow JSON file
            - initial_input: Initial input for the first capsule
            
    Returns:
        Dictionary with execution results including:
            - success: Boolean indicating if workflow completed successfully
            - final_output: Output from the last capsule
            - steps_executed: Number of steps executed
            - error: Error message if execution failed
            - step_results: Array of results for each step
    """
    # #region agent log
    _log("C", "execute:entry", "Workflow execution started", {"has_workflow": "workflow" in input_data, "has_workflow_file": "workflow_file" in input_data})
    # #endregion
    try:
        # Load and validate workflow
        # #region agent log
        _log("C", "execute:before_load", "About to load workflow", {})
        # #endregion
        workflow = load_workflow(input_data)
        # #region agent log
        _log("C", "execute:after_load", "Workflow loaded", {"num_steps": len(workflow.get("steps", []))})
        # #endregion
        validate_workflow(workflow)
        # #region agent log
        _log("C", "execute:after_validate", "Workflow validated", {})
        # #endregion
        
        # Get initial input
        initial_input = input_data.get('initial_input', {})
        
        # Get orchestrator URL
        orchestrator_url = get_orchestrator_url()
        # #region agent log
        _log("A", "execute:orchestrator_url", "Orchestrator URL obtained", {"url": orchestrator_url})
        # #endregion
        
        # Test connectivity to orchestrator using socket first (faster failure)
        # #region agent log
        _log("A", "execute:connectivity_test", "Testing connectivity to orchestrator", {"url": orchestrator_url})
        # #endregion
        test_url = f"{orchestrator_url}/health"
        connectivity_ok = False
        alternative_urls = []
        
        # First, try socket connection test (faster than HTTP)
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(orchestrator_url)
            host = parsed.hostname
            port = parsed.port or 8000
            # #region agent log
            _log("A", "execute:socket_test", "Testing socket connection", {"host": host, "port": port})
            # #endregion
            print(f"[DEBUG] Testing socket connection to {host}:{port}...", file=sys.stderr, flush=True)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                print(f"[DEBUG] Socket connection successful to {host}:{port}", file=sys.stderr, flush=True)
                # #region agent log
                _log("A", "execute:socket_success", "Socket connection successful", {"host": host, "port": port})
                # #endregion
                # Socket works, now try HTTP
                try:
                    test_start = time.time()
                    test_response = requests.get(test_url, timeout=5)
                    test_end = time.time()
                    if test_response.status_code == 200:
                        # #region agent log
                        _log("A", "execute:connectivity_success", "Connectivity test successful", {"url": test_url, "status_code": test_response.status_code, "duration_seconds": test_end - test_start})
                        # #endregion
                        connectivity_ok = True
                except requests.exceptions.RequestException as e:
                    # #region agent log
                    _log("A", "execute:http_failed", "HTTP request failed even though socket works", {"error": str(e)})
                    # #endregion
                    print(f"[DEBUG] Socket works but HTTP failed: {e}", file=sys.stderr, flush=True)
            else:
                print(f"[DEBUG] Socket connection failed to {host}:{port}, error code: {result}", file=sys.stderr, flush=True)
                # #region agent log
                _log("A", "execute:socket_failed", "Socket connection failed", {"host": host, "port": port, "error_code": result})
                # #endregion
        except Exception as e:
            # #region agent log
            _log("A", "execute:socket_test_exception", "Socket test exception", {"error": str(e)})
            # #endregion
            print(f"[DEBUG] Socket test exception: {e}", file=sys.stderr, flush=True)
        
        # If socket test didn't work, try HTTP directly (might work if socket test had issues)
        if not connectivity_ok:
            try:
                test_start = time.time()
                test_response = requests.get(test_url, timeout=5)
                test_end = time.time()
                if test_response.status_code == 200:
                    # #region agent log
                    _log("A", "execute:connectivity_success", "Connectivity test successful", {"url": test_url, "status_code": test_response.status_code, "duration_seconds": test_end - test_start})
                    # #endregion
                    connectivity_ok = True
            except requests.exceptions.RequestException as e:
                # #region agent log
                _log("A", "execute:http_fallback_failed", "HTTP fallback also failed", {"url": test_url, "error": str(e), "error_type": type(e).__name__})
                # #endregion
                print(f"[DEBUG] HTTP fallback also failed: {e}", file=sys.stderr, flush=True)
        
        if not connectivity_ok:
            # #region agent log
            _log("A", "execute:connectivity_all_failed", "All connectivity attempts failed", {"primary_url": orchestrator_url, "alternatives_tried": alternative_urls})
            # #endregion
            error_msg = (
                f"CRITICAL: Cannot reach orchestrator at {orchestrator_url}. "
                f"The workflow capsule cannot make HTTP requests to execute other capsules. "
                f"This is likely a network configuration issue. "
                f"On Windows Docker Desktop, 'host.docker.internal' should work, but it appears to be unreachable. "
                f"Possible solutions: "
                f"1. Check Windows Firewall settings "
                f"2. Verify Docker Desktop network configuration "
                f"3. Try using the host's actual IP address instead of host.docker.internal"
            )
            print(error_msg, file=sys.stderr, flush=True)
            # Return error immediately instead of continuing
            return {
                "success": False,
                "final_output": {},
                "steps_executed": 0,
                "error": f"Cannot reach orchestrator at {orchestrator_url}. Network connectivity issue - the workflow capsule cannot make HTTP requests to execute other capsules.",
                "step_results": []
            }
        
        # Execute steps sequentially
        step_results: List[Dict[str, Any]] = []
        current_output = initial_input
        
        print(f"[DEBUG] Starting workflow execution with {len(workflow['steps'])} steps", file=sys.stderr, flush=True)
        # #region agent log
        _log("C", "execute:before_steps", "About to execute workflow steps", {"num_steps": len(workflow['steps']), "orchestrator_url": orchestrator_url})
        # #endregion
        
        for step_index, step in enumerate(workflow['steps']):
            # #region agent log
            _log("C", "execute:step_start", "Starting workflow step", {"step_index": step_index, "capsule": step.get("capsule")})
            # #endregion
            print(f"[DEBUG] Step {step_index + 1}/{len(workflow['steps'])}: {step.get('capsule')}", file=sys.stderr, flush=True)
            capsule_name = step['capsule']
            translator = step.get('translator')
            translator_instructions = step.get('translator_instructions')
            
            step_result = {
                "step_index": step_index,
                "capsule": capsule_name,
                "success": False
            }
            
            try:
                # Apply translation if needed
                if translator and translator_instructions:
                    # #region agent log
                    _log("C", "execute:before_translator", "About to execute translator", {"step_index": step_index, "translator": translator, "target_capsule": translator_instructions.get('target_capsule')})
                    # #endregion
                    print(f"[DEBUG] Executing translator before step {step_index + 1}", file=sys.stderr, flush=True)
                    # Get target capsule name from translator instructions
                    target_capsule = translator_instructions.get('target_capsule', capsule_name)
                    
                    # Execute translator
                    current_output = execute_translator(
                        current_output,
                        target_capsule,
                        translator,
                        translator_instructions,
                        orchestrator_url
                    )
                    # #region agent log
                    _log("C", "execute:after_translator", "Translator completed", {"step_index": step_index})
                    # #endregion
                    print(f"[DEBUG] Translator completed for step {step_index + 1}", file=sys.stderr, flush=True)
                
                # Execute the capsule
                # #region agent log
                _log("C", "execute:before_capsule", "About to execute capsule", {"step_index": step_index, "capsule": capsule_name})
                # #endregion
                print(f"[DEBUG] Executing capsule: {capsule_name}", file=sys.stderr, flush=True)
                result = execute_capsule_via_orchestrator(
                    capsule_name,
                    current_output,
                    orchestrator_url
                )
                # #region agent log
                _log("C", "execute:after_capsule", "Capsule execution completed", {"step_index": step_index, "capsule": capsule_name, "success": result.get("success")})
                # #endregion
                print(f"[DEBUG] Capsule {capsule_name} completed, success={result.get('success')}", file=sys.stderr, flush=True)
                
                if not result.get('success'):
                    step_result['error'] = result.get('error', 'Unknown error')
                    step_results.append(step_result)
                    return {
                        "success": False,
                        "final_output": {},
                        "steps_executed": step_index + 1,
                        "error": f"Step {step_index} ({capsule_name}) failed: {result.get('error')}",
                        "step_results": step_results
                    }
                
                # Update current output for next step
                current_output = result.get('output') or {}
                step_result['success'] = True
                step_result['output'] = current_output
                
            except Exception as e:
                # #region agent log
                _log("C", "execute:step_exception", "Exception in step execution", {"step_index": step_index, "error": str(e), "error_type": type(e).__name__})
                # #endregion
                step_result['error'] = str(e)
                step_results.append(step_result)
                return {
                    "success": False,
                    "final_output": {},
                    "steps_executed": step_index + 1,
                    "error": f"Step {step_index} ({capsule_name}) failed: {str(e)}",
                    "step_results": step_results
                }
            
            step_results.append(step_result)
            # #region agent log
            _log("C", "execute:step_complete", "Step completed", {"step_index": step_index, "total_steps": len(workflow['steps'])})
            # #endregion
        
        # Workflow completed successfully
        # #region agent log
        _log("C", "execute:success", "Workflow completed successfully", {"total_steps": len(workflow['steps'])})
        # #endregion
        
        # Build return value - only include error if it's not None
        return {
            "success": True,
            "final_output": current_output,
            "steps_executed": len(workflow['steps']),
            "step_results": step_results
        }
        
    except Exception as e:
        # #region agent log
        _log("C", "execute:top_level_exception", "Top-level exception in workflow execution", {"error": str(e), "error_type": type(e).__name__})
        # #endregion
        return {
            "success": False,
            "final_output": {},
            "steps_executed": 0,
            "error": str(e),
            "step_results": []
        }
