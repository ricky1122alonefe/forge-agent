"""External integrations for forge-agent.

IM adapters and webhook receivers plug into the runtime layer
(triggers + callbacks), keeping core / Pipeline unaware of external
surfaces. This is S1.2: protocol contracts only; concrete adapters
land in S5.
"""
