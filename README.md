# Agent-On-Demand (AOD) Standard

**A Specification for Containerized, AI-Augmented Micro-Services.**

---

## 1. Overview

The **Agent-On-Demand (AOD)** is an architectural pattern for "Just-in-Time" AI agents. In this Docker-native iteration, every Agent is a **Capsule**: a self-contained, ephemeral Docker image. The philosophy is **Software First, AI Second**, emphasizing the creation of narrowly-scoped agents with strict validation through software checks.

### **The First Philosophy: "Software First, AI Second"**

* **Scoping:** Every capsule is a piece of software relying on an AI agent to perform a narrowly-scoped, well-defined task.
* **Software-First:**
    * **Rigidity:** Traditional software is used whenever possible.
    * **Flexibility:** Each capsule's logic is called from a Python file, but any software tools may be used from this entry point.
* **AI-Second:**
    * **Expressivity:** When the *how* of a task is hard to define in code but the instructions for completing it with a given set of tools are simple to follow, an AI agent with tool-calling ability is used.
    * **Strict Scoping:** Each capsule does one task, and the AI agent doing the task is given only the permissions needed to complete it.
    * **Decomposing Complex Tasks:** As well as its MCP server the AI agent is given a restricted list of functions it may call, corresponding to handing off subtasks to other capsules. Naturally, complex problems get decomposed into simpler ones.



### Logic-IO Isolation

* **Encapsulation:** Every capsule contains its own OS, dependencies, and Model Context Protocol (MCP) servers.
* **Separation of Concerns:**
    * **The Bridge (`run.py`):** Handles the infrastructure layer (File I/O, finishing tasks).
    * **The Logic (`src/`):** Handles the intelligence. It accepts pure data and returns pure data.
* **I/O Safety:** Input and Output are handled via a **Shared Volume mount**, strictly separating data (files) from logging (stdout/stderr). Each container also has a **Workspace**.

---

## 2. The Capsule Specification

A capsule is a directory that must include a `Dockerfile`. The Runtime builds/runs this container to execute the task.

```text
/my-agent-capsule
├── Dockerfile          # Environment setup.
├── agent.yaml          # Configuration file for the agent detailing which model(s) to use
├── tools.yaml          # Configuration file for the visible capsule function calls this agent can make
├── schema.json         # Contract: I/O validation (Types & File Formats).
├── run.py              # THE BRIDGE: Manages /io file operations and validation.
└── /src                # THE LOGIC: Capsule-specific code.
    ├── main.py         # Entry Point: Contains the 'execute' function.
    ├── /utils          # [OPTIONAL] Helper functions/additional logic outside of main.py
    ├── /mcp_servers    # [OPTIONAL] Local Tools: MCP server implementations.
    └── /ai
        ├── system.md   # Persona: The system prompt for this agent.
        └── task.md     # Template: The template detailing how the AI agent is to solve the given task.

```

---

## 3. I/O Data Contracts & File Handling

To ensure reliability, capsules communicate via a strict contract defined in `schema.json`. Data exchange is divided into **Payload Data** (Primitives) and **Artifact Data** (Files).

### 3.1 The `schema.json` Contract

The `schema.json` file defines the expected input and output structure. The `run.py` bridge validates incoming data against this schema before the AI logic (`src/main.py`) ever sees it.

**Supported Data Types:**

* **Primitives:** `int`, `float`, `string`, `bool`.
* **Structured:** `dict` (nested objects), `list` (arrays).
* **File References:** Special string patterns denoting file paths in the shared volume.

### 3.2 Handling Primitives (Ints, Strings, Dicts)

Primitive data is passed directly within the JSON payload.

* **Input:** The Orchestrator writes a JSON file to the input volume. `run.py` parses this and passes it as a native Python dictionary to `src/main.py`.
* **Output:** The `execute` function in `src/main.py` returns a native dictionary. `run.py` serializes this to JSON.

### 3.3 Handling Files (PDFs, Images, CSVs)

Large payloads or binary formats are **never** embedded in the JSON. Instead, they are handled via the Shared Volume (`/io`).

1. **Input Files:** The Orchestrator places the file (e.g., `data.csv`) into the capsule's mounted `/io/input` directory. The JSON payload contains the **filename** (string).
2. **Processing:** The logic in `src/main.py` reads the filename from the input dict, locates the file at `/io/input/<filename>`, and processes it.
3. **Output Files:** If the capsule generates a file (e.g., `report.pdf`), it writes the file to `/io/output/report.pdf` and returns the **filename** in its return dictionary.

#### Example `schema.json`:

```json
{
  "input": {
    "type": "object",
    "properties": {
      "retry_count": { "type": "integer" },
      "user_prompt": { "type": "string" },
      "source_document": { 
        "type": "string", 
        "format": "file_path", 
        "description": "Path to a PDF in the /io/input volume"
      }
    },
    "required": ["user_prompt", "source_document"]
  },
  "output": {
    "type": "object",
    "properties": {
      "summary_text": { "type": "string" },
      "processed_document": { 
        "type": "string", 
        "description": "Filename of the cleaned text file generated in /io"
      }
    }
  }
}

```

---

## 4. Capsules Calling Capsules

A single **Orchestrator** exists outside of any capsule and manages the creation, deletion, and message passing of information between capsules.

### 4.1 The Handoff Mechanism

A capsule cannot directly network with another capsule. Instead, it "calls" another capsule by returning a specific **Handoff Request** to the Orchestrator.

1. **The Call:** Capsule A (The Caller) determines it needs help. It sends an HTTP request to the orchestrator with a structured object requesting `Capsule B` with specific arguments (e.g., `{"target": "Capsule B", "args": {"input_image": "graph.png"}}`).
2. **The Orchestrator:** * Acknowledges the receipt of this call. Capsule A waits until it gets the result back.
* Reads the arguments.
* **Moves Files:** If an argument references a file in Capsule A's `/io/handoff/outgoing`, the Orchestrator copies that file to Capsule B's `/io/input` mount.
* Spins up Capsule B.


3. **The Return:**
* Capsule B finishes and outputs data (and potentially new files in its `/io/output`).
* The Orchestrator copies the output files back to Capsule A's `/io/handoff/incoming`.
* The Orchestrator injects the results back into Capsule A, which resumes execution.

**For more details on the handoff mechanism, see `HANDOFF.md`**
