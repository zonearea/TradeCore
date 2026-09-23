"""Convenience launcher: python -m server from repo root, or run this file."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="127.0.0.1", port=5080, reload=True)
