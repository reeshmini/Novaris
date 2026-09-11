NOVARIS — QUICK STREAMLIT COMMUNITY CLOUD DEPLOYMENT

1. Create a GitHub repository, e.g. "novaris".
2. Upload these files to the repository root:
   - streamlit_app.py
   - requirements.txt
   - .gitignore

   Do NOT upload your real .env or secrets.toml.

3. Go to https://share.streamlit.io and sign in / connect GitHub.
4. Click "Create app" -> "Yup, I have an app".
5. Select:
   Repository: your NOVARIS repo
   Branch: main
   Main file path: streamlit_app.py

6. Open Advanced settings -> Secrets.
7. Copy the values from your local .env into TOML format.
   See secrets.toml.example in this package.

8. Save the secrets and click Deploy.

9. Wait for the app to build. Streamlit will give you a
   https://<name>.streamlit.app URL.

NOTES FOR THIS DEMO VERSION
- This preserves the current NOVARIS session-state / API architecture.
- It does not add PostgreSQL yet.
- Data persistence is still session-based.
- For a mentor demo, that is fine.
- PostgreSQL can be added after the meeting without changing the visual design.
