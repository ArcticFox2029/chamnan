"""iFlow CLI — `IFLOW.md`.

Another renamed context file, and another reason not to infer one convention from a neighbour's.
iFlow has a SessionStart hook; the documented file mechanism is what gets written, for the same
reason as everywhere else here.
"""

NAME = "iflow"
TARGET = "IFLOW.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
