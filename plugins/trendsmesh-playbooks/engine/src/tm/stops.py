"""The stop contract shared by the playbooks' commands (PB04's `tm research`, `tm seeds`; PB02 and
PB03 import it too).

`Stop` means the run lacks an input, or a file the agent wrote needs fixing: the command exits 2
(`status: "stop"`) with what happened, what to do, and that the run continues from the same place.
A plain `ValueError` stays for a bad argument (exit 1).
"""

from __future__ import annotations

AGAIN = "the run continues from the same place"
AGAIN_SENTENCE = "The run continues from the same place."   # AGAIN as a sentence of its own


class Stop(ValueError):
    """Something to fix or fetch first: exit 2, the message says what to do."""
