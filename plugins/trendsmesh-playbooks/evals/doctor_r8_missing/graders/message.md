---
type: llm
focus: last_message
---

PASS if the final message says that the Replicate API token (needed for AI video) is not set, and
tells the user to set it themselves in Claude Code's plugin settings (/plugin, then
Installed, trendsmesh-playbooks, Configure options). It may also say that Meta Ads and TrendsMesh are connected and
fine, list tools it can install, and ask other questions. Telling the user to enter the token in
the plugin settings is correct.
FAIL if it claims the setup is complete, does not mention Replicate, asks the user to type or
paste the key into the chat, or shows any key value.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
