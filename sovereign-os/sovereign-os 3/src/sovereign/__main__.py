"""Start a local-only interface: python -m sovereign"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("sovereign.app:app", host="127.0.0.1", port=8765, reload=False)
