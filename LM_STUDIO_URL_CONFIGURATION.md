# LM Studio URL Configuration Guide

## The Problem
When configuring LM Studio, you were getting this error:
```
Unexpected endpoint or method. (POST /v1/v1/chat/completions)
```

This happened because the URL had **double `/v1/`** in the path.

## The Solution

### Correct URL Formats

#### Option 1: Without `/v1` prefix (Recommended for testing)
```
http://localhost:1234
```
- This will automatically use endpoint: `http://localhost:1234/v1/chat/completions`

#### Option 2: With `/v1` prefix (For OpenAI-compatible APIs)
```
http://localhost:1234/v1
```
- This will automatically use endpoint: `http://localhost:1234/v1/chat/completions`

### What We Fixed

The code now intelligently handles both URL formats:

```python
# If URL ends with /v1, don't add it again
if base_url.endswith("/v1"):
    endpoint = f"{base_url}/chat/completions"
else:
    # LM Studio uses /v1/chat/completions endpoint (OpenAI-compatible API)
    endpoint = f"{base_url}/v1/chat/completions"
```

## How to Configure in Settings Modal

### Method 1: Simple URL (Recommended)
1. Open **Agent Settings** modal
2. Select **Local LM Studio** provider
3. Set `LM Studio URL` to: `http://localhost:1234`
4. Click **Test Local Model** button
5. Should show: ✓ Local: OK

### Method 2: With /v1 Prefix
1. Open **Agent Settings** modal  
2. Select **Local LM Studio** provider
3. Set `LM Studio URL` to: `http://localhost:1234/v1`
4. Click **Test Local Model** button
5. Should show: ✓ Local: OK

## Testing Steps

### Step 1: Start LM Studio
1. Launch LM Studio application
2. Load your model (e.g., qwen3.5-4b)
3. Wait for it to start serving on port 1234

### Step 2: Verify Endpoint
Test if LM Studio is responding:
```bash
# Test without /v1 prefix
curl http://localhost:1234/v1/models

# OR test with /v1 prefix  
curl http://localhost:1234/v1/models
```

Both should return a list of available models.

### Step 3: Configure in App
1. Open your dashboard at `http://localhost:5000`
2. Click **Agent Settings** (person icon)
3. Set URL to either format above
4. Click **Test Local Model** button

### Step 4: Verify Success
You should see:
```
✓ Local: OK qwen3.5-4b
```

## Common Issues & Solutions

### Issue: Still getting double /v1/ error
**Solution**: Check your URL in the settings modal. Make sure it's either:
- `http://localhost:1234` (no /v1)
- OR `http://localhost:1234/v1` (with /v1, but not double)

### Issue: LM Studio not responding at all
**Solutions**:
1. Make sure LM Studio is running on port 1234
2. Check if you're using the correct host (localhost vs 127.0.0.1)
3. Verify the model name matches exactly what's in LM Studio

### Issue: Model not detected
**Solutions**:
1. Ensure the model is loaded in LM Studio
2. Check the exact model name (case-sensitive)
3. Try auto-detection by leaving the model field blank

## API Endpoints Used

The fixed code now correctly handles these endpoints based on URL format:

| URL Format | Models Endpoint | Chat Completions Endpoint |
|------------|-----------------|---------------------------|
| `http://localhost:1234` | `/v1/models` | `/v1/chat/completions` |
| `http://localhost:1234/v1` | `/models` | `/chat/completions` |

## Best Practices

✅ **Use simple URL format**: `http://localhost:1234` (without /v1)  
✅ **Test before syncing**: Always test individual models first  
✅ **Check logs**: Console shows detailed LM Studio response info  
✅ **Auto-detect model**: Leave model field blank to auto-detect from LM Studio  
