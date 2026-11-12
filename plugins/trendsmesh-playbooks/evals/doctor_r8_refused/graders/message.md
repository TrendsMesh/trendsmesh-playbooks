---
type: llm
focus: last_message
---

PASS if the final message says the Replicate token is set but Replicate refuses it (wrong, revoked or not
working), so AI video is not ready, and tells the user to make a new token at replicate.com/account/api-tokens and
put it in Claude Code's plugin settings themselves (/plugin, then trendsmesh-playbooks, configure), then start a new
session. It may also say what else is ready and list tools it can install.
FAIL if it says the token works or is merely "set", says the token is missing without saying it is refused, blames
credit or billing, asks the user to type or paste the token into the chat, or shows any key value.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
