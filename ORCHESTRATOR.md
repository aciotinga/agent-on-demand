# ORCHESTRATOR.md

**Specification for the AOD Central Management Unit**

## 1. Overview

The Orchestrator is the external management entity responsible for the lifecycle of all AOD Capsules. It operates outside the containerized environments and manages the creation, deletion, and message passing of information between capsules. It acts as the bridge between the external world and the ephemeral agentic runtimes.

## 2. Core Responsibilities

The Orchestrator has three primary functions:

1. **Lifecycle Management:** Spinning up and tearing down Docker containers for specific capsules.
2. **I/O Management:** Handling file system operations to ensure strict data isolation and correct file placement in mounted volumes.
3. **Inter-Capsule Routing:** Acting as the HTTP server that accepts "Handoff Requests" from running capsules and routes them to new capsule instances.

---

## 3. The Execution Lifecycle (Single Capsule)

When a task is initiated, the Orchestrator performs the following sequence:

### 3.1. Preparation

1. **Volume Creation:** Create a dedicated shared volume or host directory for the capsule session.
2. **Input File Placement:** If the request includes files (e.g., `data.csv`), copy them into the designated `/io/input` directory on the host that will be mounted to the container.
3. **Payload Construction:** Write the input JSON file (containing primitives and filenames) to the input volume.

### 3.2. Execution

1. **Container Launch:** Run the specific Capsule Docker image.
2. **Volume Mount:** Mount the prepared directory to `/io` inside the container.
3. **Wait:** Monitor the execution. The Orchestrator waits until the capsule finishes execution or sends a Handoff Request.

### 3.3. Teardown & Retrieval

1. **Output Retrieval:** Once the capsule exits, read the JSON output from the volume.
2. **File Retrieval:** If the output JSON references files, locate them in `/io/output`.
3. **Cleanup:** Destroy the ephemeral container.

---

## 4. Inter-Capsule Communication (The Handoff)

Capsules cannot network directly with each other. The Orchestrator brokers all communication via an HTTP server that running capsules can access.

### 4.1. Handoff Request Syntax

The Orchestrator must listen for HTTP POST requests containing the following JSON structure:

```json
{
  "target": "Capsule Name",
  "args": {
    "argument_key": "value",
    "file_key": "filename.ext" 
  }
}

```

*Ref: Capsule A sends a structured object requesting a target with specific arguments.*

### 4.2. Handoff Logic Flow

When the Orchestrator receives a Handoff Request from **Capsule A** targeting **Capsule B**:

1. **Acknowledge:** Confirm receipt of the call. Capsule A pauses/waits.
2. **Analyze Arguments:** Parse the `args` dictionary.
3. **File Movement (Outgoing):**
* Check if any argument value references a file in Capsule A's `/io/handoff/outgoing`.
* **Action:** Copy identified files from `A:/io/handoff/outgoing` to `B:/io/input`.


4. **Execute Capsule B:** Spin up Capsule B using the standard Execution Lifecycle (Section 3).
5. **File Movement (Incoming):**
* Upon Capsule B's completion, identify output files in `B:/io/output`.
* **Action:** Copy these files to `A:/io/handoff/incoming`.


6. **Result Injection:** Pass the JSON results from Capsule B back to Capsule A as the HTTP response, allowing Capsule A to resume execution.

---

## 5. File System Architecture

The Orchestrator must maintain a strict directory structure for the shared volume mounted to `/io`.

### 5.1. Directory Structure

For every active capsule instance, the Orchestrator manages the following paths:

| Host Path (Managed by Orch) | Container Mount Path | Purpose |
| --- | --- | --- |
| `.../inputs/` | `/io/input/` | Location for input files (PDFs, CSVs) sourced from user or other capsules. |
| `.../outputs/` | `/io/output/` | Location where the capsule writes generated files. |
| `.../handoffs/out/` | `/io/handoff/outgoing/` | Staging area for files the capsule wants to send to a sub-capsule. |
| `.../handoffs/in/` | `/io/handoff/incoming/` | Receiving area for files returned by a sub-capsule. |

### 5.2. File Transfer Rules

* **No Embedding:** Binary data must never be embedded in JSON payloads; only file paths/names are allowed.
* **Name Resolution:** The JSON payload contains the *filename* (string). The Orchestrator ensures the actual file exists at `/io/input/<filename>` before the capsule logic (`src/main.py`) attempts to read it.

---

## 6. Implementation Checklist

To implement this Orchestrator, the following components are required:

* [ ] **Docker Client:** To interface with the Docker daemon for spinning up/down `Capsule` images.
* [ ] **HTTP Server:** To accept `POST` requests from running capsules (The Handoff).
* [ ] **File Manager:** To copy/move files between the host file system and the specific volume directories (`input`, `output`, `handoff`).
* [ ] **JSON Parser:** To read/write the payload contracts defined in `schema.json`.