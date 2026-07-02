# Newsletter Intelligence Harvester

Automated daily pipeline that reads `leonidaseldarov@gmail.com`'s newsletter inbox,
extracts geopolitical/macroeconomic intelligence via DeepSeek, and feeds results
into the Gazzetta di Kyiv data pipeline.

## Architecture

```
Gmail Inbox (leonidaseldarov@gmail.com)
     │
     ▼  Gmail API (OAuth 2.0)
     │
GCP Cloud Scheduler (07:00 UTC = 10:00 Kyiv)
     │
     ▼
Cloud Run Job: gazzetta-newsletter-harvester
     │
     ├── Detect newsletters (List-Unsubscribe headers + heuristics)
     ├── DeepSeek extraction (summary, bullets, topics, narrative_matches, value_score)
     ├── data/newsletters.json (rolling 30-day window)
     ├── gazzetta.db → newsletters table
     └── Telegram digest → _TCH channel (high-value items only, score ≥ 7)
```

## Setup (One Time)

### Step 1 — Get OAuth credentials from Google Cloud Console

1. Go to: https://console.cloud.google.com/apis/credentials?project=project-b7155ed8-61c1-491f-a36
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: `Newsletter Harvester`
5. Download JSON → save as `client_secret.json` in project root

### Step 2 — Run OAuth setup (forwards a URL to your friend)

```bash
# Activate venv first
source venv/bin/activate

# Install Google auth libs
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client google-cloud-secret-manager

# Run the setup — opens a browser
python scripts/gmail_oauth_setup.py
```

**→ Send the browser URL to `leonidaseldarov@gmail.com`**
They click it once, grant access, done forever.

The script saves a `.gmail_token.json` file in the project root.

### Step 3 — Run the full cloud setup

```bash
bash ops/setup_newsletter.sh
```

This script:
- Enables required GCP APIs
- Creates a `newsletter-harvester` service account
- Stores the Gmail token in Secret Manager
- Builds the Docker image via Cloud Build
- Deploys it as a Cloud Run Job
- Creates a Cloud Scheduler job (daily at 07:00 UTC)

## Manual Operation

```bash
# Trigger immediately on Cloud Run
gcloud run jobs execute gazzetta-newsletter-harvester \
  --region=us-central1 \
  --project=project-b7155ed8-61c1-491f-a36

# Dry run locally (no DeepSeek calls, no writes)
python scripts/fetch_newsletters.py --dry-run --days=7

# Test on 3 emails, print output
python scripts/fetch_newsletters.py --test-sample

# Look back 7 days
python scripts/fetch_newsletters.py --days=7 --telegram

# View Cloud Run job logs
gcloud run jobs executions list \
  --job=gazzetta-newsletter-harvester \
  --region=us-central1 \
  --project=project-b7155ed8-61c1-491f-a36
```

## Output Format

`data/newsletters.json`:
```json
{
  "generated_at": "2026-07-02T07:01:23Z",
  "count": 23,
  "items": [
    {
      "id": "gmail_message_id",
      "received_at": "2026-07-02T06:14:00+00:00",
      "sender": "Arnaud Bertrand <newsletter@bertrand.com>",
      "sender_name": "Arnaud Bertrand",
      "subject": "The Great Power Competition Weekly",
      "newsletter_confidence": 0.95,
      "summary": "China accelerated its semiconductor investment...",
      "bullets": ["point 1", "point 2", "point 3"],
      "topics": ["geopolitics", "semiconductor", "china"],
      "narrative_matches": ["china_tech_decoupling"],
      "links": [{"url": "...", "context": "..."}],
      "data_points": [{"stat": "$47B investment", "source": "MIIT"}],
      "value_score": 8,
      "value_score_reason": "Hard data on narrative-relevant investment",
      "raw_word_count": 1240,
      "language": "en"
    }
  ]
}
```

## Cost Estimate

| Resource | Cost/month |
|---|---|
| Cloud Run Job (daily, ~2min) | ~$0.01 |
| Cloud Scheduler | $0.10 |
| DeepSeek (25 newsletters × 30 days) | ~$1.50 |
| Secret Manager | ~$0.06 |
| **Total** | **~$1.70/month** |

## Security

- Gmail token stored in **GCP Secret Manager** (never in code or env files)
- `.gmail_token.json` and `client_secret.json` are in `.gitignore`
- Cloud Run Job uses a dedicated service account with minimal permissions
- Gmail access is **read-only** (`gmail.readonly` scope)
