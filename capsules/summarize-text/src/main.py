"""Main logic for the summarize-text capsule."""

import os
import sys
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


def read_file_content(file_path: str) -> str:
    """Read a file as raw text.
    
    Args:
        file_path: Path to the file to read. If the file doesn't exist at the given path,
                   tries to find it in /io/input/ using the filename.
        
    Returns:
        The file content as a string.
    """
    # Try the original path first
    actual_path = file_path
    if not os.path.exists(file_path):
        # If file doesn't exist, try to find it in /io/input/ using the filename
        filename = os.path.basename(file_path)
        io_input_path = f"/io/input/{filename}"
        if os.path.exists(io_input_path):
            actual_path = io_input_path
        else:
            raise ValueError(f"File not found: {file_path} (also checked /io/input/{filename})")
    
    try:
        with open(actual_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except FileNotFoundError:
        raise ValueError(f"File not found: {file_path}")
    except Exception as e:
        raise ValueError(f"Error reading file {file_path}: {e}")


def summarize_text(text: str, client, agent_config, system_prompt, task_template) -> str:
    """Summarize a single text string.
    
    Args:
        text: The text to summarize.
        client: OpenAI client instance.
        agent_config: Agent configuration dictionary.
        system_prompt: System prompt string.
        task_template: Task template string.
        
    Returns:
        The summarized text.
    """
    if not text:
        raise ValueError("Text cannot be empty")
    
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
    
    return response.choices[0].message.content.strip()


def execute(input_data: dict) -> dict:
    """Execute the summarize-text capsule.
    
    Args:
        input_data: Dictionary containing one of:
            - 'text': single text string to summarize
            - 'texts': list of text strings to summarize separately
            - 'file': single file path to read and summarize
            - 'files': list of file paths to read and summarize separately
        
    Returns:
        Dictionary containing:
            - 'summary': single summary string (for single inputs)
            - 'summaries': list of summary strings (for batch inputs)
    """
    # Determine input type and extract data
    text = input_data.get('text')
    texts = input_data.get('texts')
    file_path = input_data.get('file')
    files = input_data.get('files')
    
    # Validate that exactly one input type is provided
    input_count = sum([
        text is not None,
        texts is not None,
        file_path is not None,
        files is not None
    ])
    
    if input_count == 0:
        raise ValueError("At least one input must be provided: 'text', 'texts', 'file', or 'files'")
    if input_count > 1:
        raise ValueError("Only one input type should be provided at a time: 'text', 'texts', 'file', or 'files'")
    
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
    
    # Process based on input type
    if text is not None:
        # Single text input
        summary = summarize_text(text, client, agent_config, system_prompt, task_template)
        return {"summary": summary}
    
    elif texts is not None:
        # Batch texts input
        if not isinstance(texts, list):
            raise ValueError("'texts' must be a list of strings")
        if len(texts) == 0:
            raise ValueError("'texts' list cannot be empty")
        
        summaries = []
        for i, text_item in enumerate(texts):
            if not isinstance(text_item, str):
                raise ValueError(f"Item at index {i} in 'texts' must be a string")
            print(f"[DEBUG] Summarizing text {i+1}/{len(texts)}", flush=True)
            summary = summarize_text(text_item, client, agent_config, system_prompt, task_template)
            summaries.append(summary)
        
        return {"summaries": summaries}
    
    elif file_path is not None:
        # Single file input
        if not isinstance(file_path, str):
            raise ValueError("'file' must be a string path")
        
        print(f"[DEBUG] Reading file: {file_path}", flush=True)
        
        try:
            file_content = read_file_content(file_path)
            print(f"[DEBUG] File read successfully, length: {len(file_content)} characters", flush=True)
        except Exception as e:
            raise
        
        summary = summarize_text(file_content, client, agent_config, system_prompt, task_template)
        return {"summary": summary}
    
    elif files is not None:
        # Batch files input
        if not isinstance(files, list):
            raise ValueError("'files' must be a list of file paths")
        if len(files) == 0:
            raise ValueError("'files' list cannot be empty")
        
        summaries = []
        for i, file_item in enumerate(files):
            if not isinstance(file_item, str):
                raise ValueError(f"Item at index {i} in 'files' must be a string path")
            
            print(f"[DEBUG] Reading and summarizing file {i+1}/{len(files)}: {file_item}", flush=True)
            
            try:
                file_content = read_file_content(file_item)
                print(f"[DEBUG] File read successfully, length: {len(file_content)} characters", flush=True)
            except Exception as e:
                raise
            
            summary = summarize_text(file_content, client, agent_config, system_prompt, task_template)
            summaries.append(summary)
        
        return {"summaries": summaries}
    
    else:
        # This should never be reached due to validation above, but included for safety
        raise ValueError("No valid input provided")
