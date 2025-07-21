from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path

from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.api.drive import router as drive_router
from app.api.admin import router as admin_router
from app.api.ads import router as ads_router
from app.routes import router as web_router

# Create FastAPI app
app = FastAPI(
    title="Invoice Extractor",
    description="""Extract invoice details from uploaded files

## API Key Authentication

### Getting Your API Key

1. **Log in** to the Invoice Extractor application using your credentials.
2. Navigate to the **API Keys** section by clicking on the "API Keys" link in the main navigation menu.
3. On the API Keys page, click the **Generate New API Key** button to create a new API key.
4. Your new API key will be displayed in the table. Keep this key secure and do not share it with others.
5. You can create multiple API keys and activate/deactivate them as needed.

### Using Your API Key

To authenticate your API requests, include your API key in the `X-API-Key` header with every request:

```bash
curl -X POST "https://your-domain.com/api/extract" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -F "files=@/path/to/your/invoice.pdf"
```

### Security Best Practices

- Keep your API keys secure and never expose them in client-side code
- Rotate your API keys periodically by generating new ones and deactivating old ones
- Only use API keys in secure, server-to-server communications
- If you suspect an API key has been compromised, deactivate it immediately
""",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/auth")
app.include_router(drive_router)
app.include_router(admin_router, prefix="/api")
app.include_router(ads_router, prefix="/api")
app.include_router(web_router) 