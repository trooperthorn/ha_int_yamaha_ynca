# Design notes

Rationale behind UI and flow behavior that isn't obvious from the code.

## Options flow: no-connection dialog exits as success, not abort

When the options flow's `async_step_no_connection` step is confirmed, it
calls `async_step_done()` (which finishes as a successful update) rather
than `self.async_abort(reason="no_connection")`. Home Assistant's abort box
has no title, so an abort here reads as an unexplained dead end. Exiting
through the normal "done" step instead re-saves the current settings and
gives the user a clear, titled result, even though nothing was actually
changed.
