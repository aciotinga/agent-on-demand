# Workflows Documentation

## Overview

Workflows in the Agent-On-Demand (AOD) system enable you to chain multiple capsules together to accomplish complex tasks. A workflow is a linear sequence of capsules where the output of one capsule becomes the input to the next capsule. The workflow system itself is implemented as a capsule, following the AOD philosophy that "everything is a capsule."

## How Workflows Work

### Architecture

A workflow consists of:

1. **Workflow Definition**: A JSON file or JSON string that describes the sequence of capsules to execute
2. **Workflow Capsule**: The capsule that executes the workflow (located at `capsules/workflow/`)
3. **Translator Capsule**: An optional capsule that transforms data between capsules (located at `capsules/translator/`)

### Execution Flow

```
User Input → Workflow Capsule → Step 1 (Capsule A)
                                    ↓
                            Output A → [Translator?] → Step 2 (Capsule B)
                                                           ↓
                                                   Output B → [Translator?] → Step 3 (Capsule C)
                                                                                  ↓
                                                                          Final Output
```

The workflow capsule:
1. Parses the workflow definition
2. Validates all referenced capsules exist
3. Executes each step sequentially
4. For each step, optionally applies translation if needed
5. Passes output from one step to the next
6. Returns the final output from the last step

## Workflow Definition Format

A workflow is defined as a JSON object with the following structure:

```json
{
  "name": "example-workflow",
  "description": "A description of what this workflow does",
  "steps": [
    {
      "capsule": "capsule-name-1",
      "translator": null,
      "translator_instructions": null
    },
    {
      "capsule": "capsule-name-2",
      "translator": "translator",
      "translator_instructions": {
        "target_capsule": "capsule-name-2",
        "mapping": {
          "target_field": "source_field"
        },
        "instructions": "Natural language instructions for transformation"
      }
    }
  ]
}
```

### Workflow Schema

- **name** (string, optional): A human-readable name for the workflow
- **description** (string, optional): A description of what the workflow accomplishes
- **steps** (array, required): An ordered list of workflow steps

### Step Schema

Each step in the `steps` array must contain:

- **capsule** (string, required): The name of the capsule to execute. Must match a capsule registered in `orchestrator/config.yaml`
- **translator** (string, optional): The name of the translator capsule to use. Typically `"translator"` or `null` if no translation is needed
- **translator_instructions** (object, optional): Instructions for the translator capsule. Required if `translator` is not `null`
  - **target_capsule** (string, required): The name of the target capsule (the `capsule` field in this step)
  - **mapping** (object, optional): Field mappings from source output fields to target input fields
    - Keys are target field names
    - Values are source field names (or `null` to omit the field)
  - **instructions** (string, optional): Natural language instructions describing how to transform the data

## Creating a Workflow

### Step 1: Define Your Workflow

Create a JSON file (e.g., `my-workflow.json`) with your workflow definition:

```json
{
  "name": "research-and-summarize",
  "description": "Research a topic and summarize the findings",
  "steps": [
    {
      "capsule": "web-context",
      "translator": null,
      "translator_instructions": null
    },
    {
      "capsule": "summarize-text",
      "translator": "translator",
      "translator_instructions": {
        "target_capsule": "summarize-text",
        "mapping": {
          "text": "final_summary"
        },
        "instructions": "Extract the final_summary field from the web-context output and pass it as the 'text' field to summarize-text"
      }
    }
  ]
}
```

### Step 2: Execute the Workflow

Execute the workflow using the workflow capsule via the orchestrator API:

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "capsule": "workflow",
    "input": {
      "workflow_file": "/path/to/my-workflow.json",
      "initial_input": {
        "research_goal": "What is machine learning?"
      }
    }
  }'
```

Or provide the workflow as a JSON string:

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "capsule": "workflow",
    "input": {
      "workflow": "{\"steps\":[{\"capsule\":\"web-context\",\"translator\":null,\"translator_instructions\":null},{\"capsule\":\"summarize-text\",\"translator\":\"translator\",\"translator_instructions\":{\"target_capsule\":\"summarize-text\",\"mapping\":{\"text\":\"final_summary\"}}}]}",
      "initial_input": {
        "research_goal": "What is machine learning?"
      }
    }
  }'
```

