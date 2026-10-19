"""Preserve process failure status despite Kit's fast-shutdown process exit."""
import os
import sys
import traceback


def close_simulator(app, env=None, failed=False):
    if env is not None:
        try:
            env.close()
        except Exception:
            traceback.print_exc()
            failed = True
    sys.stdout.flush()
    sys.stderr.flush()
    if failed:
        # Kit fast shutdown may terminate Python with code 0, swallowing an active
        # exception. Full non-fast teardown segfaults in the installed Sim stack.
        # On errors, terminate THIS worker with code 1; the OS releases its CUDA
        # context. All diagnostic/checkpoint writes happen before this point.
        os._exit(1)
    app.close()
