# WebSocket protocol — v3 mobile dashboard

**Status**: FROZEN at 2026-04-19. Backend and frontend subagents both
read this file. Changes require new version (`v=2` query param) +
explicit note here.

**Version tag**: `v=1` in handshake query string.

---

## 1 · Connection

- URL: `ws://<host>:7861/ws?t=<auth-token>&v=1`
- `auth-token`: random 16-char hex printed at boot. Required.
- `v`: protocol version. Required. Server rejects mismatch with close
  code `1008` (policy violation).
- Origin policy: server accepts any Origin (LAN-only setup).
- TLS: not used (LAN-only). If we ever expose to WAN, add `wss://`.

### Handshake outcome
- Auth ok + version ok → server responds with first `state` message.
- Bad token → close `4401` ("auth_failed").
- Bad version → close `1008` ("version_mismatch").

---

## 2 · Client → Server messages

All client messages are JSON objects with mandatory `op` string.
Unknown `op` → server sends `{"type": "error", "code": "unknown_op"}`
and closes `1003` (unsupported data).

### 2.1 `start`
Start the engine (open camera, begin pipeline).
```json
{"op": "start"}
```
Response: server pushes new `state` (with `running=true`) when start
completes. May take 500 ms - 2 s (camera open). Server runs
`engine.start(blocking=False)` in an executor — never blocks event loop.

### 2.2 `stop`
Stop the engine (release camera, halt pipeline).
```json
{"op": "stop"}
```
Response: `state` push with `running=false`.

### 2.3 `toggle_filter`
Enable or disable a filter.
```json
{"op": "toggle_filter", "filter": "<filter_id>", "on": true}
```
- `filter`: must be in registry whitelist. Unknown → `error code unknown_filter`.
- `on`: bool, required. Anything truthy is coerced; null/missing → `error`.

Response: `state` push reflecting the new `enabled` value.

### 2.4 `set_param`
Set a single param of a single filter.
```json
{"op": "set_param", "filter": "temporal_scan", "param": "angle", "value": 45.0}
```
- `filter` + `param` must both pass registry whitelist. Unknown →
  `error code unknown_param`.
- `value` is clamped + cast to the registry's `min/max/step/type`.
  Out-of-range values are silently clamped (NOT rejected) — the UI
  may have lag and we want forgiving behavior.
- Booleans for switch params: any truthy value coerces to `true`.

Response: `state` push with the clamped value (so the client can
reconcile if it sent something out-of-range).

### 2.5 `pong`
Reply to server `ping` heartbeat.
```json
{"op": "pong"}
```
If no `pong` received within 30 s of `ping`, server closes `1011`
(server detected client gone).

---

## 3 · Server → Client messages

All server messages are JSON objects with mandatory `type` string.

### 3.1 `state`
The full snapshot of engine + filters. Pushed:
- Once on connect.
- After every successful client op.
- Debounced 50 ms when multiple ops fire close together.
- Once per second as an FPS/latency tick (even when nothing changes).

```json
{
  "type": "state",
  "running": true,
  "fps": 29.4,
  "lat_ms": 27.8,
  "filters": {
    "temporal_scan": {
      "enabled": false,
      "wip": false,
      "params": {"angle": 0.0, "max_frames": 30}
    },
    "bloom": {
      "enabled": true,
      "wip": false,
      "params": {"intensity": 0.6, "threshold": 200, "blur_size": 21}
    },
    "bc": {
      "enabled": false,
      "wip": false,
      "params": {"brightness": 0, "contrast": 1.0}
    },
    "chroma": {"enabled": false, "wip": true, "params": {}},
    "invert": {"enabled": false, "wip": true, "params": {}}
  }
}
```

- `wip: true` filters are stubs — UI shows a "WIP" badge and disables
  the toggle. Server rejects ops on wip filters with `error code wip_filter`.
- `fps`, `lat_ms` come from the engine's perf snapshot. If engine not
  running, both are `0.0`.
- `params` keys for each filter are exactly the keys in the registry
  (see registry.py).

### 3.2 `ping`
Heartbeat. Sent every 15 s.
```json
{"type": "ping"}
```
Client must reply `{"op": "pong"}` within 30 s.

### 3.3 `error`
Non-fatal protocol error. Connection stays open unless the error
implies the client is misbehaving (then server closes after sending).
```json
{"type": "error", "code": "unknown_op", "msg": "got 'flubber'"}
```

#### Error codes
| `code` | Meaning | Server closes? |
|---|---|---|
| `unknown_op` | `op` not in whitelist | yes (1003) |
| `unknown_filter` | `filter` id not in registry | no |
| `unknown_param` | `param` id not in filter's registry | no |
| `wip_filter` | tried to operate on a WIP stub | no |
| `bad_payload` | JSON parse error or missing required field | yes (1003) |
| `internal` | server hit an exception (logged) | no |

---

## 4 · Server-side guardrails (NON-NEGOTIABLE)

Every incoming message goes through `protocol.py` which:

1. Whitelists `op` against a literal set: `{"start", "stop", "toggle_filter", "set_param", "pong"}`.
2. Whitelists `(filter_id, param_id)` against `registry.py`.
3. Clamps `value` with `min/max/step/type` from the registry.
4. Coerces types defensively (`int`, `float`, `bool`).
5. Catches all exceptions in dispatchers and emits `error code internal`.

The auth token check happens once at handshake; subsequent messages
are not re-authenticated (LAN, single-user assumption).

---

## 5 · Reconnection (client-side)

- On WS close: client retries with exponential backoff starting at
  250 ms, doubling, capped at 4 s.
- On reconnect: client receives a fresh `state` snapshot. Local UI
  state is overwritten by server state. No replay of pending ops —
  state is idempotent.
- Reconnect attempts continue indefinitely (no give-up).

---

## 6 · Threading model (server)

- uvicorn event loop in main thread.
- Engine loop in its own thread (existing behavior).
- WS handlers (async) call sync `EngineBridge` methods directly for
  filter mutations (microsecond ops, lock-protected).
- `engine.start()` / `engine.stop()` MUST go through
  `loop.run_in_executor(None, ...)` because they block 500 ms - 2 s.
- Engine → WS pushes use `loop.call_soon_threadsafe(broadcast)`.

---

## 7 · Versioning

- This is `v=1`. Any breaking change → `v=2`, this file frozen, new
  doc written.
- Additive changes (new `op`, new `error code`, new param) do NOT bump
  version, but MUST be appended to this file with a `2026-MM-DD added:`
  note in the relevant section.
