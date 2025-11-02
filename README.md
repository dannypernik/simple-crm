# Flow CRM

Flow CRM is a focused follow-up assistant inspired by OnePageCRM. It centers every contact around their next action, keeps your pipeline moving, and learns from Gmail conversations to craft smart email nudges.

## Highlights

- ?? **Action-first dashboard** ? contacts are ordered by the next task due so you always know who needs attention.
- ?? **Flow for closing actions** ? marking an action complete immediately prompts you for the next one, keeping momentum.
- ?? **Gmail integration** ? connect your Gmail account (OAuth) to sync recent threads, log activity, and send scheduled emails.
- ?? **AI suggestions** ? optional OpenAI integration analyzes recent email context to suggest subject, body, and follow-up timing.
- ?? **Batch scheduling** ? review, edit, and approve suggestions in one place before committing them to the send queue.
- ?? **Auto re-approval** ? if a contact emails you before a scheduled message fires, the suggestion is paused and flagged for review.
- ?? **Flexible contact intake** ? add contacts manually or import them via CSV in seconds.

## Quickstart

1. **Clone & install**
   ```bash
   git clone <repo-url>
   cd workspace
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create the database**
   ```bash
   flask --app app db init
   flask --app app db migrate -m "Initial tables"
   flask --app app db upgrade
   ```

3. **Set environment variables** (see `.env.example` snippet below). At minimum you need `FLASK_ENV`, `SECRET_KEY`, and optionally provider keys.

4. **Run the app**
   ```bash
   flask --app app run
   ```

5. **Open the dashboard** at http://127.0.0.1:5000/ and start adding contacts.

## Configuration

| Variable | Purpose |
| --- | --- |
| `FLASK_ENV` | `development` or `production`. Defaults to `development`. |
| `SECRET_KEY` | Flask session & CSRF secret. |
| `DATABASE_URL` | SQLAlchemy connection string. Defaults to SQLite in `instance/crm.sqlite3`. |
| `SENDER_NAME` | Used in fallback email copy. |
| `OPENAI_API_KEY` | Optional. Enables AI drafting via OpenAI. |
| `OPENAI_MODEL` | Optional. Defaults to `gpt-4o-mini`. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Required for Gmail OAuth. |
| `GOOGLE_REDIRECT_URI` | Optional override. If unset, the app uses `/gmail/oauth2callback`. |

Example `.env` values:

```env
FLASK_ENV=development
SECRET_KEY=change-me
SENDER_NAME=Taylor
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:5000/gmail/oauth2callback
```

Load them locally with `python-dotenv` by creating an `.env` file or exporting them in your shell before you run Flask.

## Gmail OAuth Setup

1. Create a Google Cloud project and enable the Gmail API.
2. Configure OAuth consent for your user.
3. Create OAuth client credentials (web application) and add `http://localhost:5000/gmail/oauth2callback` as an authorized redirect URI.
4. Populate the environment variables above with the client ID/secret.
5. In Flow CRM, visit **Email Suggestions ? Sync Gmail** or the **Connect Gmail** button to start the OAuth flow.

## AI Suggestions

- When the OpenAI key is present, the app summarizes up to five recent Gmail snippets and current action context to request a follow-up draft.
- If no key is configured, Flow CRM falls back to a tasteful templated message using the contact name and action title.
- You can regenerate suggestions any time, or approve multiple drafts in the batch approval view.

## Scheduling & Re-approval

- Approved suggestions are scheduled with APScheduler and logged in the `scheduled_emails` table.
- Outgoing messages are sent through Gmail?s API using your connected account.
- When a new incoming Gmail message is synced for a contact with a scheduled email, the job is canceled and the suggestion status flips to `needs_review`, prompting you to re-approve before anything goes out.

## CSV Import Format

Supported headers (case-insensitive):

| Column | Description |
| --- | --- |
| `Name` | Required contact name |
| `Email` | Optional email |
| `Company`, `Phone`, `Notes`, `Tags` | Optional profile data |
| `Next Action` | Optional first action title |
| `Due Date` | Optional due date (`YYYY-MM-DD`, `MM/DD/YYYY`, or `DD/MM/YYYY`) |

## Development Tips

- Use `flask shell` for interactive work with `db`, `Contact`, etc.
- APScheduler runs in-process; when using the reloader you may see duplicate schedulers. Disable the reloader (`flask --app app run --no-reload`) when testing scheduled sends.
- The Gmail API client caches discovery documents; if you see discovery warnings, ensure internet access or pass `cache_discovery=False` (already configured).

## Future Enhancements

- Multi-user accounts with authentication.
- Deep Gmail history sync and thread analytics.
- Webhook integration (Gmail push notifications) instead of polling.
- Richer analytics views for action completion velocity.

---

Made with ?? to keep your relationships in flow.
