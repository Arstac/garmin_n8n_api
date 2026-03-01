#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from api.api import app
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
