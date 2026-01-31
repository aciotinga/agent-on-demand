"""Main logic for the summarize-text capsule."""

import os
from pathlib import Path
from openai import OpenAI
import yaml

# Load agent configuration
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


def execute(input_data: dict) -> dict:
    """Execute the summarize-text capsule.
    
    Args:
        input_data: Dictionary containing 'text' key with the text to summarize.
        
    Returns:
        Dictionary containing 'summary' key with the summarized text.
    """
    # Extract input
    text = input_data.get('text', '')
    if not text:
        raise ValueError("Input 'text' is required and cannot be empty")
    
    # Load configuration with error handling
    try:
        agent_config = load_agent_config()
    except Exception as e:
        raise RuntimeError(f"Failed to load agent config: {e}")
    
    try:
        system_prompt = load_system_prompt()
    except Exception as e:
        raise RuntimeError(f"Failed to load system prompt: {e}")
    
    try:
        task_template = load_task_template()
    except Exception as e:
        raise RuntimeError(f"Failed to load task template: {e}")
    
    # Get API configuration from environment variables
    api_base = os.environ.get('OPENAI_API_BASE')
    if not api_base:
        raise RuntimeError("OPENAI_API_BASE environment variable not set")
    
    api_key = os.environ.get('OPENAI_API_KEY', '')
    # Default to 'dummy' if empty (required by some LiteLLM proxy configurations)
    if not api_key or api_key == "":
        api_key = 'dummy'
    
    # Print debug info (flush to ensure it appears in logs)
    print(f"[DEBUG] API Key: {api_key}", flush=True)
    print(f"[DEBUG] API Base: {api_base}", flush=True)
    
    # Initialize OpenAI client with explicit parameters (more reliable than env vars)
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
    except Exception as e:
        raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
    
    # Format task template with input text
    try:
        user_message = task_template.format(text=text)
    except Exception as e:
        raise RuntimeError(f"Failed to format task template: {e}")
    
    # Make API call
    try:
        response = client.chat.completions.create(
            model=agent_config.get('model', 'gemini-2.5-flash-lite'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=agent_config.get('temperature', 0.3),
            max_tokens=agent_config.get('max_tokens', 1000)
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API call failed: {e}")
    
    # Extract summary
    if not response.choices or not response.choices[0].message:
        raise RuntimeError("Invalid response from OpenAI API")
    
    summary = response.choices[0].message.content.strip()
    
    return {
        "summary": summary
    }
