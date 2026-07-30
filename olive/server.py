"""
Decoder-free OLIVE gRPC server (EM + CLIP scorer).

This module re-exports and delegates to wingman_olive.wingman_server.
"""

import runpy

from wingman_olive.wingman_server import serve

__all__ = ["serve"]


if __name__ == "__main__":
    runpy.run_module("wingman_olive.wingman_server", run_name="__main__")
