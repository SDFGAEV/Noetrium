# vNext Boundary: experimentation/run/control

SYSTEM = "experimentation"
NODE = "experimentation/run/control"
OWNS = "durable generic run lifecycle control authority and fenced control generations"
MUST_NOT_OWN = "operator product intents, server supervision internals or duplicate run manifest/checkpoint truth"
AUTHORITY = "run_control"
