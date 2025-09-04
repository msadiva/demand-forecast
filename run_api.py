#!/usr/bin/env python3
"""
Simple script to run the Workforce Management API server.
"""

import uvicorn
from workforce_management.api.main import app

if __name__ == "__main__":
    print("Starting Workforce Management API...")
    print("API will be available at: http://localhost:8000")
    print("Interactive docs at: http://localhost:8000/docs")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )