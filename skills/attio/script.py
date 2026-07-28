import os
import json
import httpx

BASE = "https://api.attio.com/v2"


def _safe_int(v, default):
    """Coerce v to int, falling back to default for None, "", lists, dicts,
    or non-numeric strings. Agents commonly emit null for unset numeric
    fields; dict.get(key, default) only returns the default for MISSING keys,
    not explicit nulls, so this normalizes both cases."""
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def api(token, method, path, body=None, params=None, timeout=20):
    with httpx.Client(timeout=timeout) as c:
        r = c.request(
            method,
            f"{BASE}/{path.lstrip('/')}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=body,
            params=params,
        )
        if r.status_code >= 400:
            detail = ""
            try:
                j = r.json()
                detail = j.get("message") or j.get("error", {}).get("message") or json.dumps(j)[:400]
            except Exception:
                detail = r.text[:400]
            raise Exception(f"Attio API {r.status_code} on {method} {path}: {detail}")
        return r.json() if r.content else {}


def do_list_objects(token):
    data = api(token, "GET", "objects")
    objs = data.get("data", []) if isinstance(data, dict) else data
    return {
        "objects": [
            {
                "id": (o.get("id") or {}).get("object_id"),
                "slug": o.get("api_slug") or o.get("slug"),
                "singular": o.get("singular_noun"),
                "plural": o.get("plural_noun"),
            }
            for o in objs
        ],
        "count": len(objs),
    }


def do_list_records(token, obj, limit, offset):
    body = {"limit": min(max(limit, 1), 500), "offset": max(offset, 0)}
    data = api(token, "POST", f"objects/{obj}/records/query", body=body)
    records = data.get("data", []) if isinstance(data, dict) else data
    return {"records": records, "count": len(records), "object": obj}


def do_search_records(token, obj, query, limit):
    """Fuzzy search via Attio's dedicated /v2/objects/records/search endpoint
    (beta). Matches names, domains, emails, phone numbers, social handles on
    people/companies, and labels on other objects — mirrors Attio's in-product
    search. Verified against
    https://docs.attio.com/rest-api/endpoint-reference/records/search-records.

    Previous implementation used the records/query endpoint with a hard-coded
    `{"name": {"$contains": query}}` filter, which failed for the `people`
    object (where `name` is a personal-name slot needing nested field
    references) and for any custom object that doesn't have a `name`
    attribute. The dedicated search endpoint handles all those cases natively."""
    if not obj:
        raise Exception("object is required for search_records")
    if query is None:
        query = ""
    body = {
        "query": query,
        "objects": [obj],
        # `request_as: {workspace: true}` returns everything visible at the
        # workspace level; agents typically want broad recall, not per-user
        # scoping. The user_management:read scope is required by Attio for
        # the {workspace: true} variant.
        "request_as": {"workspace": True},
        "limit": min(max(limit, 1), 25),  # Attio caps at 25 for this endpoint
    }
    data = api(token, "POST", "objects/records/search", body=body)
    records = data.get("data", []) if isinstance(data, dict) else data
    return {"records": records, "count": len(records), "query": query, "object": obj}


def do_get_record(token, obj, record_id):
    data = api(token, "GET", f"objects/{obj}/records/{record_id}")
    return {"record": data.get("data", data), "object": obj, "record_id": record_id}


def do_create_record(token, obj, values):
    if not values:
        raise Exception("values is required for create_record")
    data = api(token, "POST", f"objects/{obj}/records", body={"data": {"values": values}})
    rec = data.get("data", data)
    return {"ok": True, "record": rec, "object": obj}


def do_update_record(token, obj, record_id, values):
    if not values:
        raise Exception("values is required for update_record")
    data = api(token, "PATCH", f"objects/{obj}/records/{record_id}", body={"data": {"values": values}})
    rec = data.get("data", data)
    return {"ok": True, "record": rec, "object": obj, "record_id": record_id}


def do_list_lists(token):
    data = api(token, "GET", "lists")
    lists = data.get("data", []) if isinstance(data, dict) else data
    return {
        "lists": [
            {
                "id": (l.get("id") or {}).get("list_id"),
                "slug": l.get("api_slug"),
                "name": l.get("name"),
                "parent_object": l.get("parent_object"),
            }
            for l in lists
        ],
        "count": len(lists),
    }


