---
type: regex
target: last_message
# never asks to install gh, sign in to GitHub or create an account
pattern: 'gh auth login|sign up|create (a|an|your) (free )?GitHub account|install (the )?(GitHub CLI|gh)'
flags: 'i'
match: not_contains
---
