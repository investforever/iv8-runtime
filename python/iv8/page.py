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

from . import _core
from .errors import JSContextDisposedError

__all__ = ["Page"]


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

    @property
    def disposed(self) -> bool:
        return self._native.disposed

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

    def load(self, html: str, base_url: str) -> None:
        """Refresh the page state from static HTML and a base URL.

        Replaces the current page state: the JS context is rebuilt (globals reset)
        and ``location`` is re-derived from ``base_url``. ``html`` is captured as
        internal document-bootstrap state (no public document surface yet). This
        is NOT a real navigation/loader — no network, subresources, or history.

        Repeated calls replace the prior page state; a retained ``JSValue`` from a
        previous load follows the usual disposed/invalidation rules. Raises
        ``JSContextBusyError`` if an operation is active, and
        ``JSContextDisposedError`` after ``dispose()``.
        """
        if not isinstance(html, str):
            raise TypeError("html must be a str")
        if not isinstance(base_url, str):
            raise TypeError("base_url must be a str")
        self._native.load(html, base_url)

    def dispose(self) -> None:
        """Release the page's context-owned native resources. Idempotent."""
        self._native.dispose()

    def __enter__(self) -> "Page":
        if self._native.disposed:
            raise JSContextDisposedError("Page is already disposed")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        # Dispose on exit without suppressing any in-flight user exception.
        self.dispose()
        return False
