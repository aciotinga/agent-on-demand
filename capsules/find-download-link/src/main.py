"""Main logic for the find-download-link capsule."""

import os
import json
from pathlib import Path
from openai import OpenAI
import yaml
from typing import Dict, List, Any, Optional
from capabilities import search_web, verify_url_headers, extract_page_links


def load_agent_config():
    """Load agent.yaml configuration."""
    config_path = Path(__file__).parent.parent / "agent.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_system_prompt():
    """Load the system prompt from system_prompt.md."""
    prompt_path = Path(__file__).parent / "ai" / "system_prompt.md"
    with open(prompt_path, 'r') as f:
        return f.read()


def load_user_prompt_template():
    """Load the user prompt template from user_prompt.md."""
    template_path = Path(__file__).parent / "ai" / "user_prompt.md"
    with open(template_path, 'r') as f:
        return f.read()


def load_tools():
    """Load tool definitions from tools.yaml."""
    tools_path = Path(__file__).parent.parent / "tools.yaml"
    with open(tools_path, 'r') as f:
        tools = yaml.safe_load(f)
    
    # Convert to OpenAI function calling format
    functions = []
    for tool in tools:
        functions.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        })
    return functions


def format_user_prompt(template: str, query: str, required_extension: Optional[str] = None, domain_hint: Optional[str] = None) -> str:
    """Format the user prompt template with input data."""
    import re
    
    # Replace query variable
    prompt = template.replace("{{query}}", query)
    
    # Handle required_extension conditional
    if required_extension:
        # Extract and replace the conditional block content
        pattern = r'\{%\s*if\s+required_extension\s*%\}(.*?)\{%\s*endif\s*%\}'
        match = re.search(pattern, prompt, flags=re.DOTALL)
        if match:
            content = match.group(1).replace("{{required_extension}}", required_extension)
            prompt = re.sub(pattern, content, prompt, flags=re.DOTALL)
    else:
        # Remove the entire conditional block
        prompt = re.sub(r'\{%\s*if\s+required_extension\s*%\}.*?\{%\s*endif\s*%\}', '', prompt, flags=re.DOTALL)
    
    # Handle domain_hint conditional
    if domain_hint:
        # Extract and replace the conditional block content
        pattern = r'\{%\s*if\s+domain_hint\s*%\}(.*?)\{%\s*endif\s*%\}'
        match = re.search(pattern, prompt, flags=re.DOTALL)
        if match:
            content = match.group(1).replace("{{domain_hint}}", domain_hint)
            prompt = re.sub(pattern, content, prompt, flags=re.DOTALL)
    else:
        # Remove the entire conditional block
        prompt = re.sub(r'\{%\s*if\s+domain_hint\s*%\}.*?\{%\s*endif\s*%\}', '', prompt, flags=re.DOTALL)
    
    return prompt.strip()


