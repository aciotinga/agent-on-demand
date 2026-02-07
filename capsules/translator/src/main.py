"""Main logic for the translator capsule."""

import os
import sys
import json
from pathlib import Path
from openai import OpenAI
import yaml
from typing import Dict, Any, Optional
import requests


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


def get_orchestrator_url() -> str:
    """Get orchestrator URL from environment variable.
    
    Returns:
        Orchestrator URL (defaults to http://host.docker.internal:8000)
    """
    return os.environ.get('ORCHESTRATOR_URL', 'http://host.docker.internal:8000')


def fetch_target_schema(target_capsule: str, orchestrator_url: str) -> Optional[Dict[str, Any]]:
    """Fetch the target capsule's input schema from the orchestrator.
    
    Args:
        target_capsule: Name of the target capsule
        orchestrator_url: Base URL of the orchestrator
        
    Returns:
        Target capsule's input schema dictionary, or None if fetch failed
    """
    url = f"{orchestrator_url}/capsules/{target_capsule}/schema"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        schema_data = response.json()
        return schema_data.get('input')
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to fetch schema from orchestrator: {e}", file=sys.stderr)
        return None


def format_mapping_instructions(mapping: Optional[Dict[str, str]]) -> str:
    """Format field mapping instructions for the prompt.
    
    Args:
        mapping: Dictionary mapping target fields to source fields
        
    Returns:
        Formatted string describing the mappings
    """
    if not mapping:
        return "No field mappings provided."
    
    instructions = "Apply the following field mappings:\n"
    for target_field, source_field in mapping.items():
        if source_field:
            instructions += f"- Map '{source_field}' from source to '{target_field}' in target\n"
        else:
            instructions += f"- Set '{target_field}' to null or omit it\n"
    
    return instructions


def transform_data_with_llm(
    source_output: Dict[str, Any],
    target_schema: Dict[str, Any],
    mapping: Optional[Dict[str, str]],
    instructions: Optional[str],
    agent_config: Dict[str, Any],
    system_prompt: str,
    task_template: str
) -> Dict[str, Any]:
    """Use LLM to transform source output to match target schema.
    
    Args:
        source_output: Source output data
        target_schema: Target capsule's input schema
        mapping: Field mappings
        instructions: Natural language transformation instructions
        agent_config: Agent configuration
        system_prompt: System prompt template
        task_template: Task template
        
    Returns:
        Transformed input data matching target schema
    """
    # Format mapping instructions
    mapping_instructions = format_mapping_instructions(mapping)
    
    # Format transformation instructions
    transformation_instructions = instructions if instructions else "No specific transformation instructions provided. Transform the data to match the target schema."
    
    # Build task prompt
    task_prompt = task_template.format(
        source_output=json.dumps(source_output, indent=2),
        target_capsule="target_capsule",  # Will be filled in by caller context
        target_schema=json.dumps(target_schema, indent=2),
        mapping_instructions=mapping_instructions,
        transformation_instructions=transformation_instructions
    )
    
    # Initialize OpenAI client
    api_base = os.environ.get('OPENAI_API_BASE')
    api_key = os.environ.get('OPENAI_API_KEY', 'dummy-key')
    
    client = OpenAI(
        api_key=api_key,
        base_url=api_base
    )
    
    # Make LLM call
    response = client.chat.completions.create(
        model=agent_config['model'],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt}
        ],
        temperature=agent_config.get('temperature', 0.1),
        max_tokens=agent_config.get('max_tokens', 2000)
    )
    
    result_text = response.choices[0].message.content.strip()
    
    # Try to parse JSON from response
    # The LLM might return JSON wrapped in markdown code blocks
    if result_text.startswith('```'):
        # Extract JSON from code block
        lines = result_text.split('\n')
        json_lines = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                json_lines.append(line)
        result_text = '\n'.join(json_lines)
    
    try:
        return json.loads(result_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nResponse: {result_text}")


def execute(input_data: dict) -> dict:
    """Transform source output into target capsule input.
    
    Args:
        input_data: Dictionary containing:
            - source_output: Output from previous capsule
            - target_capsule: Name of target capsule
            - mapping: Optional field mappings
            - instructions: Optional transformation instructions
            
    Returns:
        Transformed input data matching target capsule's schema
    """
    source_output = input_data['source_output']
    target_capsule = input_data['target_capsule']
    mapping = input_data.get('mapping')
    instructions = input_data.get('instructions')
    
    # Get orchestrator URL
    orchestrator_url = get_orchestrator_url()
    
    # Fetch target schema
    target_schema = fetch_target_schema(target_capsule, orchestrator_url)
    
    if not target_schema:
        # Fallback: try to read schema from file system if orchestrator API fails
        # This assumes capsules directory is accessible
        print("Warning: Could not fetch schema from orchestrator, attempting file system access", file=sys.stderr)
        # For now, we'll proceed without schema validation and let the LLM work with just the instructions
        target_schema = {"type": "object", "description": "Target capsule input schema"}
    
    # Load agent configuration and prompts
    agent_config = load_agent_config()
    system_prompt = load_system_prompt()
    task_template = load_task_template()
    
    # Update task template with actual target capsule name
    task_template = task_template.replace("{target_capsule}", target_capsule)
    
    # Transform data using LLM
    transformed_data = transform_data_with_llm(
        source_output=source_output,
        target_schema=target_schema,
        mapping=mapping,
        instructions=instructions,
        agent_config=agent_config,
        system_prompt=system_prompt,
        task_template=task_template
    )
    
    return transformed_data
