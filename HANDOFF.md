### 1. The Handoff Architecture

The AOD architecture relies on a single **Orchestrator** that exists outside all capsules. This Orchestrator manages the lifecycle of capsules (creation/deletion) and acts as the message bus for inter-capsule communication.

The protocol follows a strictly defined **Call**, **Process**, and **Return** cycle:

### 2. The Handoff Mechanism (Step-by-Step)

#### Step 1: The Call (Request)

When Capsule A (the Caller) requires assistance, it cannot call Capsule B directly. Instead, it issues a **Handoff Request** via an HTTP request to the Orchestrator.

* **Action:** Capsule A pauses and waits for the result.
* **File Prep:** If the request involves files, Capsule A must place them in its `/io/handoff/outgoing` directory.

**Request Syntax (JSON Object):**
The request is a structured object specifying the target agent and arguments.

```json
{
  "target": "Capsule B",
  "args": {
    "input_image": "graph.png",
    "param_2": "value"
  }
}

```

#### Step 2: The Orchestrator (Mediation)

The Orchestrator receives the HTTP request and performs the bridging operations:

1. **Read Arguments:** It parses the `target` and `args` from the JSON payload.
2. **File Movement (Outgoing):** If an argument references a file (e.g., `graph.png` located in Capsule A's `/io/handoff/outgoing`), the Orchestrator copies that file into Capsule B's `/io/input` mount.
3. **Execution:** The Orchestrator spins up Capsule B to process the task.

#### Step 3: The Return (Response)

Once Capsule B completes its logic:

1. **Output Generation:** Capsule B writes its data and places any generated files into its own `/io/output` directory.
2. **File Movement (Incoming):** The Orchestrator copies these output files from Capsule B's `/io/output` into Capsule A's `/io/handoff/incoming` directory.
3. **Resume:** The Orchestrator injects the results back into Capsule A, allowing it to resume execution with the new data.

---

### 3. File System Flow Summary

The protocol relies heavily on specific volume mounts to maintain isolation while enabling file transfer.

| Stage | Source Location | Destination Location | Action by |
| --- | --- | --- | --- |
| **Request** | Capsule A: `/io/handoff/outgoing` | Capsule B: `/io/input` | Orchestrator copies files |
| **Response** | Capsule B: `/io/output` | Capsule A: `/io/handoff/incoming` | Orchestrator copies files |

---

### 4. JSON Syntax Definition

The handoff relies on a specific JSON structure for the initial request.

**Handoff Request Object:**

```json
{
  "target": "<Name of Target Capsule>",
  "args": {
    "<argument_key>": "<value_or_filename>"
  }
}

```

* **target**: String. The identifier of the capsule to be called (e.g., `"Capsule B"`).
* **args**: Dictionary. Key-value pairs corresponding to the input schema of the target capsule. If a value is a filename, it implies the file exists in the caller's outgoing directory.