def do_list_entries(token, list_ref, limit, offset):
    body = {"limit": min(max(limit, 1), 500), "offset": max(offset, 0)}
    data = api(token, "POST", f"lists/{list_ref}/entries/query", body=body)
    entries = data.get("data", []) if isinstance(data, dict) else data
    return {"entries": entries, "count": len(entries), "list": list_ref}


def do_add_record_to_list(token, list_ref, obj, record_id, values):
    if not list_ref:
        raise Exception("list is required for add_record_to_list")
    if not record_id:
        raise Exception("record_id is required for add_record_to_list")
    if not obj:
        raise Exception("object is required for add_record_to_list (the parent_object slug or id of the record being added — e.g. 'people', 'companies', or a custom object)")
    # Attio's POST /v2/lists/{list}/entries requires parent_object + parent_record_id + entry_values
    # (verified against https://docs.attio.com/rest-api/endpoint-reference/entries/create-an-entry-add-record-to-list)
    payload = {"data": {"parent_object": obj, "parent_record_id": record_id, "entry_values": values or {}}}
    data = api(token, "POST", f"lists/{list_ref}/entries", body=payload)
    return {"ok": True, "entry": data.get("data", data), "list": list_ref, "object": obj, "record_id": record_id}


def do_list_tasks(token, limit, offset):
    params = {"limit": min(max(limit, 1), 500), "offset": max(offset, 0)}
    data = api(token, "GET", "tasks", params=params)
    tasks = data.get("data", []) if isinstance(data, dict) else data
    return {"tasks": tasks, "count": len(tasks)}


def do_create_task(token, content, assignees, deadline_at, record_id):
    if not content:
        raise Exception("content is required for create_task")
    task_data = {
        "content": content,
        "format": "plaintext",
        "is_completed": False,
    }
    if deadline_at:
        task_data["deadline_at"] = deadline_at
    if assignees:
        task_data["assignees"] = [{"referenced_actor_type": "workspace-member", "referenced_actor_id": a} for a in assignees]
    if record_id:
        task_data["linked_records"] = [{"target_record_id": record_id}]
    data = api(token, "POST", "tasks", body={"data": task_data})
    return {"ok": True, "task": data.get("data", data)}


def do_complete_task(token, task_id):
    if not task_id:
        raise Exception("task_id is required for complete_task")
    data = api(token, "PATCH", f"tasks/{task_id}", body={"data": {"is_completed": True}})
    return {"ok": True, "task": data.get("data", data), "task_id": task_id}


def do_list_notes(token, obj, record_id, limit, offset):
    """List notes. Optional filters: object slug + record_id (both required together
    to scope to a specific record's notes per Attio's API). When omitted, returns
    notes across the workspace."""
    params = {"limit": min(max(limit, 1), 50), "offset": max(offset, 0)}
    if obj and record_id:
        params["parent_object"] = obj
        params["parent_record_id"] = record_id
    elif obj or record_id:
        raise Exception("To filter notes by record, provide BOTH object and record_id (Attio's API requires the pair).")
    data = api(token, "GET", "notes", params=params)
    notes = data.get("data", []) if isinstance(data, dict) else data
    return {"notes": notes, "count": len(notes)}


def do_get_note(token, note_id):
    if not note_id:
        raise Exception("note_id is required for get_note")
    data = api(token, "GET", f"notes/{note_id}")
    return {"note": data.get("data", data), "note_id": note_id}


def do_create_note(token, obj, record_id, title, content):
    if not obj:
        raise Exception("object is required for create_note (the parent object slug or id — e.g. 'people', 'companies', or a custom object)")
    if not record_id:
        raise Exception("record_id is required for create_note")
    if not content:
        raise Exception("content is required for create_note")
    payload = {
        "data": {
            "parent_object": obj,
            "parent_record_id": record_id,
            "title": title or "Note",
            "content": content,
            "format": "markdown",
        }
    }
    data = api(token, "POST", "notes", body=payload)
    return {"ok": True, "note": data.get("data", data), "record_id": record_id, "object": obj}


# ─── Workspace members ───

def do_list_workspace_members(token):
    data = api(token, "GET", "workspace_members")
    members = data.get("data", []) if isinstance(data, dict) else data
    return {
        "members": [
            {
                "id": (m.get("id") or {}).get("workspace_member_id"),
                "email": m.get("email_address"),
                "first_name": m.get("first_name"),
                "last_name": m.get("last_name"),
                "access_level": m.get("access_level"),
            }
            for m in members
        ],
        "count": len(members),
    }


