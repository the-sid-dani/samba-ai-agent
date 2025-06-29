import os

#####
# SambaAI Slack Bot Configs
#####
SAMBAAI_BOT_NUM_RETRIES = int(os.environ.get("SAMBAAI_BOT_NUM_RETRIES", "5"))
# How much of the available input context can be used for thread context
MAX_THREAD_CONTEXT_PERCENTAGE = 512 * 2 / 3072
# Number of docs to display in "Reference Documents"
SAMBAAI_BOT_NUM_DOCS_TO_DISPLAY = int(
    os.environ.get("SAMBAAI_BOT_NUM_DOCS_TO_DISPLAY", "5")
)
# If the LLM fails to answer, SambaAI can still show the "Reference Documents"
SAMBAAI_BOT_DISABLE_DOCS_ONLY_ANSWER = os.environ.get(
    "SAMBAAI_BOT_DISABLE_DOCS_ONLY_ANSWER", ""
).lower() not in ["false", ""]
# When SambaAI is considering a message, what emoji does it react with
SAMBAAI_REACT_EMOJI = os.environ.get("SAMBAAI_REACT_EMOJI") or "eyes"
# When User needs more help, what should the emoji be
SAMBAAI_FOLLOWUP_EMOJI = os.environ.get("SAMBAAI_FOLLOWUP_EMOJI") or "sos"
# What kind of message should be shown when someone gives an AI answer feedback to SambaAIBot
# Defaults to Private if not provided or invalid
# Private: Only visible to user clicking the feedback
# Anonymous: Public but anonymous
# Public: Visible with the user name who submitted the feedback
SAMBAAI_BOT_FEEDBACK_VISIBILITY = (
    os.environ.get("SAMBAAI_BOT_FEEDBACK_VISIBILITY") or "private"
)
# Should SambaAIBot send an apology message if it's not able to find an answer
# That way the user isn't confused as to why SambaAIBot reacted but then said nothing
# Off by default to be less intrusive (don't want to give a notif that just says we couldnt help)
NOTIFY_SLACKBOT_NO_ANSWER = (
    os.environ.get("NOTIFY_SLACKBOT_NO_ANSWER", "").lower() == "true"
)
# Mostly for debugging purposes but it's for explaining what went wrong
# if SambaAIBot couldn't find an answer
SAMBAAI_BOT_DISPLAY_ERROR_MSGS = os.environ.get(
    "SAMBAAI_BOT_DISPLAY_ERROR_MSGS", ""
).lower() not in [
    "false",
    "",
]
# Default is only respond in channels that are included by a slack config set in the UI
SAMBAAI_BOT_RESPOND_EVERY_CHANNEL = (
    os.environ.get("SAMBAAI_BOT_RESPOND_EVERY_CHANNEL", "").lower() == "true"
)

# Maximum Questions Per Minute, Default Uncapped
SAMBAAI_BOT_MAX_QPM = int(os.environ.get("SAMBAAI_BOT_MAX_QPM") or 0) or None
# Maximum time to wait when a question is queued
SAMBAAI_BOT_MAX_WAIT_TIME = int(os.environ.get("SAMBAAI_BOT_MAX_WAIT_TIME") or 180)

# Time (in minutes) after which a Slack message is sent to the user to remind him to give feedback.
# Set to 0 to disable it (default)
SAMBAAI_BOT_FEEDBACK_REMINDER = int(
    os.environ.get("SAMBAAI_BOT_FEEDBACK_REMINDER") or 0
)
# Set to True to rephrase the Slack users messages
SAMBAAI_BOT_REPHRASE_MESSAGE = (
    os.environ.get("SAMBAAI_BOT_REPHRASE_MESSAGE", "").lower() == "true"
)

# SAMBAAI_BOT_RESPONSE_LIMIT_PER_TIME_PERIOD is the number of
# responses SambaAIBot can send in a given time period.
# Set to 0 to disable the limit.
SAMBAAI_BOT_RESPONSE_LIMIT_PER_TIME_PERIOD = int(
    os.environ.get("SAMBAAI_BOT_RESPONSE_LIMIT_PER_TIME_PERIOD", "5000")
)
# SAMBAAI_BOT_RESPONSE_LIMIT_TIME_PERIOD_SECONDS is the number
# of seconds until the response limit is reset.
SAMBAAI_BOT_RESPONSE_LIMIT_TIME_PERIOD_SECONDS = int(
    os.environ.get("SAMBAAI_BOT_RESPONSE_LIMIT_TIME_PERIOD_SECONDS", "86400")
)
