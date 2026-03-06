# Drafter AI — Stateful Document Editor

## Quick Overview

**Drafter** lets users iteratively edit documents with LLM help:
1. User requests a change → Agent proposes it (saved as **Draft** — non-destructive)
2. User asks for more changes → Agent builds on the Draft
3. User says "save" → Draft becomes permanent (creates **Revision**, increments **Document** version)

Notes:
- Drafts are persisted to the database when the agent calls a draft tool.
- The live Document is only updated when the Draft is applied.
- This project relies on LLM tool-calling (function calling) for `propose_update` / `propose_append`.
   If your provider/model does not support tool calls, the agent may respond in text but no Draft will be saved.

## Agent Graph

```mermaid
graph TD
    Start([Entry]) --> Agent["Agent Node<br/>(LLM + bind_tools)"]
    Agent --> ShouldContinue{"should_continue<br/>tool_calls present?"}
   ShouldContinue -->|Yes| Tools["Tools Node<br/>(propose_update / propose_append)"]
    ShouldContinue -->|No| End([END])
    Tools --> Agent
    
    style Agent fill:#e1f5ff
    style Tools fill:#f3e5f5
    style ShouldContinue fill:#fff3e0
    style End fill:#c8e6c9
```

The LLM is bound to the `propose_update` tool. When called, it saves the proposal as a Draft in the database.

For additive requests like “add more info about X”, the agent can use `propose_append` to safely append new material
to the existing Draft (or Document if no Draft exists), avoiding accidental overwrites.

## Agent Graph (Full Data Flow)

```mermaid
flowchart TB
   UserInput([User Input]) --> Interact["POST /documents/{id}/interact"]
   Interact --> AgentNode["Agent Node (LLM + Tools)"]
   AgentNode --> ShouldContinue{Tool Call?}
   ShouldContinue -- No --> End([End / Return Response])
   ShouldContinue -- Yes --> ToolsNode["Tools Node"]

   ToolsNode --> ProposeUpdate["propose_update\n(FULL document rewrite)\nNon-destructive"]
   ToolsNode --> ProposeAppend["propose_append\n(Append-only)\nNon-destructive"]

   ProposeUpdate --> DraftDB[(Draft Table)]
   ProposeAppend --> DraftDB

   DraftDB --> InteractResp["Response includes draft.content"]
   InteractResp --> ConfirmInput(["User confirms: save/apply/yes"])
   InteractResp --> MoreEdits(["User asks more edits"])
   MoreEdits --> Interact

   ConfirmInput --> Apply["POST /documents/{id}/apply-update\n(or confirmation in /interact)"]
   Apply --> ApplyDraft["apply_draft()"]
   ApplyDraft --> RevisionDB[(Revision Table)]
   ApplyDraft --> DocumentsDB[(Documents Table)]
   ApplyDraft --> DraftDeleted["Draft deleted"]
   DraftDeleted --> End:::endstyle

   classDef tool fill:#f3e5f5;
   class ProposeUpdate,ProposeAppend tool;
   classDef endstyle fill:#c8e6c9,stroke:#333,stroke-width:2;
```

## Three Core Models

| Model | Purpose | When Created | Deleted? |
|-------|---------|--------------|----------|
| **Document** | Live version (id, title, content, version) | First | Never |
| **Draft** | In-progress proposal | Agent calls `propose_update` / `propose_append` | On apply |
| **Revision** | Historical snapshot | When Draft is applied | Never |

## API Endpoints

```
POST   /documents/{id}/interact       → Run agent, iterate on draft
POST   /documents/{id}/apply-update   → Commit draft to document
GET    /documents/{id}/draft          → Fetch current draft
```

### Response shape

`POST /documents/{id}/interact` returns:
- `response`: the assistant-facing message
- `draft` (optional): the current working draft content (when a draft exists)

Clients should render `draft.content` as the “current proposed document” because it is the accumulated working state.

## How It Works: 3-Step Example

```
1. POST /documents/123/interact
   "Fix the grammar"
   → Draft created: "corrected text"
   → Response includes the latest Draft content

2. POST /documents/123/interact
   "Add more detail"
   → Agent reads Draft, adds detail
   → Draft updated: "corrected text + detail"
   → Response includes the updated Draft content

3. POST /documents/123/interact
   "Yes, save it"
   → Confirmed! apply_draft() called
   → Revision created (stores old content)
   → Document.version++ (v1 → v2)
   → Draft deleted
   → Response: "Changes saved. Document updated to version 2."

Confirmation detection is intentionally strict to avoid accidental applies. Prefer short confirmations like `save`, `apply`, or `yes`.
```

## Logging

All operations logged to console + `drafter.log`. Set `LOG_LEVEL=DEBUG` in `.env` for verbose output.

## Setup

```bash
pip install -r requirements.txt
# Configure .env (DATABASE_URL, OPENAI_API_KEY, LLM_PROVIDER, etc.)
uvicorn app.main:app --reload
```

### LLM Provider note

The agent workflow depends on tool binding. In this repo, **OpenAI is the supported/reliable provider for tool-calling**.
Ollama tool-calling support depends on the model + integration and may be unreliable; if tool calls are not emitted,
Draft updates won’t persist.

## Docker (DB + Ollama)

The included docker compose file starts:
- **Postgres** on `localhost:5432`
- **Ollama** on `localhost:11434`

```bash
docker compose up -d
```

Example `.env` values when using docker compose:
- `DATABASE_URL=postgresql+psycopg2://drafter:drafter@localhost:5432/drafter`

If using **OpenAI** (recommended for tool-calling):
- `LLM_PROVIDER=openai`
- `OPENAI_API_KEY=...`

If using **Ollama** (may not support tool calls for your model):
- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434`

Then run the API with:

```bash
uvicorn app.main:app --reload
```

Done. The agent always works on the **Draft**, so changes stack cumulatively until you confirm.

