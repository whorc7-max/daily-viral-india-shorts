# Setup: Daily Silent Hindi Shorts

## 1. Add GitHub Secrets

Open the repository's **Settings -> Secrets and variables -> Actions** and add:

- `GEMINI_API_KEY`: create or use an existing key from Google AI Studio.
- `PEXELS_API_KEY`: optional; get a free key from Pexels. Without it, the workflow uses generated backgrounds.
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, and `YT_REFRESH_TOKEN`: YouTube OAuth credentials.

The OAuth app must enable **YouTube Data API v3**, and your Google account must be added as a test user while the app is in testing mode.

## 2. Test privately

Create the repository variable `YT_PRIVACY_STATUS` with value `unlisted`. Run the workflow manually from **Actions** and inspect the uploaded Short.

After the output is correct, change the variable to `public`.

## 3. Schedule

The workflow runs twice per day. GitHub Actions uses UTC; edit `.github/workflows/schedule.yml` to change the times.
