---
type: llm
focus: last_message
---

PASS if the final message says that the middle of the video is what is fading (the opening holds),
and offers re-cut variants for it (for example a shorter cut, a speed-up of the slow part, proof
inserted in the weak part, a new shot), where each variant changes one thing and comes with its
level (a number from 0 to 5, or the level's name: pure edit, graphics layer, own assets, repair
AI, generative AI, audio). A level that depends on the ad (for example "level 0, or level 1 if a
card has to move") still names a level, and one variant is one kind of change even when it says
what that change may need. It may say that the exact variants are chosen once the video has been
broken down, it may mention the routine extras of every refresh (a 4:5 version, the copy and
thumbnail decision, music for a new length), and it may ask the user to accept the diagnosis, with
the other answers the check-in takes: refresh another part instead, in the user's own words (issue
#143's override), or do not refresh (the run ends with the diagnosis report).
FAIL if it says this kind of refresh is not supported, offers no re-cut variant, proposes doing
several kinds of change in one variant (for example a shorter cut that also adds a new AI shot),
gives any variant without a level, or makes, renders or buys anything.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
