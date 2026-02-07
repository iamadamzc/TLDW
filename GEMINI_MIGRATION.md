# Gemini Flash Migration Summary

## Changes Made

### 1. Dependencies (`requirements.txt`)
- **Removed:** `openai==1.99.7`
- **Added:** `google-generativeai==0.8.3`

### 2. Summarizer (`summarizer.py`)
- Completely rewritten to use **Gemini 2.0 Flash Experimental**
- Same prompt format, same timestamp linking
- Error handling updated for Gemini API responses

### 3. Security Manager (`security_manager.py`)
- Updated validation: `OPENAI_API_KEY` → `GOOGLE_API_KEY`
- Key format check: Now expects `AIza...` prefix (Google format)

---

## Environment Variables

### Local Testing (`.env`)
Add this line to your `.env` file:
```bash
GOOGLE_API_KEY=AIza...your-actual-key
```

### AWS App Runner
1. Go to **AWS App Runner Console**
2. Select **tldw-service**
3. **Configuration** → **Configure**
4. **Environment variables** → **Add**:
   - **Key:** `GOOGLE_API_KEY`
   - **Value:** `AIza...` (paste your key)
5. Click **Next** → **Deploy**

---

## Cost Comparison (Input Tokens)

| Model | Cost per 1M tokens | 100 Videos (2M tokens) |
|:---|---:|---:|
| **GPT-4o (old)** | $2.50 | $5.00 |
| **Gemini Flash (new)** | **$0.075** | **$0.15** |
| **Savings** | **97%** | **$4.85 saved** |

---

## Next Steps

1. ✅ **Add `GOOGLE_API_KEY` to `.env`** (for local testing)
2. ✅ **Add `GOOGLE_API_KEY` to App Runner** (for production)
3. 🚀 **Deploy**: Run `.\deploy-apprunner.ps1`
4. ✅ **Test**: Submit a video and check the email digest

---

## Rollback Plan (If Needed)

If Gemini Flash doesn't work as expected, you can rollback:

```bash
# In requirements.txt, replace:
google-generativeai==0.8.3
# with:
openai==1.99.7

# In summarizer.py, use the old OpenAI version
# In security_manager.py, change GOOGLE_API_KEY back to OPENAI_API_KEY
```

But you won't need to — Gemini Flash is excellent for this use case.
