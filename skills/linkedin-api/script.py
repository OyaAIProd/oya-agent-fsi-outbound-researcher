import os
import json
import re
import httpx

UNIPILE_DSN = os.environ.get("UNIPILE_DSN", "").rstrip("/")
UNIPILE_API_KEY = os.environ.get("UNIPILE_API_KEY", "")
UNIPILE_ACCOUNT_ID = os.environ.get("UNIPILE_ACCOUNT_ID", "")


def _headers():
    return {
        "X-API-KEY": UNIPILE_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _params(extra=None):
    """Build query params — account_id always goes here."""
    p = {"account_id": UNIPILE_ACCOUNT_ID}
    if extra:
        p.update(extra)
    return p


def api_get(path, params=None, timeout=15):
    with httpx.Client(timeout=timeout) as c:
        r = c.get(f"{UNIPILE_DSN}/{path}", headers=_headers(), params=_params(params))
        r.raise_for_status()
        return r.json()


def api_post_json(path, body=None, params=None, timeout=15):
    """POST with JSON body."""
    with httpx.Client(timeout=timeout) as c:
        r = c.post(f"{UNIPILE_DSN}/{path}", headers=_headers(), json=body or {}, params=_params(params))
        r.raise_for_status()
        return r.json() if r.content else {}


def api_post_form(path, data=None, params=None, timeout=15):
    """POST with multipart/form-data body (required by some Unipile endpoints like create_post)."""
    h = {"X-API-KEY": UNIPILE_API_KEY, "Accept": "application/json"}
    with httpx.Client(timeout=timeout) as c:
        r = c.post(
            f"{UNIPILE_DSN}/{path}",
            headers=h,
            files={k: (None, str(v)) for k, v in (data or {}).items()},
            params=_params(params),
        )
        r.raise_for_status()
        return r.json() if r.content else {}


# --- Helpers ---


def _strip_markdown(text):
    """Strip markdown formatting for platforms that don't support it (LinkedIn).
    Converts **bold** and *italic* to plain text."""
    import re
    # Remove bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Remove italic: *text* or _text_ (but not inside words like don't)
    text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    # Remove markdown links [text](url) -> text (url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    # Remove headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return text


# --- Actions ---


def do_get_me():
    data = api_get("api/v1/users/me")
    return {
        "name": (data.get("first_name", "") + " " + data.get("last_name", "")).strip(),
        "public_identifier": data.get("public_identifier", ""),
        "headline": data.get("headline", ""),
        "provider_id": data.get("provider_id", ""),
    }


def do_create_post(text):
    if not text or not text.strip():
        return {"error": "text is required for create_post"}
    clean_text = _strip_markdown(text.strip())
    data = api_post_form("api/v1/posts", {
        "account_id": UNIPILE_ACCOUNT_ID,
        "text": clean_text,
    })
    return {
        "created": True,
        "post_id": data.get("post_id", "") or data.get("id", ""),
    }


def _resolve_social_id(post_id):
    """Ensure we have a social_id URN. If given a numeric ID, fetch the post to get it."""
    pid = post_id.strip()
    if pid.startswith("urn:li:"):
        return pid
    # Numeric or internal ID — resolve via get_post
    data = api_get(f"api/v1/posts/{pid}")
    sid = data.get("social_id", "")
    if not sid:
        return pid  # fallback to what we have
    return sid


def do_get_post(post_id):
    if not post_id:
        return {"error": "post_id is required for get_post"}
    data = api_get(f"api/v1/posts/{post_id.strip()}")
    return {
        "post_id": data.get("id", ""),
        "social_id": data.get("social_id", ""),
        "text": data.get("text", ""),
        "author": data.get("author", {}),
        "share_url": data.get("share_url", ""),
        "comment_counter": data.get("comment_counter", 0),
        "reaction_counter": data.get("reaction_counter", 0),
    }


def do_comment(post_id, text):
    if not post_id:
        return {"error": "post_id is required for comment"}
    if not text or not text.strip():
        return {"error": "text is required for comment"}
    sid = _resolve_social_id(post_id)
    clean_text = _strip_markdown(text.strip())
    data = api_post_json(
        f"api/v1/posts/{sid}/comments",
        {"account_id": UNIPILE_ACCOUNT_ID, "text": clean_text},
    )
    return {
        "commented": True,
        "post_id": sid,
        "comment_id": data.get("comment_id", "") or data.get("id", ""),
    }


def do_react(post_id, reaction_type="like"):
    if not post_id:
        return {"error": "post_id is required for react"}
    sid = _resolve_social_id(post_id)
    # Unipile expects lowercase reaction types
    rt = reaction_type.lower() if reaction_type else "like"
    api_post_json(
        "api/v1/posts/reaction",
        {"account_id": UNIPILE_ACCOUNT_ID, "post_id": sid, "reaction_type": rt},
    )
    return {
        "reacted": True,
        "post_id": sid,
        "reaction_type": rt,
    }


def _normalize_identifier(identifier):
    """Accept a public identifier, a provider_id (ACo...), or any form of
    LinkedIn profile URL and return the bare identifier Unipile expects.

    The agent often passes a full/partial URL (e.g. ``linkedin.com/in/jane-doe``
    or ``https://www.linkedin.com/in/jane-doe/``). Passed through verbatim it
    becomes ``/api/v1/users/linkedin.com/in/jane-doe`` → HTTP 404. Extract the
    ``/in/<slug>`` segment, otherwise strip scheme/host/query so a clean slug
    or provider_id is left."""
    ident = (identifier or "").strip()
    if not ident:
        return ident
    m = re.search(r"/in/([^/?#]+)", ident)
    if m:
        return m.group(1)
    ident = re.sub(r"^https?://", "", ident, flags=re.I)
    ident = re.sub(r"^([a-z0-9-]+\.)?linkedin\.com/+", "", ident, flags=re.I)
    return ident.strip("/").split("?")[0].split("#")[0]


def do_get_user(identifier):
    if not identifier:
        return {"error": "identifier is required for get_user (username or profile URL)"}
    data = api_get(f"api/v1/users/{_normalize_identifier(identifier)}")
    return {
        "name": (data.get("first_name", "") + " " + data.get("last_name", "")).strip(),
        "public_identifier": data.get("public_identifier", ""),
        "headline": data.get("headline", ""),
        "provider_id": data.get("provider_id", ""),
        "follower_count": data.get("follower_count", 0),
    }


def do_send_connection(identifier, message=""):
    if not identifier:
        return {"error": "identifier is required for send_connection"}
    # First resolve provider_id
    user = do_get_user(identifier)
    if "error" in user:
        return user
    provider_id = user.get("provider_id", "")
    if not provider_id:
        return {"error": f"Could not resolve provider_id for {identifier}"}
    body = {
        "account_id": UNIPILE_ACCOUNT_ID,
        "provider_id": provider_id,
    }
    if message and message.strip():
        body["message"] = message.strip()[:300]
    api_post_json("api/v1/users/invite", body)
    return {
        "sent": True,
        "identifier": identifier.strip(),
        "provider_id": provider_id,
    }


def do_get_user_posts(identifier):
    if not identifier:
        return {"error": "identifier is required for get_user_posts"}
    # Unipile requires provider_id for listing posts, not public_identifier
    ident = identifier.strip()
    if not ident.startswith("ACo"):
        # Resolve provider_id from username
        user = do_get_user(ident)
        if "error" in user:
            return user
        pid = user.get("provider_id", "")
        if not pid:
            return {"error": f"Could not resolve provider_id for {ident}"}
        ident = pid
    data = api_get(f"api/v1/users/{ident}/posts")
    items = data.get("items", [])
    return {
        "posts": [
            {
                "post_id": p.get("social_id", "") or p.get("id", ""),
                "text": (p.get("text", "") or "")[:200],
                "author": p.get("author", {}),
                "share_url": p.get("share_url", ""),
                "reaction_counter": p.get("reaction_counter", 0),
                "comment_counter": p.get("comment_counter", 0),
            }
            for p in items[:20]
        ],
        "count": len(items),
    }


def do_search(keywords, category="posts"):
    if not keywords:
        return {"error": "keywords is required for search"}
    keywords = keywords.strip()
    # LinkedIn/Unipile rejects an oversized query with a 400 content_too_large that the
    # agent can't act on (it just sees "the provider rejected it"). Catch it here first
    # with a message the agent can actually use on its next turn. 700 chars is far past any
    # real keyword search; an ICP prospector cramming a giant boolean query into keywords
    # trips this. Encourages splitting into several narrower searches instead.
    if len(keywords) > 700:
        return {
            "error": (
                "Search query too long (" + str(len(keywords)) + " chars, max 700). LinkedIn "
                "rejects oversized queries. Narrow it: use fewer keywords, or split a broad "
                "boolean query into several smaller searches and combine the results."
            )
        }
    body = {
        "api": "classic",
        "category": category,
        "keywords": keywords,
    }
    data = api_post_json("api/v1/linkedin/search", body)
    items = data.get("items", [])
    if category == "posts":
        return {
            "results": [
                {
                    # Prefer social_id (URN) — it's what comment/react need directly
                    "post_id": p.get("social_id", "") or p.get("id", ""),
                    "text": (p.get("text", "") or "")[:200],
                    "author": p.get("author", {}),
                    "share_url": p.get("share_url", ""),
                    "reaction_counter": p.get("reaction_counter", 0),
                    "comment_counter": p.get("comment_counter", 0),
                }
                for p in items[:20]
            ],
            "count": data.get("paging", {}).get("total_count", len(items)),
        }
    else:
        return {
            "results": [
                {
                    "name": (p.get("first_name", "") + " " + p.get("last_name", "")).strip()
                    if "first_name" in p
                    else p.get("name", ""),
                    "public_identifier": p.get("public_identifier", ""),
                    "headline": p.get("headline", ""),
                    "provider_id": p.get("provider_id", ""),
                }
                for p in items[:20]
            ],
            "count": data.get("paging", {}).get("total_count", len(items)),
        }


# --- Main ---

try:
    if not UNIPILE_DSN or not UNIPILE_API_KEY:
        raise ValueError("Unipile API not configured. Contact the platform admin.")
    if not UNIPILE_ACCOUNT_ID:
        raise ValueError(
            "No LinkedIn account connected. Please reconnect your LinkedIn gateway."
        )

    inp = json.loads(os.environ.get("INPUT_JSON", "{}"))
    action = inp.get("action", "")

    if action == "get_me":
        result = do_get_me()
    elif action == "create_post":
        result = do_create_post(inp.get("text", ""))
    elif action == "get_post":
        result = do_get_post(inp.get("post_id", ""))
    elif action == "comment":
        result = do_comment(inp.get("post_id", ""), inp.get("text", ""))
    elif action == "react":
        result = do_react(inp.get("post_id", ""), inp.get("reaction_type", "LIKE"))
    elif action == "send_connection":
        result = do_send_connection(inp.get("identifier", ""), inp.get("message", ""))
    elif action == "get_user":
        result = do_get_user(inp.get("identifier", ""))
    elif action == "get_user_posts":
        result = do_get_user_posts(inp.get("identifier", ""))
    elif action == "search":
        result = do_search(inp.get("keywords", ""), inp.get("category", "posts"))
    else:
        result = {
            "error": f"Unknown action: {action}. Available: get_me, create_post, get_post, comment, react, send_connection, get_user, get_user_posts, search"
        }

    print(json.dumps(result))

except httpx.HTTPStatusError as e:
    status = e.response.status_code
    detail = ""
    body = {}
    try:
        body = e.response.json()
        detail = body.get("message", "") or str(body)
    except Exception:
        detail = e.response.text[:200]
    # A too-large payload/filter is user-actionable, not a transient API fault: tell the
    # agent to narrow the request rather than surfacing the raw provider envelope.
    if status in (400, 413) and isinstance(body, dict) and body.get("type") == "errors/content_too_large":
        print(
            json.dumps(
                {
                    "error": "LinkedIn rejected the request as too large. Narrow it: fewer "
                    "keywords or filters, or split a broad search into several smaller ones."
                }
            )
        )
    else:
        print(
            json.dumps(
                {
                    "error": f"LinkedIn API error {status}: {detail}"
                    if detail
                    else f"LinkedIn API error {status}"
                }
            )
        )
except Exception as e:
    print(json.dumps({"error": str(e)}))
