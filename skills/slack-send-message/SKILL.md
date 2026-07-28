---
name: slack-send-message
display_name: "Slack Send Message"
description: "Send a message to a Slack channel (top-level) or thread"
category: communication
icon: message-square
skill_type: sandbox
catalog_type: platform
resource_requirements:
  - env_var: SLACK_BOT_TOKEN
    name: "Slack Bot Token"
    description: "Slack Bot OAuth token (xoxb-...)"
tool_schema:
  name: slack_send_message
  description: "Post a message to a Slack channel. Omit thread_ts for a top-level post; set it only to reply inside an existing thread."
  parameters:
    type: object
    properties:
      channel:
        type: "string"
        description: "Channel ID"
      thread_ts:
        type: "string"
        description: "Optional. Timestamp of a root message to reply under (e.g. 1709827000.000001). Omit to post a new top-level message."
      text:
        type: "string"
        description: "Message text"
    required: [channel, text]
---
# Slack Send Message
Post a message to a Slack channel. Requires channel and text. `thread_ts` is optional: omit it for a new top-level message, or set it to the root message timestamp to reply inside that thread.
