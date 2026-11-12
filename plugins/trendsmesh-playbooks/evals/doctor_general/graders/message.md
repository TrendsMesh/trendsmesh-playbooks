---
type: llm
focus: last_message
---

PASS if the final message gives the plugin's general state without picking a playbook: the base tools (ready,
or offered to install), the Replicate token and the ElevenLabs key as missing, with where to set them
(Claude Code's plugin settings: /plugin, then Installed, trendsmesh-playbooks, Configure options) and without asking for them in
chat, presented as things some playbooks need rather than as blockers; TrendsMesh as connected or signed in;
and how to check one playbook (by naming it, for example "/trendsmesh-playbooks:doctor trend research"). It may
list the playbooks and offer to check one.
FAIL if it presents the result as one playbook's readiness check (for example "Refresh an ad: readiness check"),
asks for the user's Meta ad account, says it is waiting for Meta Ads, says nothing about the keys, asks the user
to paste a key into the chat, or shows any key value.
