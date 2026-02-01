"""Bridge: Handles I/O operations and validation for the link-scout capsule."""

import json
import sys
from pathlib import Path
import jsonschema

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import execute function
# #region agent log
import json
log_path = Path("/tmp/debug.log") if Path("/tmp").exists() else Path("/app/debug.log")
try:
    with open(log_path, "a") as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"pre-import","hypothesisId":"A","location":"run.py:13","message":"Before import attempt","data":{"pythonPath":sys.path},"timestamp":__import__("time").time()}) + "\n")
except: pass
# #endregion
try:
    from main import execute
    # #region agent log
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"pre-import","hypothesisId":"A","location":"run.py:15","message":"Import successful","data":{},"timestamp":__import__("time").time()}) + "\n")
    except: pass
    # #endregion
except ImportError as e:
    # #region agent log
    try:
        import subprocess
        installed = subprocess.check_output(["pip", "list"], text=True, stderr=subprocess.DEVNULL)
        with open(log_path, "a") as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"pre-import","hypothesisId":"A,B","location":"run.py:17","message":"Import failed - checking installed packages","data":{"error":str(e),"installedPackages":installed[:500]},"timestamp":__import__("time").time()}) + "\n")
    except Exception as check_err:
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"pre-import","hypothesisId":"A,B","location":"run.py:17","message":"Import failed - could not check packages","data":{"error":str(e),"checkError":str(check_err)},"timestamp":__import__("time").time()}) + "\n")
        except: pass
    # #endregion
    print(f"ERROR: Failed to import execute from main: {e}", file=sys.stderr)
    print(f"ERROR: Python path: {sys.path}", file=sys.stderr)
    print(f"ERROR: Looking for main.py in: {src_path}", file=sys.stderr)
    if (src_path / "main.py").exists():
        print(f"ERROR: main.py exists at {src_path / 'main.py'}", file=sys.stderr)
    else:
        print(f"ERROR: main.py NOT found at {src_path / 'main.py'}", file=sys.stderr)
    sys.exit(1)


def load_schema():
    """Load and return the schema.json file."""
    schema_path = Path(__file__).parent / "schema.json"
    with open(schema_path, 'r') as f:
        return json.load(f)


def validate_input(data, schema):
    """Validate input data against the input schema."""
    input_schema = schema.get('input')
    if not input_schema:
        return True, None
    
    try:
        jsonschema.validate(instance=data, schema=input_schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"Input validation failed: {e.message}"
    except jsonschema.SchemaError as e:
        return False, f"Schema error: {e.message}"


def validate_output(data, schema):
    """Validate output data against the output schema."""
    output_schema = schema.get('output')
    if not output_schema:
        return True, None
    
    try:
        jsonschema.validate(instance=data, schema=output_schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"Output validation failed: {e.message}"
    except jsonschema.SchemaError as e:
        return False, f"Schema error: {e.message}"


def main():
    """Main entry point for the capsule."""
    # Debug: Print environment variables at container startup
    import os
    api_base = os.environ.get('OPENAI_API_BASE', '(not set)')
    api_key = os.environ.get('OPENAI_API_KEY', '(not set)')
    print(f"[DEBUG] Container startup - Environment variables:", flush=True)
    print(f"  OPENAI_API_BASE: {api_base}", flush=True)
    print(f"  OPENAI_API_KEY: {api_key}", flush=True)
    
    # Load schema
    schema = load_schema()
    
    # Read input JSON
    input_path = Path("/io/input.json")
    if not input_path.exists():
        print("ERROR: input.json not found in /io/", file=sys.stderr)
        sys.exit(1)
    
    with open(input_path, 'r') as f:
        try:
            input_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in input.json: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Validate input
    is_valid, error_msg = validate_input(input_data, schema)
    if not is_valid:
        print(f"ERROR: {error_msg}", file=sys.stderr)
        sys.exit(1)
    
    # Execute the capsule logic
    try:
        output_data = execute(input_data)
    except Exception as e:
        print(f"ERROR: Execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Validate output
    is_valid, error_msg = validate_output(output_data, schema)
    if not is_valid:
        print(f"ERROR: {error_msg}", file=sys.stderr)
        sys.exit(1)
    
    # Write output JSON
    output_path = Path("/io/output.json")
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print("SUCCESS: Capsule execution completed", file=sys.stderr)


if __name__ == "__main__":
    main()