### Step 3: Handle the Response

The workflow capsule returns a response with the following structure:

```json
{
  "success": true,
  "output": {
    "success": true,
    "final_output": {
      "summary": "Machine learning is..."
    },
    "steps_executed": 2,
    "error": null,
    "step_results": [
      {
        "step_index": 0,
        "capsule": "web-context",
        "success": true,
        "output": {
          "final_summary": "...",
          "visited_urls": [...]
        },
        "error": null
      },
      {
        "step_index": 1,
        "capsule": "summarize-text",
        "success": true,
        "output": {
          "summary": "..."
        },
        "error": null
      }
    ]
  }
}
```

## Understanding Translators

### When Do You Need a Translator?

A translator is needed when:
- The output schema of one capsule doesn't match the input schema of the next capsule
- You need to transform or restructure data between steps
- Field names differ between capsules
- You need to extract specific fields from complex output structures

### When Can You Skip the Translator?

You can skip the translator when:
- The output of one capsule directly matches the input schema of the next capsule
- All required fields are present with matching names and types
- No data transformation is needed

### How Translators Work

The translator capsule uses an LLM agent to:
1. Fetch the target capsule's input schema from the orchestrator
2. Analyze the source output data structure
3. Apply field mappings (if provided)
4. Follow natural language transformation instructions
5. Generate transformed output that matches the target schema

### Translator Input

The translator receives:
- **source_output**: The output from the previous capsule
- **target_capsule**: The name of the capsule that will receive the transformed data
- **mapping** (optional): Field mappings from source to target
- **instructions** (optional): Natural language instructions for transformation

### Example: Using a Translator

Consider a workflow where `web-context` outputs:
```json
{
  "final_summary": "Research findings...",
  "visited_urls": ["url1", "url2"]
}
```

And `summarize-text` expects:
```json
{
  "text": "Text to summarize"
}
```

You need a translator to map `final_summary` → `text`:

```json
{
  "capsule": "summarize-text",
  "translator": "translator",
  "translator_instructions": {
    "target_capsule": "summarize-text",
    "mapping": {
      "text": "final_summary"
    },
    "instructions": "Extract the final_summary field and pass it as 'text'"
  }
}
```

## Complete Examples

### Example 1: Simple Two-Step Workflow (No Translation)

```json
{
  "name": "simple-research",
  "description": "Research a topic using web-context",
  "steps": [
    {
      "capsule": "web-context",
      "translator": null,
      "translator_instructions": null
    }
  ]
}
```

**Input:**
```json
{
  "workflow_file": "simple-research.json",
  "initial_input": {
    "research_goal": "What is Python?"
  }
}
```

### Example 2: Research and Summarize (With Translation)

```json
{
  "name": "research-and-summarize",
  "description": "Research a topic and create a summary",
  "steps": [
    {
      "capsule": "web-context",
      "translator": null,
      "translator_instructions": null
    },
    {
      "capsule": "summarize-text",
      "translator": "translator",
      "translator_instructions": {
        "target_capsule": "summarize-text",
        "mapping": {
          "text": "final_summary"
        },
        "instructions": "Extract the final_summary field from web-context output and use it as the text input for summarize-text"
      }
    }
  ]
}
```

**Input:**
```json
{
  "workflow_file": "research-and-summarize.json",
  "initial_input": {
    "research_goal": "Explain quantum computing"
  }
}
```

### Example 3: Complex Transformation

```json
{
  "name": "complex-workflow",
  "description": "Multi-step workflow with multiple transformations",
  "steps": [
    {
      "capsule": "web-context",
      "translator": null,
      "translator_instructions": null
    },
    {
      "capsule": "summarize-text",
      "translator": "translator",
      "translator_instructions": {
        "target_capsule": "summarize-text",
        "mapping": {
          "text": "final_summary"
        },
        "instructions": "Extract only the final_summary field. Ignore visited_urls. The summary should be passed as 'text' to summarize-text."
      }
    }
  ]
}
```

## Workflow Capsule Input Schema

The workflow capsule accepts the following input:

