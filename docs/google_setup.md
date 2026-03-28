# Google Calendar Setup Guide for Klara

This guide walks you through connecting your Google Calendar to Klara.
You will be creating OAuth 2.0 credentials so Klara can read (but never modify)
your calendar. This takes about 10 minutes and only needs to be done once.

---

## Prerequisites

- A Google account (the same Gmail you want Klara to read)
- A web browser

---

## Step 1 — Create a Google Cloud Project

1. Open your browser and go to **https://console.cloud.google.com**

2. Sign in with your Google account if prompted.

3. At the very top of the page, click the **project selector dropdown**
   (it shows your current project name or "Select a project" next to the Google Cloud logo).

4. In the popup that appears, click **"NEW PROJECT"** in the top-right corner.

5. Fill in the form:
   - **Project name:** `Personal Ops Agent`
   - **Location:** Leave as "No organization" (default)

6. Click **"CREATE"**.

7. Wait a few seconds. A notification will appear saying the project was created.
   Click **"SELECT PROJECT"** in that notification, or use the project selector dropdown
   again and click on "Personal Ops Agent".

   > You should now see "Personal Ops Agent" in the top bar where the project name appears.

---

## Step 2 — Enable the Google Calendar API

1. In the left sidebar, click **"APIs & Services"** → **"Library"**.
   (If the sidebar is collapsed, click the hamburger menu ≡ in the top-left first.)

2. In the search box that says "Search for APIs & Services", type **`Google Calendar`**.

3. Click on **"Google Calendar API"** in the results (it has a blue calendar icon).

4. Click the blue **"ENABLE"** button.

5. Wait a few seconds. The page will reload and show the API overview.
   You should see a green checkmark and "API enabled" confirmation.

---

## Step 3 — Configure the OAuth Consent Screen

Before creating credentials, Google requires you to configure what your app is.

1. In the left sidebar, click **"APIs & Services"** → **"OAuth consent screen"**.

2. Under "User Type", select **"External"**.
   (This is required even though it's just for your personal use.)

3. Click **"CREATE"**.

4. Fill in the **App information** form:
   - **App name:** `Personal Ops Agent`
   - **User support email:** Select your Gmail address from the dropdown
   - **App logo:** Skip this (not required)
   - **Developer contact information** (at the bottom): Enter your Gmail address

5. Click **"SAVE AND CONTINUE"**.

6. On the **Scopes** page: Click **"SAVE AND CONTINUE"** without adding anything.
   (Klara will request the scope at runtime.)

7. On the **Test users** page:
   - Click **"+ ADD USERS"**
   - Type your own Gmail address in the field
   - Click **"ADD"**
   - You should see your email appear in the test users list

8. Click **"SAVE AND CONTINUE"**.

9. On the **Summary** page, review and click **"BACK TO DASHBOARD"**.

   > Your app is now in "Testing" mode. This is fine — it means only the test users
   > you added can authorize it, which is exactly what you want for personal use.

---

## Step 4 — Create OAuth 2.0 Credentials

1. In the left sidebar, click **"APIs & Services"** → **"Credentials"**.

2. Click **"+ CREATE CREDENTIALS"** at the top of the page.

3. Select **"OAuth client ID"** from the dropdown.

4. Under **"Application type"**, select **"Desktop app"**.

5. Under **"Name"**, you can leave the default or type `Klara Desktop`.

6. Click **"CREATE"**.

7. A popup appears showing your **Client ID** and **Client Secret**.
   Don't worry about copying these — you're going to download the full JSON file.

8. Click **"DOWNLOAD JSON"** (the download icon button).
   This downloads a file named something like `client_secret_....json`.

9. Click **"OK"** to close the popup.

---

## Step 5 — Save the Credentials File

1. Locate the downloaded file (usually in your Downloads folder).
   It will be named something like `client_secret_123456789-abc.apps.googleusercontent.com.json`.

2. **Rename it** to exactly: `credentials.json`

3. **Move it** to the following location inside the Klara project directory:

   ```
   personal-ops-agent/
   └── config/
       └── credentials/
           └── credentials.json   ← put it here
   ```

   The full path should look like:
   ```
   C:\Users\<you>\...\personal-ops-agent\config\credentials\credentials.json
   ```

   > This file is already listed in `.gitignore` — it will never be committed to git.

---

## Step 6 — First-Time Authorization

The first time Klara tries to access your calendar, she will:

1. Open your **default web browser** automatically (or print a URL for you to open).
2. Ask you to **sign in to Google** and select your account.
3. Show a warning screen: **"Google hasn't verified this app"**
   - Click **"Advanced"** (bottom-left link)
   - Click **"Go to Personal Ops Agent (unsafe)"**
   - This is safe — you created this app yourself.
4. Show the permissions screen: **"Personal Ops Agent wants to access your Google Account"**
   - It will request: *"See your Google Calendar events"* (read-only)
   - Click **"Allow"**
5. Show a success page. You can close the browser tab.

After this, Klara saves a `token.json` file to `config/credentials/` so you won't
need to authorize again. That file is also gitignored.

---

## Verify It's Working

Run Klara from the project root:

```bash
python main.py
```

If everything is set up correctly, Klara will greet you and her first message
will reference your actual calendar events for today.

If you see an error, check that:
- `config/credentials/credentials.json` exists and is valid JSON
- You added your Gmail as a test user in Step 3
- You enabled the Google Calendar API in Step 2

---

## Required OAuth Scope

Klara requests only the minimum necessary permission:

| Scope | Access |
|-------|--------|
| `https://www.googleapis.com/auth/calendar.readonly` | Read your calendar events (no write access) |

Klara can **never** create, modify, or delete events. When she suggests a scheduling
action, she is only showing you a proposal — you take the action yourself.
