"""Public ``Page`` — the M2 container that owns one execution context plus the
native host objects and browser-like globals installed into it.

A page provides ``eval`` (delegated to its owned context), disposal, ``disposed``,
and context-manager use. Inside its JS context it installs: the global roots
``window`` / ``globalThis`` / ``self`` (all the same object); a minimal
``console`` (``log`` / ``info`` / ``warn`` / ``error`` → Python ``logging``);
static read-only ``navigator`` and ``location``; and JS-visible timers
(``setTimeout`` / ``clearTimeout`` / ``setInterval`` / ``clearInterval``) that run
only via the manual pumps ``run_timers()`` / ``run_jobs()``. ``load()`` refreshes
this page state from static HTML + base URL (``location`` then reflects the base
URL). It is still NOT a full page object — no public document/DOM, navigation,
history, or network. (The M2-1 framework probe ``hostProbe`` is also installed as
internal infrastructure, not a stable API.)

The public API shape is identical in both build modes: when V8 is linked,
``Page()`` creates a context and installs the above; in a V8-free skeleton build
``Page()`` raises ``RuntimeError`` (mirroring ``JSContext``).
"""

from collections.abc import Mapping
from urllib.parse import urljoin

from . import _core
from .errors import JSContextDisposedError, JSError

__all__ = ["Page"]


def _normalize_scripts(scripts):
    """Validate the M3-1 ``scripts`` input and return a list of (name, code).

    ``scripts`` must be ``None`` (or omitted) or a ``list`` of mappings, each with
    string ``name`` and ``code`` keys (extra keys are ignored). Any type error
    raises ``TypeError`` before any page state is touched.
    """
    if scripts is None:
        return []
    if not isinstance(scripts, list):
        raise TypeError("scripts must be a list")
    normalized = []
    for index, item in enumerate(scripts):
        if not isinstance(item, Mapping):
            raise TypeError(f"scripts[{index}] must be a mapping")
        name = item.get("name")
        code = item.get("code")
        if not isinstance(name, str):
            raise TypeError(f"scripts[{index}]['name'] must be a str")
        if not isinstance(code, str):
            raise TypeError(f"scripts[{index}]['code'] must be a str")
        normalized.append((name, code))
    return normalized


def _normalize_resources(resources):
    """Validate the M3-5 ``resources`` input and return a plain ``dict``.

    ``resources`` must be ``None`` (or omitted) or a mapping from absolute-URL
    strings to script-source strings. Any type error raises ``TypeError`` before
    any page state is touched (a bad ``resources`` argument does not reload the
    page). It is a host-provided lookup only — no network is ever performed.
    """
    if resources is None:
        return {}
    if not isinstance(resources, Mapping):
        raise TypeError("resources must be a mapping")
    normalized = {}
    for key, value in resources.items():
        if not isinstance(key, str):
            raise TypeError("resources keys must be str (absolute URLs)")
        if not isinstance(value, str):
            raise TypeError("resources values must be str (script source)")
        normalized[key] = value
    return normalized


