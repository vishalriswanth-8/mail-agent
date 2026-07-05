# LM Studio Integration Guide

## Problem Fixed
The original issue was that the endpoint path was incorrect. LM Studio expects `/v1/chat/completions` but the code was sending just `/chat/completions`.

## Changes Made

### 1. Fixed Endpoint Path in `agent/ai_engine.py`
- Changed from: `urljoin(base_url, "chat/completions")`
- Changed to: `f"{base_url}/v1/chat/completions"`

### 2. Added Better Error Handling
- Added debug logging to see raw responses from LM Studio
- Handles different response formats (some LM Studio versions use `/output` instead of `/choices`)
- Improved retry logic with exponential backoff

### 3. Added Direct Testing Endpoint in `app.py`
New endpoint: `/api/models/test-lmstudio`
- Tests LM Studio connection directly
- Shows available models
- Displays raw response for debugging
- Useful for troubleshooting

## How to Use

### Step 1: Start LM Studio
1. Launch LM Studio
2. Load your model (e.g., qwen3.5-4b)
3. Make sure it's running and responding

### Step 2: Configure Settings
In your app settings, set:
```json
{
  "ai_provider": "local",
  "local_base_url": "http://localhost:1234",
  "local_model": "qwen3.5-4b"
}
```

### Step 3: Test the Connection
Call this endpoint to test LM Studio directly:
```bash
curl -X POST http://localhost:5000/api/models/test-lmstudio \
  -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:1234", "model": "qwen3.5-4b"}'
```

Or use the web interface at your dashboard and look for a test button.

### Step 4: Enable Auto-Sync
To sync emails automatically every 5 minutes:
```bash
curl -X POST http://localhost:5000/api/sync/auto \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "interval": 300}'
```

### Step 5: Monitor Logs
Check the console output for:
- `[LMStudio] Raw response status:` - Shows if LM Studio is responding
- `[Sync] Processing email X/Y:` - Email processing progress
- `[AIEngine] Local model failed, falling back to Gemini:` - Fallback working

## Troubleshooting

### If LM Studio shows "Not responding":
1. Make sure LM Studio is running on port 1234
2. Check if `http://localhost:1234/v1/models` returns models list
3. Verify the model name matches exactly what's in LM Studio

### If you get "'choices'" error:
This means LM Studio returned a response but with unexpected format. The code now handles both `/choices` and `/output` formats.

### To switch between Local/Cloud:
1. Go to Settings in your dashboard
2. Change `ai_provider` from "local" to "cloud" or vice versa
3. Save settings - the app will immediately use the new provider

## New Features Added

1. **Direct LM Studio Testing** - Test connection without going through full email processing
2. **Better Error Messages** - Clearer logs showing exactly what's happening
3. **Auto-Sync Support** - Automatically sync emails every 5 minutes (configurable)
4. **Provider Health Monitoring** - Check which provider is healthy before using it

## API Endpoints Available

- `POST /api/models/test` - Test current AI provider configuration
- `POST /api/models/test-lmstudio` - Direct LM Studio connection test with debug output
- `GET /api/models/status` - Get current model status and health
- `POST /api/sync` - Manual email sync
- `POST /api/sync/auto` - Enable/disable auto-sync
- `GET /api/sync/auto/status` - Check auto-sync status
