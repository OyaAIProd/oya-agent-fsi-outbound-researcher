---
name: attio
display_name: "Attio"
description: "Read and write to your Attio CRM — search records, create people/companies, manage lists, tasks, and notes"
category: crm
icon: users
skill_type: sandbox
catalog_type: platform
requirements: "httpx>=0.25"
resource_requirements:
  - env_var: ATTIO_ACCESS_TOKEN
    name: "Attio Access Token"
    description: "OAuth access token from connecting Attio, or a personal API token from app.attio.com/settings/api"
tool_schema:
  name: attio
  description: "Read and write to your Attio CRM — search records, create people/companies, manage lists, tasks, and notes"
  parameters:
    type: object
    properties:
      action:
        type: "string"
        description: "Which operation to perform"
        enum:
          - list_objects
          - list_records
          - search_records
          - get_record
          - create_record
          - update_record
          - list_lists
          - list_entries
          - add_record_to_list
          - list_tasks
          - create_task
          - complete_task
          - create_note
          - list_notes
          - get_note
          - list_workspace_members
          - list_threads
          - get_thread
          - create_comment
          - list_meetings
          - list_call_recordings
          - get_call_recording
          - list_files
          - get_file
      object:
        type: "string"
        description: "Object slug (e.g. 'people', 'companies', 'deals') or object_id UUID — for list_records, search_records, get_record, create_record, update_record, create_note (sets the note's parent_object), list_notes (optional filter — pass with record_id to scope to one record's notes), add_record_to_list (Attio requires the parent object of the record being added), and create_comment when starting a new thread on a record"
        default: ""
      record_id:
        type: "string"
        description: "Record ID UUID — for get_record, update_record, add_record_to_list, create_note"
        default: ""
      query:
        type: "string"
        description: "Free-text fuzzy search query — for search_records"
        default: ""
      values:
        type: "object"
        description: "Attribute values map — for create_record, update_record, add_record_to_list. Each key is an attribute slug, each value follows Attio's value format (usually {value: ...} per slot)."
        default: {}
      list:
        type: "string"
        description: "List slug or list_id UUID — for list_entries, add_record_to_list"
        default: ""
      limit:
        type: "integer"
        description: "Max results (default 25, max 500) — for list_records, list_entries, list_tasks"
        default: 25
      offset:
        type: "integer"
        description: "Pagination offset — for list_records, list_entries, list_tasks"
        default: 0
      content:
        type: "string"
        description: "Body of the task or note — for create_task (plaintext), create_note (markdown), and create_comment (plaintext)"
        default: ""
      title:
        type: "string"
        description: "Note title — for create_note"
        default: ""
      assignees:
        type: "array"
        description: "Workspace member IDs (UUIDs) to assign — for create_task. Attio's tasks API requires workspace_member IDs, NOT emails. To convert an email to an ID, call list_workspace_members first and look up the `id` of the entry whose `email` matches."
        items:
          type: string
        default: []
      deadline_at:
        type: "string"
        description: "ISO 8601 deadline — for create_task (e.g. '2026-06-01T17:00:00Z')"
        default: ""
      task_id:
        type: "string"
        description: "Task ID UUID — for complete_task"
        default: ""
      thread_id:
        type: "string"
        description: "Thread ID UUID — for get_thread, create_comment (when posting to an existing thread)"
        default: ""
      author_id:
        type: "string"
        description: "Workspace member ID to attribute the comment to — for create_comment. If omitted, the skill auto-resolves to the first workspace member (cheap heuristic; pass an explicit id for production use). Call list_workspace_members to discover IDs."
        default: ""
      entry_id:
        type: "string"
        description: "List entry ID UUID — for list_threads (when filtering threads on a list entry, paired with `list`)"
        default: ""
      meeting_id:
        type: "string"
        description: "Meeting ID UUID — for list_call_recordings (recordings are nested under meetings)"
        default: ""
      recording_id:
        type: "string"
        description: "Call recording ID UUID — for get_call_recording. Returns the recording with its transcript inline."
        default: ""
      file_id:
        type: "string"
        description: "File ID UUID — for get_file"
        default: ""
      note_id:
        type: "string"
        description: "Note ID UUID — for get_note"
        default: ""
      storage_provider:
        type: "string"
        description: "Filter files by storage backend — for list_files. One of: attio, dropbox, box, google-drive, microsoft-onedrive"
        default: ""
      parent_folder_id:
        type: "string"
        description: "Filter files by parent folder — for list_files"
        default: ""
      cursor:
        type: "string"
        description: "Pagination cursor — for list_meetings, list_call_recordings, list_files. Use `next_cursor` from a prior response."
        default: ""
      linked_record_id:
        type: "string"
        description: "Filter meetings to those linked to a specific record — for list_meetings. Defaults to `record_id` if not set."
        default: ""
      linked_object:
        type: "string"
        description: "Filter meetings to those linked to records of a specific object — for list_meetings. Defaults to `object` if not set."
        default: ""
      participants:
        type: "array"
        description: "Filter meetings by participant emails — for list_meetings"
        items:
          type: string
        default: []
    required: [action]
