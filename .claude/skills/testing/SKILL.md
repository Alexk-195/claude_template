---
name: testing
description: Explains how to implement tests and how to run the test suite
---

# Testing in auto_placer

## Running tests

```bash
python -m pytest
```

Runs the full suite under `tests/`. Exit code is non-zero on failure.

## Test file conventions

- Location: `tests/`, mirroring the `src/auto_placer/` package layout (e.g.
  `src/auto_placer/optimizer/skeleton.py` → `tests/optimizer/test_skeleton.py`)
- File name: `test_*.py`
- First line (or within first 20 lines): `# @file_purpose ...`

## Framework

pytest. Use plain `assert`, fixtures for setup/teardown, `tmp_path` for temp files/dirs
(handles cleanup automatically — no manual removal needed).

## Realizer backend tests

The `Realizer` protocol (see `doc/PCB_as_Code_Architecture.md` §5) is the pluggable boundary
to JITX (or any other backend). Unit tests must use a **fake/stub Realizer**, not the real
JITX backend — the real `build()` is atomic, slow, and the only ground-truth DRC (§8), so
burning it in the inner test loop is expensive and non-deterministic to depend on in CI.

```python
class FakeRealizer:
    def __init__(self):
        self.placed = []
        self.route_intents = []

    def place(self, obj, at, layer):
        self.placed.append((obj, at, layer))

    def emit_route_intent(self, layer, a, b):
        self.route_intents.append((layer, a, b))

    def build(self):
        return BuildResult(passed=True, board=None)
```

Tests that genuinely need the real backend (a full build+DRC round trip) are the exception:
mark them (e.g. `@pytest.mark.live`) and gate on the backend actually being configured/
available, so they skip cleanly rather than fail when it isn't:

```python
import pytest

@pytest.mark.live
def test_real_build_roundtrip():
    pytest.importorskip("jitx")
    ...
```

## What to test

- Happy path: normal input produces correct output/state
- Feasibility layer: hard constraints (DRC spacing, no shorts, layer legality) are enforced,
  never traded off against soft metrics
- Hop-triviality: `hop_is_trivial` correctly flags non-trivial hops *before* a build is
  attempted — this is the self-evaluating router's core guarantee (§4.4)
- Determinism: given a fixed skeleton, repeated (simulated) builds produce identical results
- Not-found / empty cases (e.g. no feasible route in a corridor)
- Error boundaries (invalid input, malformed intent)
