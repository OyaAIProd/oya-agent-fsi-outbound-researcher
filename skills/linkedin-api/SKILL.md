---
name: linkedin-api
display_name: "LinkedIn API"
description: "Create posts, comment, react, send connections, search, and manage your LinkedIn presence via Unipile API"
category: social
icon: linkedin
skill_type: sandbox
catalog_type: platform
requirements: "httpx>=0.25"
resource_requirements:
  - env_var: UNIPILE_DSN
    name: "Unipile API Base URL"
    description: "Unipile REST API endpoint (auto-provided)"
  - env_var: UNIPILE_API_KEY
    name: "Unipile API Key"
    description: "Unipile API authentication key (auto-provided)"
  - env_var: UNIPILE_ACCOUNT_ID
    name: "Unipile Account ID"
    description: "Per-user Unipile account ID (auto-provided by gateway connection)"
config_schema:
  properties:
    posting_rules:
      type: text
      label: "Posting Rules"
      description: "Rules for how the LLM should create LinkedIn posts"
      placeholder: "- Keep posts between 150-300 words\n- Hook in the first line\n- Max 3 hashtags"
      group: rules
    safety_rules:
      type: text
      label: "Safety Rules"
      description: "Safety rules and constraints"
      placeholder: "- Always confirm with the user before posting\n- Never share confidential information"
      group: rules
tool_schema:
  name: linkedin_api
  description: "Create posts, comment, react, send connections, search, and manage your LinkedIn presence"
  parameters:
    type: object
    properties:
      action:
        type: "string"
        description: "Which operation to perform"
        enum: ['get_me', 'create_post', 'comment', 'react', 'send_connection', 'get_user', 'get_user_posts', 'search', 'get_post']
      text:
        type: "string"
        description: "Text content -- for create_post, comment"
        default: ""
      post_id:
        type: "string"
        description: "Post ID -- for comment, react, get_post. Accepts any format: numeric ID from search results, social_id URN, or share URL. Auto-resolves to the correct format."
        default: ""
      reaction_type:
        type: "string"
        description: "Reaction type -- for react"
        enum: ['like', 'celebrate', 'support', 'love', 'insightful', 'funny']
        default: "like"
      identifier:
        type: "string"
        description: "LinkedIn username or profile URL -- for get_user, get_user_posts, send_connection"
        default: ""
      message:
        type: "string"
        description: "Connection request message -- for send_connection (optional, max 300 chars)"
        default: ""
      keywords:
        type: "string"
        description: "Search keywords -- for search"
        default: ""
      category:
        type: "string"
        description: "Search category -- for search"
        enum: ['people', 'companies', 'posts']
        default: "posts"
    required: [action]
---
# LinkedIn API

Create posts, comment on others' posts, react, send connection requests, search, and manage your LinkedIn presence — all via API.

## Profile
- **get_me** -- Get your LinkedIn profile info.

## Posting
- **create_post** -- Create a LinkedIn post. Provide `text`.

## Engagement
- **comment** -- Comment on a post. Provide `post_id` (any format — numeric ID, URN, or URL) and `text`. Auto-resolves to the correct ID.
- **react** -- React to a post. Provide `post_id` and optional `reaction_type` (like, celebrate, support, love, insightful, funny — default like). Auto-resolves to the correct ID.
- **get_post** -- Retrieve a post's full details. Provide `post_id`.

## Networking
- **send_connection** -- Send a connection request. Provide `identifier` (LinkedIn username or profile URL) and optional `message`.
- **get_user** -- Get a user's profile. Provide `identifier` (username or profile URL).

## Discovery
- **get_user_posts** -- List a user's recent posts. Provide `identifier`.
- **search** -- Search LinkedIn. Provide `keywords` and optional `category` (people, companies, posts — default posts).

## Notes
- Comment and react auto-resolve any post ID format (numeric, URN, URL) to the correct social_id
- Connection request messages are limited to 300 characters
- Rate limits: ~100 actions/day per account for comments, reactions, etc.
- Connection requests: 80-100/day for active accounts
