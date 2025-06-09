"""
Simplified FastAPI Application - Basic version to test setup
"""
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="VPS Automation Server - Simple",
    description="Simplified version for testing",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {
        "service": "VPS Automation Server",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 