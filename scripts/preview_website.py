"""Loopback-only website preview with the real champion inference backend."""

from __future__ import annotations

import argparse
import os
import secrets

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from escape_ai.play.production import app_factory

parser = argparse.ArgumentParser()
parser.add_argument("--dist", required=True)
parser.add_argument("--port", type=int, default=8766)
args = parser.parse_args()
os.environ["ESCAPE_INFERENCE_KEY"] = secrets.token_hex(32)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def local_proxy(request: Request, call_next):
    headers = [(key, value) for key, value in request.scope["headers"] if key != b"authorization"]
    headers.append((b"authorization", ("Bearer " + os.environ["ESCAPE_INFERENCE_KEY"]).encode()))
    request.scope["headers"] = headers
    return await call_next(request)


app.mount("/Escape/api/champion", app_factory())
app.mount("/Escape", StaticFiles(directory=args.dist, html=True))
uvicorn.run(app, host="127.0.0.1", port=args.port)
