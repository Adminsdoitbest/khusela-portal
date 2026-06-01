# Khusela Auto-Submit Portal — Replit Setup Guide

## What you need
- A free Replit account (replit.com)
- The 4 files in this folder: app.py, requirements.txt, .replit, setup.py

---

## Step 1 — Create a Replit account
1. Go to https://replit.com and click **Sign Up**
2. Sign up with Google or your email address (free)

---

## Step 2 — Create a new Repl
1. Click the blue **+ Create Repl** button (top left)
2. Choose **Python** as the template
3. Name it: `khusela-portal`
4. Click **Create Repl**

---

## Step 3 — Upload the files
1. In the left panel, click the **Files** icon (folder icon)
2. Click the three dots (⋯) next to "Files" → **Upload file**
3. Upload all 4 files: `app.py`, `requirements.txt`, `.replit`, `setup.py`
4. If Replit created a `main.py`, you can delete it (right-click → Delete)

---

## Step 4 — Run first-time setup (do this ONCE only)
1. Click the **Shell** tab at the bottom of the screen
2. Type this command and press Enter:
   ```
   python setup.py
   ```
3. Wait for it to finish (it downloads the Chromium browser — takes 1–2 minutes)
4. You'll see: ✅ Setup complete!

---

## Step 5 — Start the portal
1. Click the green **Run** button at the top
2. After a few seconds, a web preview will appear on the right
3. Copy the URL from the preview — it looks like:
   `https://khusela-portal.YOUR-USERNAME.repl.co`
4. **Save this URL** — this is the link you share with your assistant

---

## Step 6 — Keep it always-on (optional, recommended)
By default, Replit sleeps after 30 minutes of inactivity.
To keep it always awake:
1. Click the **three dots** next to your Repl name
2. Go to **Settings**
3. Enable **Always On** (requires Replit Core ~$7/month)
   OR use a free service like https://uptimerobot.com to ping the URL every 5 minutes

---

## How your assistant uses the portal
1. Open the saved URL in any browser
2. Drag and drop the CSV file onto the upload area
3. Review the member preview table
4. Click **Submit All Applications**
5. Watch the live log — ✅ = submitted, ❌ = error

---

## CSV format reminder
The file must use **semicolons (;)** as separators with these column headers:

```
SURNAME;NAME;ID NUMBER;CELL NUMBER;BRANCH CODE;ACC NUMBER;ADDRESS;DEDUCTION DATE;PLAN TYPE
```

- PLAN TYPE: use `Khusela Core R89` or `Khusela Elite R129`
- DEDUCTION DATE: use DD/MM/YYYY format, e.g. `15/06/2026`

---

## Troubleshooting
- **"Browser not found" error** → Run `python setup.py` again in the Shell
- **Form fields not filling** → The Tripetto form may have updated; contact your developer to adjust the selectors in app.py
- **Portal not loading** → Click the green Run button again

---

*Built for Khusela Dignity Plan — automated with Playwright + Flask*