def _first_workspace_member_id(token):
    """Used by create_comment when author_id isn't supplied — Attio requires an author
    on every comment, and the agent shouldn't have to know its own workspace_member_id."""
    members = do_list_workspace_members(token).get("members", [])
    if not members:
        raise Exception("No workspace members found — cannot resolve a default author")
    return members[0]["id"]


# ─── Comments + threads ───

def do_list_threads(token, record_id, obj, entry_id, list_ref, limit, offset):
    params = {"limit": min(max(limit, 1), 500), "offset": max(offset, 0)}
    if record_id and obj:
        params["record_id"] = record_id
        params["object"] = obj
    if entry_id and list_ref:
        params["entry_id"] = entry_id
        params["list"] = list_ref
    data = api(token, "GET", "threads", params=params)
    threads = data.get("data", []) if isinstance(data, dict) else data
    return {"threads": threads, "count": len(threads)}


def do_get_thread(token, thread_id):
    if not thread_id:
        raise Exception("thread_id is required for get_thread")
    data = api(token, "GET", f"threads/{thread_id}")
    return {"thread": data.get("data", data), "thread_id": thread_id}


def do_create_comment(token, thread_id, record_id, obj, content, author_id):
    if not content:
        raise Exception("content is required for create_comment")
    if not thread_id and not (record_id and obj):
        raise Exception("Provide either thread_id (post to existing thread) or record_id + object (start a new thread on a record)")
    resolved_author = author_id or _first_workspace_member_id(token)
    comment_data = {
        "content": content,
        "format": "plaintext",
        "author": {"type": "workspace-member", "id": resolved_author},
    }
    if thread_id:
        comment_data["thread_id"] = thread_id
    else:
        # New thread on a record. Per Attio's POST /v2/comments contract, the inline
        # new-thread shape uses a `record: {record_id, object_id}` envelope (and
        # `entry: {entry_id, list_id}` for list entries) — NOT `parent_object` /
        # `parent_record_id`. Verified against
        # https://docs.attio.com/rest-api/endpoint-reference/comments/create-a-comment
        # (response shape shows `record.object_id` and `record.record_id`).
        comment_data["record"] = {"record_id": record_id, "object_id": obj}
    data = api(token, "POST", "comments", body={"data": comment_data})
    return {"ok": True, "comment": data.get("data", data)}


# ─── Meetings + call recordings ───

def do_list_meetings(token, linked_record_id, linked_object, participants, limit, cursor):
    params = {"limit": min(max(limit, 1), 200)}
    if cursor:
        params["cursor"] = cursor
    if linked_record_id:
        params["linked_record_id"] = linked_record_id
    if linked_object:
        params["linked_object"] = linked_object
    if participants:
        # Cast each element to str before join — an agent might emit numeric
        # workspace member IDs in the list, which would TypeError on join.
        if isinstance(participants, list):
            params["participants"] = ",".join(str(p) for p in participants if p)
        else:
            params["participants"] = str(participants)
    data = api(token, "GET", "meetings", params=params)
    meetings = data.get("data", []) if isinstance(data, dict) else data
    return {
        "meetings": meetings,
        "count": len(meetings),
        "next_cursor": data.get("next_cursor") if isinstance(data, dict) else None,
    }


def do_list_call_recordings(token, meeting_id, limit, cursor):
    if not meeting_id:
        raise Exception("meeting_id is required for list_call_recordings (recordings are nested under meetings)")
    params = {"limit": min(max(limit, 1), 200)}
    if cursor:
        params["cursor"] = cursor
    data = api(token, "GET", f"meetings/{meeting_id}/call_recordings", params=params)
    recordings = data.get("data", []) if isinstance(data, dict) else data
    return {
        "recordings": recordings,
        "count": len(recordings),
        "meeting_id": meeting_id,
        "next_cursor": data.get("next_cursor") if isinstance(data, dict) else None,
    }


def do_get_call_recording(token, recording_id):
    """Returns the recording with its transcript inline (per Attio's call_recordings response shape)."""
    if not recording_id:
        raise Exception("recording_id is required for get_call_recording")
    data = api(token, "GET", f"call_recordings/{recording_id}")
    return {"recording": data.get("data", data), "recording_id": recording_id}


# ─── Files ───

