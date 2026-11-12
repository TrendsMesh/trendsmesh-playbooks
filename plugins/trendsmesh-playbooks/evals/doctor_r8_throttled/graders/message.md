---
type: llm
focus: last_message
---

PASS if the final message says Replicate is limiting (throttling, rate-limiting) the account's requests, so the
Replicate token can't be used right now, and gives the fix: wait a little and check again, or add a payment method at
replicate.com/account/billing (an account with no payment method is limited to a few runs a minute).
FAIL if it says the token is wrong, revoked or missing, tells the user to make a new token, asks the user to type
or paste the token into the chat, or shows any key value.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