```json
{
  "workflow": "JSON string of workflow definition",
  "workflow_file": "Path to workflow JSON file (alternative to 'workflow')",
  "initial_input": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

**Required:**
- `initial_input`: The input data for the first capsule in the workflow

**One of the following is required:**
- `workflow`: JSON string containing the workflow definition
- `workflow_file`: Path to a workflow JSON file (relative to `/io/input/` or absolute path)

## Workflow Capsule Output Schema

The workflow capsule returns:

```json
{
  "success": true,
  "final_output": {
    "output": "from last capsule"
  },
  "steps_executed": 2,
  "error": null,
  "step_results": [
    {
      "step_index": 0,
      "capsule": "capsule-name",
      "success": true,
      "output": {...},
      "error": null
    }
  ]
}
```

**Fields:**
- `success`: Boolean indicating if the workflow completed successfully
- `final_output`: Output from the last capsule in the workflow
- `steps_executed`: Number of steps that were executed
- `error`: Error message if execution failed (null if successful)
- `step_results`: Array of results for each step, including intermediate outputs

## Best Practices

### 1. Workflow Design

- **Keep workflows linear**: The current implementation supports linear chains only
- **Minimize steps**: Each step adds execution time and potential failure points
- **Use descriptive names**: Name your workflows clearly to indicate their purpose

### 2. Translation Strategy

- **Use field mappings when possible**: They're more reliable than pure natural language instructions
- **Provide clear instructions**: When using natural language instructions, be specific about what transformation is needed
- **Test translations**: Verify that translators produce the expected output format before using in production workflows

### 3. Error Handling

- **Check step_results**: The `step_results` array shows which step failed and why
- **Validate inputs**: Ensure initial_input matches the first capsule's input schema
- **Handle failures gracefully**: Workflows stop at the first failure, so design with error recovery in mind

### 4. Performance

- **Minimize translator usage**: Only use translators when necessary, as they add LLM processing time
- **Optimize workflow length**: Longer workflows take more time and have more failure points
- **Cache results**: If possible, cache intermediate results for debugging

### 5. Debugging

- **Use step_results**: The `step_results` array provides visibility into each step's execution
- **Check individual capsules**: Test each capsule independently before using in a workflow
- **Verify schemas**: Ensure you understand the input/output schemas of all capsules in your workflow

## Troubleshooting

### Workflow Fails at First Step

- **Check initial_input**: Verify it matches the first capsule's input schema
- **Validate capsule name**: Ensure the capsule is registered in `orchestrator/config.yaml`
- **Check capsule logs**: Review the orchestrator logs for detailed error messages

### Translator Fails

- **Verify target_capsule**: Ensure `target_capsule` in translator_instructions matches the capsule name
- **Check schema compatibility**: Verify the source output can be transformed to match target input
- **Review instructions**: Make sure transformation instructions are clear and achievable
- **Test translator independently**: Call the translator capsule directly to debug transformation issues

### Workflow Returns Partial Results

- **Check step_results**: Identify which step failed
- **Review error messages**: Each step_result contains an `error` field with details
- **Verify intermediate outputs**: Check that each step's output is valid before passing to the next step

## Advanced Topics

### Schema Validation

The workflow capsule validates:
- Workflow JSON structure
- All referenced capsules exist in the orchestrator registry
- Input/output schemas are checked by individual capsules

### File Handling

If capsules in your workflow handle files:
- Files are passed through the orchestrator's file management system
- File paths in outputs are automatically handled
- The translator can handle file references in transformations

### Orchestrator Integration

The workflow capsule uses the orchestrator's HTTP API:
- Endpoint: `POST /execute` for executing capsules
- Endpoint: `GET /capsules/{name}/schema` for fetching schemas (used by translator)
- All capsules are executed through the orchestrator, maintaining isolation

## Future Enhancements

Planned features (not yet implemented):
- Branching/conditional workflows
- Parallel step execution
- Workflow visualization
- Workflow validation against capsule schemas
- Advanced translation strategies

## See Also

- [README.md](README.md) - General AOD system documentation
- [ORCHESTRATOR.md](ORCHESTRATOR.md) - Orchestrator documentation
- [HANDOFF.md](HANDOFF.md) - Inter-capsule communication documentation
