# Quick Start Guide - Auto-Sync & Model Switching

## TL;DR - What Was Fixed and Added

| Issue | Solution |
|-------|----------|
| ❌ Local model not categorizing emails | ✅ Enhanced logging and error handling |
| ❌ Have to manually sync for every new mail | ✅ **New: Auto-sync feature** (automatic!) |
| ❌ Can't switch models easily | ✅ **New: Model switching in Agent Settings** |

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Open Agent Settings
Click the **gear icon** (⚙️) in the left sidebar titled "Agent Settings"

### Step 2: Enable Auto-Sync
In the **"Email Synchronization"** section:
- ✅ Check **"Enable Auto-Sync"**
- Set interval to **300** (5 minutes) - adjust if needed
- Click **"Save Settings"**

**Done!** Your emails will now sync automatically every 5 minutes.

### Step 3: Test Your Model (Optional)
In the **"Model Provider"** section:
- Choose **"Local LM Studio"** or **"Cloud Gemini"**
- Click **"Test Connection"**
- Should see: ✅ "Connection successful"

---

## 📍 Where Things Are

### Agent Settings Layout:
```
┌─────────────────────────────────────┐
│      Current Model Status           │  ← Shows if model is working
├─────────────────────────────────────┤
│      Model Provider                 │  ← Choose Local or Cloud
│  - Local LM Studio / Cloud Gemini   │
│  - Force Selected Provider (new!)   │
│  - Test Connection button           │
├─────────────────────────────────────┤
│   Email Synchronization (new!)      │  ← Auto-sync controls
│  - Enable Auto-Sync                 │
│  - Sync Interval                    │
├─────────────────────────────────────┤
│   Your Personal Info & Preferences  │  ← Agent persona
├─────────────────────────────────────┤
│   Save Settings button              │
└─────────────────────────────────────┘
```

---

## 🔄 How Auto-Sync Works

**Before** (Manual):
1. Click "Sync" button
2. Wait for emails to load
3. See categorized emails
4. Repeat when new mail comes

**After** (Automatic):
1. Enable auto-sync once
2. System runs sync every 5 minutes automatically
3. New emails appear in inbox automatically
4. You keep working - no manual action needed!

---

## 🤖 Local vs Cloud Model

### Local Model (LM Studio)
**Pros:**
- 🔒 Private - stays on your computer
- ⚡ Fast - no internet needed
- 💰 Free - no API costs

**Cons:**
- 📦 Needs LM Studio installed and running
- 🖥️ Uses computer resources
- Slower on low-end machines

**Setup:** Select "Local LM Studio" → Enter URL → Test → Save

### Cloud Model (Gemini)
**Pros:**
- 🌐 Always available - no setup needed
- ⚡ Very fast processing
- 🎯 More accurate for reasoning

**Cons:**
- 🔌 Needs internet connection
- ☁️ Data sent to Google servers
- Could have API limits

**Setup:** Select "Cloud Gemini" → Test → Save

---

## 🔧 Settings Explained

### **Enable Auto-Sync**
- ✅ Checked = System syncs automatically
- ⬜ Unchecked = Manual sync only (click button)

### **Sync Interval (seconds)**
- `60-120` = Very frequent, uses more API calls
- `300` = 5 min (recommended) 👈
- `600` = 10 min (good for quiet inbox)
- `900+` = Rarely sync, miss emails longer

### **Force Selected Provider**
- ✅ Checked = Use ONLY selected model, never switch
  - Use if you want guaranteed local/cloud
  - Will fail if model offline
  
- ⬜ Unchecked = Smart fallback (recommended) 👈
  - If local fails, tries cloud automatically
  - Best of both worlds

---

## 📊 Current Model Status

Shows you at a glance if your model is working:

```
🟢 LOCAL - ✓ Healthy
Model: qwen3.5-4b
URL: http://127.0.0.1:1234
Status: LM Studio responded successfully
```

or

```
🔴 CLOUD - ✗ Not responding
Model: gemini-3.5-flash
Status: Connection timeout - check internet
```

---

## ✅ Checklist

- [ ] Opened Agent Settings
- [ ] Enabled Auto-Sync
- [ ] Set interval (default 300s is fine)
- [ ] Selected preferred model (Local or Cloud)
- [ ] Clicked "Test Connection" - saw ✓ success
- [ ] Clicked "Save Settings"
- [ ] Received toast notification "Settings saved successfully"

**You're all set!** 🎉

---

## 🆘 If Something Goes Wrong

### Emails not syncing automatically?
1. Check if "Enable Auto-Sync" is ✅ checked
2. Wait for the set interval (300s = 5 min by default)
3. Refresh browser to see new emails
4. Check Model Status in Agent Settings

### Model shows "Not responding"?
- **Local**: Make sure LM Studio is running on configured URL
- **Cloud**: Make sure internet connection works
- Click "Test Connection" again to retry

### Emails not categorized?
1. Check Model Status - must show ✓ Healthy
2. Look at terminal logs to see which model failed
3. Try switching to the other provider
4. Manually sync to reprocess emails

---

## 📝 Terminal Logs (For Debugging)

When auto-sync runs, you'll see logs like:
```
[AutoSync] Starting periodic sync for 1 account(s)
[Sync] Starting sync for user@gmail.com
[Sync] Fetched 5 emails from user@gmail.com
[Sync] Processing email 1/5: "Important Meeting"
[Sync]   -> local model: work / important
[Sync] Processing email 2/5: "Promotional offer"
[Sync]   -> cloud model: promotion / normal
[Sync] Completed sync for user@gmail.com
```

This shows which model (local or cloud) processed each email and what category it assigned.

---

## 🎯 Common Scenarios

### Scenario 1: I want everything automatic
- ✅ Enable Auto-sync (5 min interval)
- Select Cloud Gemini (always available)
- Uncheck "Force Selected Provider"
- Forget about it - it just works!

### Scenario 2: I want to protect my privacy
- ✅ Enable Auto-sync
- Select Local LM Studio
- ✅ Check "Force Selected Provider"
- Keep LM Studio running

### Scenario 3: I want speed and reliability
- ✅ Enable Auto-sync (3-5 min interval)
- Select Cloud Gemini
- ✅ Check "Force Selected Provider"
- Fast categorization, no fallback needed

### Scenario 4: I want maximum compatibility
- ✅ Enable Auto-sync
- Select either (doesn't matter)
- ⬜ Uncheck "Force Selected Provider"
- System uses best available model automatically

---

## 💡 Pro Tips

1. **Sync interval**: Start with 5 minutes, adjust based on your email volume
2. **Test first**: Always click "Test Connection" after changing providers
3. **Check status**: Look at "Current Model Status" if something seems wrong
4. **Read logs**: Terminal logs show you exactly what's happening

---

## 🎓 What's Happening Behind The Scenes

When you enable auto-sync:
1. Flask server starts a background thread
2. Thread wakes up every X seconds
3. Fetches new emails from Gmail API
4. Processes each email through selected AI model
5. Stores category, priority, summary in database
6. Goes back to sleep, repeats

All while you work - you don't need to do anything!

---

Enjoy your improved mail management! 🚀