---
# Attio

Read and write Attio CRM data: records (people, companies, custom objects), lists, entries, tasks, and notes.

## Discovery

- **list_objects** — Discover what objects exist in the workspace. Returns slugs ('people', 'companies', plus any custom objects) and their attributes. Use this first when you don't know the schema.
- **list_lists** — List all lists in the workspace.

## Records

- **list_records** — List records for an object. Provide `object` (slug or id), optionally `limit` and `offset`.
- **search_records** — Fuzzy search records across an object. Provide `object` and `query`.
- **get_record** — Fetch one record. Provide `object` and `record_id`.
- **create_record** — Create a new record. Provide `object` and `values` (e.g. `{"name": [{"value": "Acme Inc"}], "domains": [{"domain": "acme.com"}]}`).
- **update_record** — Patch attributes. Provide `object`, `record_id`, and `values`.

## Lists

- **list_entries** — List entries in a list. Provide `list` (slug or id).
- **add_record_to_list** — Add an existing record to a list. Provide `list`, `object` (the parent object slug of the record — e.g. 'people'), `record_id`, and optional `values` for entry-specific attributes.

## Tasks

- **list_tasks** — List tasks (open and closed).
- **create_task** — Provide `content` (plaintext, required). Optional: `assignees` (workspace member UUIDs — call list_workspace_members to resolve emails to IDs), `deadline_at` (ISO 8601), `record_id` (link to a record).
- **complete_task** — Mark a task done. Provide `task_id`.

## Notes

- **list_notes** — List notes. Pass `object` + `record_id` together to scope to one record's notes (Attio requires the pair). Omit both to list workspace-wide. Defaults: `limit` 10, max 50.
- **get_note** — Fetch one note with full content (markdown + plaintext). Provide `note_id`.
- **create_note** — Attach a note to a record. Provide `object` (parent object slug), `record_id`, `content` (markdown body), and optional `title`.

## Workspace members

- **list_workspace_members** — List all members of the connected Attio workspace. Useful for resolving `author_id` (for comments) and `assignees` (for tasks).

## Comments & threads

- **list_threads** — List comment threads on a record (provide `record_id` + `object`) or a list entry (provide `entry_id` + `list`).
- **get_thread** — Fetch a single thread with its comments. Provide `thread_id`.
- **create_comment** — Post a comment. Two flows:
  - **Existing thread**: provide `thread_id` and `content`.
  - **New thread on a record**: provide `record_id` + `object` and `content` (a new thread is created inline).
  - `author_id` is optional — if omitted, the skill picks the first workspace member as a default. For production, pass an explicit `author_id`.

## Meetings

- **list_meetings** — List meetings. Optional filters: `linked_record_id`, `linked_object`, `participants` (array of emails). Pagination uses `cursor` + `next_cursor`. Beta endpoint.

## Call recordings

- **list_call_recordings** — Recordings are nested under meetings. Provide `meeting_id`. Beta endpoint.
- **get_call_recording** — Fetch one recording. Provide `recording_id`. Returns the transcript inline.

## Files

- **list_files** — List files across the workspace. All filters optional: `object`, `record_id`, `storage_provider` (`attio` | `dropbox` | `box` | `google-drive` | `microsoft-onedrive`), `parent_folder_id`. Beta endpoint.
- **get_file** — Fetch one file's metadata (incl. download URL). Provide `file_id`.

## Tips

- Attio is a typed CRM — every attribute value follows a slot format. For text attributes use `[{"value": "..."}]`; for select attributes use `[{"option": "..."}]`. When in doubt, fetch a sample record first and mirror its shape.
- The `people` and `companies` objects are standard, but every workspace can add custom objects — always run `list_objects` first if you're not sure what's available.
- Meetings, call recordings, and files endpoints are currently **beta** on Attio's side. Response shapes may evolve; if a call returns an unexpected payload, surface the raw response to the user so we can iterate.
