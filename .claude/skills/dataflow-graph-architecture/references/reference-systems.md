# Reference Dataflow Systems for AV Processing

## 1. TouchDesigner (Derivative)

**Architecture:** Operator-based dataflow graph with 6 typed operator families.

**Key Design Decisions:**
- Pull-based evaluation: nodes only "cook" when downstream requests data
- Typed operator families (TOP/CHOP/SOP/DAT/MAT/COMP) with explicit cross-family bridges
- Feedback TOP as first-class node type with 1-frame delay
- Every parameter can be driven by expressions, CHOPs, or Python
- GPU-native: TOPs execute on GPU by default

**What SIE should learn:**
- Feedback as a native concept, not a hack
- CHOP-style signal channels alongside video
- Pull-based evaluation for efficiency
- Parameter modulation as a first-class feature

**What SIE should NOT copy:**
- GPL-licensed, closed-source execution model
- Heavy GPU dependency (SIE must work CPU-only)
- Complex operator family system (SIE needs fewer types)

---

## 2. Max/MSP (Cycling '74)

**Architecture:** Message-passing dataflow with hot/cold inlets.

**Key Design Decisions:**
- Right-to-left, bottom-to-top deterministic execution order
- "Hot" inlets trigger computation; "cold" inlets store values without triggering
- Subpatchers encapsulate sub-graphs as reusable components
- Separate audio graph (signal rate) from control graph (message rate)
- Gen~ for compiled, sample-level DSP codegen

**What SIE should learn:**
- Hot/cold inlet concept: not every input change triggers recomputation
- Separate signal rates: video (30fps) vs control (smooth) vs audio (44.1kHz)
- Subgraph encapsulation for reusable effect chains
- Deterministic execution order for reproducibility

---

## 3. Notch (Notch.one)

**Architecture:** Node graph optimized for real-time rendering + live performance.

**Key Design Decisions:**
- Nodes have "exposed parameters" that surface in parent UI
- Built-in per-node performance profiling
- Automatic GPU/CPU scheduling per node type
- Video input/output nodes with NDI, Spout, capture card support
- Particle, fluid, and physics nodes built-in

**What SIE should learn:**
- Per-node profiling for performance debugging
- Exposed parameters pattern for UI generation
- GPU/CPU scheduling at the node level

---

## 4. VVVV (vvvv group)

**Architecture:** Visual dataflow with spreads (arrays as first-class values).

**Key Design Decisions:**
- "Spreads" = arrays of values that automatically broadcast through operations
- Every pin (port) can carry a spread, enabling batch processing
- Differential evaluation: only changed values propagate
- Seamless C#/.NET integration for custom nodes

**What SIE should learn:**
- Spread/broadcast semantics: one filter applied to multiple frames simultaneously
- Differential evaluation: skip processing when inputs haven't changed

---

## 5. Resolume Arena/Avenue

**Architecture:** Layer-based composition with effect chains per layer.

**Key Design Decisions:**
- Layers (like Photoshop) with blend modes
- Each layer has an independent effect chain
- Composition node merges all layers
- BPM-synced parameter automation
- FFGL (FreeFrame) plugin standard for effects

**What SIE should learn:**
- Layer-based composition model for combining effects
- Blend modes as a first-class composition operation
- FFGL/plugin standard for community effects

---

## 6. Mosaic (d3cod3, openFrameworks-based)

**Architecture:** Visual patching platform with live coding.

**Key Design Decisions:**
- Node-based with OF as rendering backend
- Live coding in Lua, GLSL, Bash
- Pure Data integration for audio
- Multi-window output for projection mapping
- MIT licensed, fully open source

**Relevance:** Most similar open-source project to what SIE could become.
Repository: https://github.com/d3cod3/Mosaic (499 stars)

---

## Comparison Matrix

| Feature | TouchDesigner | Max/MSP | Notch | VVVV | Resolume | Mosaic |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| Open source | No | No | No | Partly | No | Yes |
| Pull-based eval | Yes | No | Yes | Yes | No | No |
| Feedback loops | Native | Native | Native | Native | No | Limited |
| Audio integration | CHOP | Core | Limited | Yes | BPM sync | PureData |
| GPU processing | Native | Jitter | Native | Yes | Yes | OF/GLSL |
| Control signals | CHOP | Messages | Params | Spreads | BPM | OSC |
| Per-node profiling | Yes | No | Yes | No | No | No |
| Plugin ecosystem | .tox | Max4Live | FFGL | .NET | FFGL | OF addons |
| Multi-output | Yes | Yes | Yes | Yes | Yes | Yes |
| Parameter modulation | Native | Native | Native | Native | BPM | OSC |

## Recommended SIE Approach

Based on analysis of all reference systems:

1. **Execution model**: Hybrid push-pull (push from sources, lazy evaluation of unused branches)
2. **Port types**: ~8 types (video, audio, analysis, control, mask, trigger, text, render)
3. **Feedback**: Native with cycle detection + implicit delay insertion
4. **Control signals**: CHOP-inspired float channels for parameter modulation
5. **Profiling**: Per-node timing (from Notch pattern)
6. **Plugin model**: Node discovery via Python module scanning (like OF addons)
7. **Composition**: Composite node with blend modes (from Resolume pattern)
8. **Open source**: Follow Mosaic's MIT model