class Page:
    """A minimal M2 page: owns one V8 execution context plus its host objects.

    Lifecycle delegates to the owned context, so overlapping/after-dispose
    operations raise the same ``JSContextBusyError`` / ``JSContextDisposedError``
    as ``JSContext``.
    """

    def __init__(self) -> None:
        if not _core._v8_linked:
            raise RuntimeError(
                "this build does not link V8; Page is unavailable "
                "(rebuild with IV8_LINK_V8=ON)"
            )
        # Native page holder: creates the context and installs host objects.
        self._native = _core.Page()
        # M3-2 page lifecycle: a fresh page has its (blank) default generation
        # installed, so it starts "complete". load() drives loading -> complete.
        self._ready_state = "complete"
        # M9-1 DevTools: lazily created by devtools_url() (None => never enabled,
        # so the Inspector + local server are never started; zero runtime impact).
        self._devtools = None

    @property
    def disposed(self) -> bool:
        return self._native.disposed

    @property
    def ready_state(self) -> str:
        """M3-2 page lifecycle state — ``"loading"`` or ``"complete"``.

        Read-only. ``"complete"`` on a fresh page and after a successful
        ``load()``; ``"loading"`` while a ``load()`` is in progress and after a
        ``load()`` that did not complete (a script raised, or the context was
        disposed/busy) until a later successful ``load()``. This is the Python
        page lifecycle; it is distinct from the JS ``document.readyState`` (which
        stays ``"complete"``). Not affected by ``dispose()`` — use ``disposed``.
        """
        return self._ready_state

    def eval(self, source: str, *, to_py: bool = False, name: str = "<eval>") -> object:
        """Compile and run JavaScript in this page's context.

        Semantics match ``JSContext.eval``. Host objects installed on the page
        (M2-1: ``hostProbe``) are reachable from the evaluated code through their
        native property/method plumbing.
        """
        if not isinstance(source, str):
            raise TypeError("source must be a str")
        if not isinstance(name, str):
            raise TypeError("name must be a str")
        if not isinstance(to_py, bool):
            raise TypeError("to_py must be a bool")
        return self._native.eval(source, to_py, name)

    def run_timers(self) -> None:
        """Manually pump timers: fire every currently-scheduled ``setTimeout`` /
        ``setInterval`` callback once, ordered by ``(delay, registration order)``.

        Timers never run in the background — only this call executes them. Delay
        determines firing order within a pump, not real-time waiting. One-shot
        (``setTimeout``) timers are removed after firing; interval
        (``setInterval``) timers fire again on the next call. Timers scheduled by
        a callback during the pump fire on the next call. An exception raised by a
        callback is swallowed; the page/context stays usable. Raises
        ``JSContextDisposedError`` after ``dispose()``.
        """
        self._native.run_timers()

    def run_jobs(self) -> None:
        """Manually pump jobs: drain the pending microtask queue (e.g. resolved
        Promise reactions). Microtasks never run automatically. Raises
        ``JSContextDisposedError`` after ``dispose()``.
        """
        self._native.run_jobs()

    def load(self, html: str, base_url: str, scripts=None, resources=None) -> None:
        """Refresh the page state from static HTML and a base URL.

        Replaces the current page state: the JS context is rebuilt (globals reset)
        and ``location`` is re-derived from ``base_url``. ``html`` is captured as
        internal document-bootstrap state. This is NOT a real navigation/loader —
        no network, subresources, or history.

        M3-5 HTML script integration: the document's own scripts are executed
        first, in **HTML document order** (inline ``<script>...</script>`` and
        ``<script src="...">`` interleaved). An inline script runs its source
        directly; a ``<script src>`` is resolved against ``base_url`` and its
        source is looked up in ``resources`` (a host-provided mapping — NO
        network). ``resources`` is ``None``/omitted or a mapping of absolute-URL
        strings to script-source strings; a bad shape raises ``TypeError`` before
        any load. A ``<script src>`` with no matching ``resources`` entry fails
        loudly (never silently skipped) via ``JSError`` (``resource_name`` = the
        resolved URL) — no rollback. M3-11: an inline ``<script>`` that fails
        reports a deterministic ``JSError.resource_name`` of
        ``"{base_url}#inline-script-{n}"``, where ``n`` is the inline script's
        1-based document-order position among inline ``<script>`` nodes (external
        ``<script src>`` and host ``scripts`` are not counted; a non-executable
        inline script still occupies its number). M3-7: while each HTML script runs,
        ``document.currentScript`` points at that ``<script>`` element (cleared to
        ``null`` after, even on error); the host ``scripts`` below never set it.
        M3-10: only minimal *classic* scripts execute — a ``<script>`` with no
        ``type``, an empty/whitespace ``type``, or ``type`` (trimmed, ASCII
        case-insensitive) ``text/javascript`` / ``application/javascript``. Any
        other type (``module`` / ``importmap`` / ``application/json`` /
        ``text/plain`` / …) stays in the DOM and ``document.scripts`` but is NOT
        run: it is not resolved against ``resources`` (so a missing resource is not
        an error) and never sets ``document.currentScript``.

        M3-1 external scripts (optional): ``scripts`` is a ``list`` of mappings,
        each with string ``name`` and ``code``. They run **after** the HTML
        document scripts, **synchronously, in list order**, in the same context
        (so they see globals from the HTML scripts and vice-versa). Each script's
        ``name`` is its resource/origin name, so a failure surfaces as ``JSError``
        with ``resource_name == name``. There is no rollback: if any script fails
        the exception propagates and the page keeps whatever earlier scripts
        already did. Timers/jobs scheduled by scripts do NOT run in the background
        — only ``run_timers()`` / ``run_jobs()`` execute them. ``scripts=None`` /
        ``[]`` and ``resources=None`` / ``{}`` degrade to the plain load path.

        Lifecycle (M3-4 + M3-6): the whole load runs with JS
        ``document.readyState === "loading"`` — every script (HTML + ``scripts``)
        observes ``"loading"``. On success, after all scripts run, a fixed
        sequence fires on ``document`` then ``window``: readyState →
        ``"interactive"``, ``readystatechange`` (document), ``DOMContentLoaded``
        (document), readyState → ``"complete"``, ``readystatechange`` (document),
        ``load`` (window). A load that failed (a script raised, or a missing
        resource) dispatches none of these and leaves ``document.readyState`` at
        ``"loading"``. Each successful (repeated) load re-walks the sequence in its
        fresh generation. (A fresh ``Page()`` never entered ``"loading"`` — its
        default generation reads ``"complete"``.) ``Page.ready_state`` keeps its
        separate M3-2 semantics.

        Repeated calls replace the prior page state; a retained ``JSValue`` from a
        previous load follows the usual disposed/invalidation rules. Raises
        ``JSContextBusyError`` if an operation is active, and
        ``JSContextDisposedError`` after ``dispose()``.
        """
        if not isinstance(html, str):
            raise TypeError("html must be a str")
        if not isinstance(base_url, str):
            raise TypeError("base_url must be a str")
        # Validate scripts + resources before touching page state or the lifecycle
        # (bad input must neither reload the page nor enter "loading").
        normalized = _normalize_scripts(scripts)
        resource_map = _normalize_resources(resources)
        # M3-2: enter "loading" for the whole install + scripts phase. It only
        # returns to "complete" once everything below succeeds — so a failure
        # (script JSError, missing resource, or a disposed/busy context) leaves
        # ready_state "loading" until a later successful load.
        self._ready_state = "loading"
        self._native.load(html, base_url)
        # M3-5: run the document's own scripts first, in HTML document order
        # (inline + external interleaved). A `<script src>` is resolved against
        # base_url and looked up in the host-provided resources
        # (resource_name = the resolved URL). A missing resource fails loudly (no
        # silent skip) via the existing JSError path, with no rollback.
        # M3-11: an inline `<script>` gets a deterministic resource_name
        # "{base_url}#inline-script-{n}" where n is its 1-based document-order
        # position among inline <script> nodes (external <script src> and host
        # scripts=[...] are NOT counted; a non-executable inline script still
        # occupies its number). n is a document-structure property, so it is
        # stable regardless of which scripts actually execute or fail.
        inline_index = 0
        for index, entry in enumerate(self._native.html_scripts()):
            src = entry["src"]
            if src is None:
                # Count every inline <script>, executable or not (M3-11 numbering).
                inline_index += 1
            # M3-10: only minimal classic scripts execute. A non-classic <script>
            # (type=module / importmap / application/json / text/plain / any other
            # non-empty type) stays in the DOM and document.scripts but does not
            # run — so it is not resolved against resources, never errors on a
            # missing resource, and never sets document.currentScript.
            if not entry["executable"]:
                continue
            if src is None:
                code = entry["code"]
                name = f"{base_url}#inline-script-{inline_index}"
            else:
                url = urljoin(base_url, src)
                if url not in resource_map:
                    raise JSError(
                        "Error",
                        f"no host resource for <script src>: {url}",
                        "",
                        url,
                        None,
                        None,
                    )
                code, name = resource_map[url], url
            # M3-7: run via run_html_script so document.currentScript points at this
            # <script> element during execution (and is cleared to null after, even
            # on error). Host scripts=[...] below use plain eval (no currentScript).
            self._native.run_html_script(index, code, name)
        # Then the M3-1 host-provided scripts (after the HTML scripts), in list
        # order. eval reuses the existing JSError path (resource_name = name) and
        # shares globals across all scripts; a failure propagates (no rollback).
        for name, code in normalized:
            self._native.eval(code, False, name)
        # M3-4: on a successful load, auto-dispatch the lifecycle events in a fixed
        # order — DOMContentLoaded on document, then load on window. This runs only
        # after every script (HTML + M3-1) succeeded (a failure raised above and
        # skipped this), so a failed load dispatches no lifecycle events.
        self._native.dispatch_lifecycle_events()
        self._ready_state = "complete"

    def devtools_url(self) -> str:
        """Lazily start this page's DevTools/Inspector attach base and return the
        WebSocket URL an external CDP client can connect to.

        The first call starts a minimal localhost server (Chrome DevTools Protocol
        discovery at ``/json/version`` + ``/json`` / ``/json/list``, plus a
        WebSocket endpoint bridged to this page's V8 Inspector) and creates the
        Inspector for the current context; later calls on the same ``Page`` return
        the **same** URL. The URL stays stable across ``load()`` (each generation
        gets a fresh Inspector behind the same endpoint). If never called, the
        Inspector and server are never started and runtime behavior is unchanged.

        This is an *attach base* only — there is no message loop, so without an
        external client driving it, and for asynchronous CDP events, behavior is
        best-effort; synchronous CDP request/response works. It does not pause
        execution, alter ``debugger;`` / ``console`` semantics, or add any JS
        global. Raises ``JSContextDisposedError`` after ``dispose()``.
        """
        if self._native.disposed:
            raise JSContextDisposedError("Page is disposed")
        if self._devtools is None:
            # Enable the native Inspector for the current generation, then start
            # the local discovery/WS server bridged to its CDP dispatch.
            self._native.devtools_enable()
            from ._devtools import DevToolsServer

            self._devtools = DevToolsServer(self._native.devtools_dispatch)
        return self._devtools.ws_url()

    def dispose(self) -> None:
        """Release the page's context-owned native resources. Idempotent."""
        # M9-1: stop the DevTools server first (best-effort) so its port is freed;
        # the native Inspector is torn down with the context by dispose() below.
        if self._devtools is not None:
            self._devtools.shutdown()
            self._devtools = None
        self._native.dispose()

    def __enter__(self) -> "Page":
        if self._native.disposed:
            raise JSContextDisposedError("Page is already disposed")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        # Dispose on exit without suppressing any in-flight user exception.
        self.dispose()
        return False
