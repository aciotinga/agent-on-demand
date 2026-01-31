#!/usr/bin/env python3
"""Debug script to test LiteLLM connection from orchestrator config."""

import os
import sys
from pathlib import Path
from openai import OpenAI

# Add orchestrator to path to import config
sys.path.insert(0, str(Path(__file__).parent / "orchestrator"))
from config_loader import Config


def test_litellm():
    """Test LiteLLM connection using orchestrator config."""
    print("=" * 60)
    print("LiteLLM Connection Test")
    print("=" * 60)
    
    # Load config
    try:
        config_path = Path(__file__).parent / "orchestrator" / "config.yaml"
        config = Config(config_path=str(config_path))
        print(f"✓ Loaded config from: {config_path}")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return False
    
    # Get LLM config
    api_base = config.get_llm_api_base()
    api_key = config.get_llm_api_key()
    
    print(f"\nConfiguration:")
    print(f"  API Base: {api_base}")
    print(f"  API Key: {'*' * min(len(api_key), 8) if api_key else 'None'} (from {'ENV' if os.environ.get('OPENAI_API_KEY') else 'config'})")
    
    # Initialize OpenAI client
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        print(f"\n✓ OpenAI client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize OpenAI client: {e}")
        return False
    
    # Test connection with a simple request
    print(f"\nTesting connection with a simple chat completion...")
    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash-lite",  # Default model, adjust if needed
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello, LiteLLM is working!' if you can read this."}
            ],
            temperature=0.3,
            max_tokens=50
        )
        
        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content.strip()
            print(f"\n✓ Connection successful!")
            print(f"\nResponse:")
            print(f"  {content}")
            print(f"\nModel used: {response.model}")
            print(f"Tokens used: {response.usage.total_tokens if hasattr(response, 'usage') and response.usage else 'N/A'}")
            return True
        else:
            print(f"✗ Invalid response format")
            return False
            
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        print(f"\nError details:")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {str(e)}")
        
        # Additional debugging info
        if hasattr(e, 'response'):
            print(f"  Response status: {getattr(e.response, 'status_code', 'N/A')}")
            print(f"  Response body: {getattr(e.response, 'text', 'N/A')}")
        
        return False


if __name__ == "__main__":
    success = test_litellm()
    print("\n" + "=" * 60)
    if success:
        print("✓ Test PASSED")
        sys.exit(0)
    else:
        print("✗ Test FAILED")
        sys.exit(1)