def execute_function_call(function_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute a function call requested by the LLM."""
    if function_name == "search_web":
        query = arguments.get("query", "")
        results = search_web(query, max_results=10)
        return json.dumps(results, indent=2)
    
    elif function_name == "verify_url_headers":
        url = arguments.get("url", "")
        result = verify_url_headers(url)
        return json.dumps(result, indent=2)
    
    elif function_name == "extract_page_links":
        url = arguments.get("url", "")
        filter_pattern = arguments.get("filter_pattern")
        results = extract_page_links(url, filter_pattern=filter_pattern)
        return json.dumps(results, indent=2)
    
    elif function_name == "submit_result":
        # This is handled specially in the main loop - just return acknowledgment
        return json.dumps({"status": "received", "message": "Result submitted successfully"})
    
    else:
        return json.dumps({"error": f"Unknown function: {function_name}"})


def validate_url(result: Dict, required_extension: Optional[str] = None, domain_hint: Optional[str] = None) -> bool:
    """Validate if a URL result meets the criteria."""
    if not result.get("valid", False):
        return False
    
    final_url = result.get("final_url", "")
    content_type = result.get("content_type", "")
    
    # Check domain hint if provided
    if domain_hint:
        if domain_hint not in final_url:
            return False
    
    # Check extension if provided
    if required_extension:
        # Check URL extension
        url_has_extension = final_url.lower().endswith(required_extension.lower())
        
        # Check content type (common mappings)
        content_type_matches = False
        extension_lower = required_extension.lower()
        if extension_lower == ".jar":
            content_type_matches = "java-archive" in content_type.lower() or "application/java-archive" in content_type.lower()
        elif extension_lower == ".zip":
            content_type_matches = "zip" in content_type.lower() or "application/zip" in content_type.lower()
        elif extension_lower == ".exe":
            content_type_matches = "exe" in content_type.lower() or "application/x-msdownload" in content_type.lower()
        elif extension_lower == ".dmg":
            content_type_matches = "dmg" in content_type.lower() or "application/x-apple-diskimage" in content_type.lower()
        elif extension_lower == ".deb":
            content_type_matches = "deb" in content_type.lower() or "application/vnd.debian.binary-package" in content_type.lower()
        elif extension_lower == ".rpm":
            content_type_matches = "rpm" in content_type.lower() or "application/x-rpm" in content_type.lower()
        
        if not url_has_extension and not content_type_matches:
            return False
    
    return True


def execute(input_data: dict) -> dict:
    """Execute the find-download-link capsule.
    
    Args:
        input_data: Dictionary containing:
            - 'query': What to look for
            - 'required_extension': Optional file extension to enforce
            - 'domain_hint': Optional preferred domain
            
    Returns:
        Dictionary containing:
            - 'found': Boolean indicating if a link was found
            - 'url': The found URL (or null)
            - 'metadata': File metadata (content_type, file_size_mb, status_code)
            - 'reasoning': Brief explanation
    """
    # Extract input parameters
    query = input_data.get("query", "")
    required_extension = input_data.get("required_extension")
    domain_hint = input_data.get("domain_hint")
    
    if not query:
        raise ValueError("'query' is required")
    
    # Load configuration
    try:
        agent_config = load_agent_config()
    except Exception as e:
        raise RuntimeError(f"Failed to load agent config: {e}")
    
    try:
        system_prompt = load_system_prompt()
    except Exception as e:
        raise RuntimeError(f"Failed to load system prompt: {e}")
    
    try:
        user_prompt_template = load_user_prompt_template()
    except Exception as e:
        raise RuntimeError(f"Failed to load user prompt template: {e}")
    
    try:
        functions = load_tools()
    except Exception as e:
        raise RuntimeError(f"Failed to load tools: {e}")
    
    # Get API configuration from environment variables
    api_base = os.environ.get('OPENAI_API_BASE')
    if not api_base:
        raise RuntimeError("OPENAI_API_BASE environment variable not set")
    
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key or api_key == "":
        api_key = 'dummy'
    
    # Initialize OpenAI client
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
    except Exception as e:
        raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
    
    # Format user prompt
    user_message = format_user_prompt(user_prompt_template, query, required_extension, domain_hint)
    
    # Initialize conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    # Agent execution loop (max 20 iterations to prevent infinite loops)
    max_iterations = 20
    iteration = 0
    found_url = None
    found_metadata = None
    reasoning = ""
    
    while iteration < max_iterations:
        iteration += 1
        print(f"[DEBUG] Agent iteration {iteration}/{max_iterations}", flush=True)
        
        try:
            # Make API call with function calling
            response = client.chat.completions.create(
                model=agent_config.get('model', 'gemini-2.5-flash-lite'),
                messages=messages,
                tools=functions,
                tool_choice="required",
                temperature=agent_config.get('temperature', 0.3),
                max_tokens=agent_config.get('max_tokens', 2000)
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {e}")
        
        if not response.choices or not response.choices[0].message:
            raise RuntimeError("Invalid response from OpenAI API")
        
        assistant_message = response.choices[0].message
        assistant_msg_dict = {
            "role": "assistant",
            "content": assistant_message.content or ""
        }
        # Add tool_calls if present (need to serialize them properly)
        if assistant_message.tool_calls:
            assistant_msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        messages.append(assistant_msg_dict)
        
        # Check if the agent wants to call a function
        if assistant_message.tool_calls:
            # Execute function calls
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                
                print(f"[DEBUG] Executing function: {function_name} with args: {arguments}", flush=True)
                
                # Execute the function
                function_result = execute_function_call(function_name, arguments)
                
                # Add function result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": function_result,
                    "name": function_name
                })
                
                # Handle submit_result - agent is returning the found URL
                if function_name == "submit_result":
                    submitted_url = arguments.get("url", "")
                    submitted_reasoning = arguments.get("reasoning", "")
                    
                    # Verify the submitted URL before accepting it
                    verification_result = verify_url_headers(submitted_url)
                    
                    if validate_url(verification_result, required_extension, domain_hint):
                        found_url = verification_result.get("final_url", submitted_url)
                        content_length = verification_result.get("content_length", 0)
                        found_metadata = {
                            "content_type": verification_result.get("content_type", ""),
                            "file_size_mb": round(content_length / (1024 * 1024), 2) if content_length > 0 else 0,
                            "status_code": verification_result.get("status_code", 0)
                        }
                        reasoning = submitted_reasoning or f"Found valid download URL: {found_url}"
                        print(f"[DEBUG] Agent submitted valid URL: {found_url}", flush=True)
                        break
                    else:
                        # URL doesn't meet requirements - tell agent to try again
                        print(f"[DEBUG] Submitted URL failed validation: {submitted_url}", flush=True)
                        messages.append({
                            "role": "user",
                            "content": f"The URL you submitted ({submitted_url}) does not meet the requirements. Please verify it again with verify_url_headers and ensure it matches all criteria before submitting."
                        })
                        continue
        
        # With tool_choice="required", we should always have tool_calls
        # If somehow we don't (shouldn't happen), log a warning and continue
        if not assistant_message.tool_calls:
            print(f"[WARNING] No tool calls in iteration {iteration} despite tool_choice='required'", flush=True)
            messages.append({
                "role": "user",
                "content": "You must call a tool in every iteration. Please use search_web, extract_page_links, verify_url_headers, or submit_result."
            })
            continue
        
        # If we found a valid URL, break out of the loop
        if found_url:
            break
    
    # Return result
    if found_url:
        return {
            "found": True,
            "url": found_url,
            "metadata": found_metadata or {},
            "reasoning": reasoning or "Successfully located and verified download URL"
        }
    else:
        return {
            "found": False,
            "url": None,
            "metadata": {},
            "reasoning": reasoning or f"Could not find a valid download URL after {iteration} attempts"
        }
