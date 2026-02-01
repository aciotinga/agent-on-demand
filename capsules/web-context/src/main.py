"""Main logic for the web-context capsule."""

import os
import json
from pathlib import Path
from openai import OpenAI
import yaml
from typing import Dict, List, Any, Optional
from capabilities import search_web, visit_page


def load_agent_config():
    """Load agent.yaml configuration."""
    config_path = Path(__file__).parent.parent / "agent.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_system_prompt():
    """Load the system prompt from system.md."""
    prompt_path = Path(__file__).parent / "ai" / "system.md"
    with open(prompt_path, 'r') as f:
        return f.read()


def load_task_template():
    """Load the task template from task.md."""
    template_path = Path(__file__).parent / "ai" / "task.md"
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


def format_task_prompt(template: str, research_goal: str) -> str:
    """Format the task prompt template with research goal."""
    return template.replace("{research_goal}", research_goal)


def format_system_prompt(template: str, research_goal: str) -> str:
    """Format the system prompt template with research goal."""
    return template.replace("{research_goal}", research_goal)


def execute_function_call(function_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute a function call requested by the LLM."""
    if function_name == "search_web":
        query = arguments.get("query", "")
        result = search_web(query, max_results=10)
        return result
    
    elif function_name == "visit_page":
        url = arguments.get("url", "")
        result = visit_page(url)
        return result
    
    elif function_name == "complete_task":
        # This is handled specially in the main loop - just return acknowledgment
        return json.dumps({"status": "received", "message": "Task completed successfully"})
    
    else:
        return json.dumps({"error": f"Unknown function: {function_name}"})


def generate_forced_summary(messages: List[Dict], client, agent_config) -> str:
    """Generate a summary from conversation context when max_steps is reached."""
    summary_prompt = (
        "Based on the conversation history above, synthesize a comprehensive answer to the research goal. "
        "Summarize the key information gathered from all the web pages visited."
    )
    
    # Add summary request to messages
    summary_messages = messages + [
        {"role": "user", "content": summary_prompt}
    ]
    
    try:
        response = client.chat.completions.create(
            model=agent_config.get('model', 'gemini-2.5-flash-lite'),
            messages=summary_messages,
            temperature=agent_config.get('temperature', 0.3),
            max_tokens=agent_config.get('max_tokens', 4000)
        )
        
        if not response.choices or not response.choices[0].message:
            return "Unable to generate summary from gathered information."
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARNING] Failed to generate forced summary: {e}", flush=True)
        return "Research session reached maximum steps. Summary generation failed."


def execute(input_data: dict) -> dict:
    """Execute the web-context capsule.
    
    Args:
        input_data: Dictionary containing:
            - 'research_goal': The question or topic to research
            - 'max_steps': Maximum number of tool calls (default: 10)
            
    Returns:
        Dictionary containing:
            - 'final_summary': The synthesized answer
            - 'visited_urls': List of all URLs successfully visited
    """
    # Extract input parameters
    research_goal = input_data.get("research_goal", "")
    max_steps = input_data.get("max_steps", 10)
    
    if not research_goal:
        raise ValueError("'research_goal' is required")
    
    # Load configuration
    try:
        agent_config = load_agent_config()
    except Exception as e:
        raise RuntimeError(f"Failed to load agent config: {e}")
    
    try:
        system_prompt_template = load_system_prompt()
    except Exception as e:
        raise RuntimeError(f"Failed to load system prompt: {e}")
    
    try:
        task_template = load_task_template()
    except Exception as e:
        raise RuntimeError(f"Failed to load task template: {e}")
    
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
    
    # Format prompts with research goal
    system_prompt = format_system_prompt(system_prompt_template, research_goal)
    user_message = format_task_prompt(task_template, research_goal)
    
    # Initialize conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    # Track visited URLs and final summary
    visited_urls = []
    final_summary = None
    step_count = 0
    
    # Agent execution loop (ReAct pattern)
    while step_count < max_steps:
        step_count += 1
        print(f"[DEBUG] Agent iteration {step_count}/{max_steps}", flush=True)
        
        try:
            # Make API call with function calling (tool_choice="required" forces tool call)
            response = client.chat.completions.create(
                model=agent_config.get('model', 'gemini-2.5-flash-lite'),
                messages=messages,
                tools=functions,
                tool_choice="required",
                temperature=agent_config.get('temperature', 0.3),
                max_tokens=agent_config.get('max_tokens', 4000)
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
        
        # Add tool_calls if present
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
                
                # Track visited URLs for visit_page calls
                if function_name == "visit_page":
                    url = arguments.get("url", "")
                    # Only add to visited_urls if the visit was successful (not an error message)
                    if url and not function_result.startswith("Error"):
                        if url not in visited_urls:
                            visited_urls.append(url)
                
                # Add function result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": function_result if isinstance(function_result, str) else json.dumps(function_result),
                    "name": function_name
                })
                
                # Handle complete_task - agent is returning the final summary
                if function_name == "complete_task":
                    summary = arguments.get("summary", "")
                    if summary:
                        final_summary = summary
                        print(f"[DEBUG] Agent completed task with summary", flush=True)
                        break
            
            # Break if complete_task was called
            if final_summary:
                break
        
        # With tool_choice="required", we should always have tool_calls
        # If somehow we don't (shouldn't happen), log a warning and continue
        if not assistant_message.tool_calls:
            print(f"[WARNING] No tool calls in iteration {step_count} despite tool_choice='required'", flush=True)
            messages.append({
                "role": "user",
                "content": "You must call a tool in every iteration. Please use search_web, visit_page, or complete_task."
            })
            continue
    
    # If loop ended without complete_task, generate forced summary
    if not final_summary:
        print(f"[DEBUG] Max steps reached ({max_steps}), generating forced summary", flush=True)
        final_summary = generate_forced_summary(messages, client, agent_config)
    
    # Return result
    return {
        "final_summary": final_summary or "No summary generated.",
        "visited_urls": visited_urls
    }
