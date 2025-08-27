# ASGI shim to avoid 'Attribute app not found in module main'
try:
    from main import app  # FastAPI instance
except Exception as e:
    # Fallback: create minimal app to expose error message
    from fastapi import FastAPI
    app = FastAPI(title="GanadoBravo (ASGI fallback)")
    @app.get("/__asgi_error__")
    def asgi_error():
        return {"error": "Failed to import app from main.py", "detail": str(e)}
