"""Preregister four offline semantic probes for the newly found serialization gap, separate from the strict JSON check."""
PROBES = [
    ('original','Export the devices table from network.mdb and preserve control characters using JSON escaping.','preserve'),
    ('same','Export devices from ledger.mdb. Decoding the exported JSON should recover every original character, including controls.','preserve'),
    ('opposite','Export devices from ledger.mdb. Replace each control character with a space in the exported JSON.','replace'),
    ('distractor','Export devices from ledger.mdb. Replace each control character with a space in the exported JSON. The database arrived on Tuesday.','replace'),
]
