# M2-4 — Timers / Jobs

Scope of this phase only. Building on M2-1/M2-2/M2-3, M2-4 adds minimal, fully
manual scheduling: JS-visible timers and a Python-side pump. **Nothing runs in
the background** — no auto event loop, no threads, no browser-grade loop
fidelity. M2-5 is not started.

## JS-visible timers

Installed as bare global functions on the page's context (like `window`/`self`):

- `setTimeout(fn, delay)` → returns a numeric timer id
- `clearTimeout(id)`
- `setInterval(fn, delay)` → returns a numeric timer id
- `clearInterval(id)`

`clearTimeout` and `clearInterval` share one id space (either cancels any id).
Invalid calls (missing/!function first arg) register nothing and return
`undefined`. Extra callback arguments are not forwarded (out of scope).

## Manual pump (the hard constraint)

Two Python methods on `Page`:

- **`page.run_timers()`** — fire every *currently-scheduled* timer callback
  **once**, ordered by `(delay, registration order)`. Delay determines firing
  order within a pump; it does **not** cause real-time waiting (there is no
  clock). One-shot (`setTimeout`) timers are removed after firing; interval
  (`setInterval`) timers remain and fire again on the next call. Timers scheduled
  by a callback *during* a pump are not in that pump's snapshot and fire on the
  **next** call — so a self-rescheduling timer advances one step per pump and
  never loops forever.
- **`page.run_jobs()`** — drain the pending microtask (job) queue, e.g. resolved
  `Promise` reactions. The isolate's microtask policy is **explicit**, so
  microtasks never run automatically; only `run_jobs()` executes them.

Timers and jobs are independent: `run_timers()` does not drain microtasks and
`run_jobs()` does not fire timers. Call both if you need both.

## Scheduling model

The timer registry lives on `ContextState` (id → callback + delay + kind + seq),
reset in the context teardown before isolate disposal. `setTimeout` etc. recover
their `ContextState` from an isolate embedder-data slot. All registration,
cancellation, and pumping run under the **existing M1 operation guard**, so:

- callbacks obey the context serial/busy rules (an overlapping op → `JSContextBusyError`);
- the GIL is released around each callback (as with `eval`);
- a callback that throws is caught and swallowed — the page/context stays usable;
- after `dispose()`, `run_timers()` / `run_jobs()` raise `JSContextDisposedError`
  (the M1 path — no new error type).

## Public API

New Python API: `Page.run_timers()` and `Page.run_jobs()` (the manual pump — the
core deliverable of this phase). The timer functions themselves are JS globals,
not Python API. No new exception types. Page remains a minimal container (no
`load`/navigation/document).

## Frozen out of M2-4 (not implemented)

Automatic/background event loop, thread scheduling, browser-grade loop fidelity,
`queueMicrotask` as a public API, `page.load`, document, DOM, network, DevTools,
trusted input — and M2-5.

## Tests

`test/test_timers.py`: timer functions exist; `setTimeout` runs only on a pump
(and one-shots don't re-fire); `clearTimeout` cancels; `setInterval` fires per
pump until `clearInterval`; delay-then-registration ordering; a self-rescheduling
timer advances one step per pump (loop-safe); callbacks mutate global state; a
throwing callback leaves the page usable; `run_jobs()` drains microtasks that do
not run automatically; pumping after `dispose()` uses the M1 error path.
API-shape guards confirm no new Python surface beyond the two pump methods.