def do_list_files(token, obj, record_id, storage_provider, parent_folder_id, limit, cursor):
    params = {"limit": min(max(limit, 1), 200)}
    if cursor:
        params["cursor"] = cursor
    if obj:
        params["object"] = obj
    if record_id:
        params["record_id"] = record_id
    if storage_provider:
        params["storage_provider"] = storage_provider
    if parent_folder_id:
        params["parent_folder_id"] = parent_folder_id
    data = api(token, "GET", "files", params=params)
    files = data.get("data", []) if isinstance(data, dict) else data
    return {
        "files": files,
        "count": len(files),
        "next_cursor": data.get("next_cursor") if isinstance(data, dict) else None,
    }


def do_get_file(token, file_id):
    if not file_id:
        raise Exception("file_id is required for get_file")
    data = api(token, "GET", f"files/{file_id}")
    return {"file": data.get("data", data), "file_id": file_id}


try:
    token = os.environ["ATTIO_ACCESS_TOKEN"]
    inp = json.loads(os.environ.get("INPUT_JSON", "{}"))
    action = inp.get("action", "")
    obj = inp.get("object", "")
    record_id = inp.get("record_id", "")
    values = inp.get("values", {}) or {}
    list_ref = inp.get("list", "")
    # Use _safe_int — int() would crash on null/list/dict/non-numeric strings.
    # Agents often emit `null` for unset numeric fields.
    limit = _safe_int(inp.get("limit"), 25)
    offset = _safe_int(inp.get("offset"), 0)
    query = inp.get("query", "")
    content = inp.get("content", "")
    title = inp.get("title", "")
    assignees = inp.get("assignees", []) or []
    deadline_at = inp.get("deadline_at", "")
    task_id = inp.get("task_id", "")
    thread_id = inp.get("thread_id", "")
    entry_id = inp.get("entry_id", "")
    author_id = inp.get("author_id", "")
    meeting_id = inp.get("meeting_id", "")
    recording_id = inp.get("recording_id", "")
    file_id = inp.get("file_id", "")
    note_id = inp.get("note_id", "")
    storage_provider = inp.get("storage_provider", "")
    parent_folder_id = inp.get("parent_folder_id", "")
    cursor = inp.get("cursor", "")
    linked_record_id = inp.get("linked_record_id", "") or record_id
    linked_object = inp.get("linked_object", "") or obj
    participants = inp.get("participants", []) or []

    if action == "list_objects":
        result = do_list_objects(token)
    elif action == "list_records":
        result = do_list_records(token, obj, limit, offset)
    elif action == "search_records":
        result = do_search_records(token, obj, query, limit)
    elif action == "get_record":
        result = do_get_record(token, obj, record_id)
    elif action == "create_record":
        result = do_create_record(token, obj, values)
    elif action == "update_record":
        result = do_update_record(token, obj, record_id, values)
    elif action == "list_lists":
        result = do_list_lists(token)
    elif action == "list_entries":
        result = do_list_entries(token, list_ref, limit, offset)
    elif action == "add_record_to_list":
        result = do_add_record_to_list(token, list_ref, obj, record_id, values)
    elif action == "list_tasks":
        result = do_list_tasks(token, limit, offset)
    elif action == "create_task":
        result = do_create_task(token, content, assignees, deadline_at, record_id)
    elif action == "complete_task":
        result = do_complete_task(token, task_id)
    elif action == "create_note":
        result = do_create_note(token, obj, record_id, title, content)
    elif action == "list_notes":
        result = do_list_notes(token, obj, record_id, limit, offset)
    elif action == "get_note":
        result = do_get_note(token, note_id)
    elif action == "list_workspace_members":
        result = do_list_workspace_members(token)
    elif action == "list_threads":
        result = do_list_threads(token, record_id, obj, entry_id, list_ref, limit, offset)
    elif action == "get_thread":
        result = do_get_thread(token, thread_id)
    elif action == "create_comment":
        result = do_create_comment(token, thread_id, record_id, obj, content, author_id)
    elif action == "list_meetings":
        result = do_list_meetings(token, linked_record_id, linked_object, participants, limit, cursor)
    elif action == "list_call_recordings":
        result = do_list_call_recordings(token, meeting_id, limit, cursor)
    elif action == "get_call_recording":
        result = do_get_call_recording(token, recording_id)
    elif action == "list_files":
        result = do_list_files(token, obj, record_id, storage_provider, parent_folder_id, limit, cursor)
    elif action == "get_file":
        result = do_get_file(token, file_id)
    else:
        result = {"error": f"Unknown action: {action}"}

    print(json.dumps(result))

except KeyError as e:
    print(json.dumps({"error": f"Missing required env var: {e}"}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
