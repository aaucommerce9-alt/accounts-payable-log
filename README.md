# Amazon Bookkeeping Auto-Sync Tool — v1

Pulls every financial transaction from Amazon SP-API, applies your COGS and
profit-share rules, and writes everything into your Excel workbook.  
Reconciles each settlement cycle to the cent against your actual Amazon payout.

---

## Step 1 — SP-API Credentials (do this first)

You need **three values** from Amazon Seller Central:

| Value | Where to get it |
|---|---|
| **LWA Client ID** | Seller Central → Apps & Services → Develop Apps → Your app → View credentials |
| **LWA Client Secret** | Same page |
| **Refresh Token** | See below |

### Registering the developer app & getting a Refresh Token

1. Go to **Seller Central → Apps & Services → Develop Apps**.
2. Click **Add new app client** (or use an existing one).
3. Under **IAM ARN**, enter `arn:aws:iam::899787423542:role/SellerAPIRole`  
   *(Amazon's shared role for self-authorisation — fine for a personal tool)*.
4. On the **Data access** tab, add the **Finance & Accounting** role.  
   *(Also add "Direct to Consumer Shipping" if you want order-level items.)*
5. Save and note your **Client ID** and **Client Secret**.
6. To get the **Refresh Token**, open this URL in your browser  
   (replace `YOUR_CLIENT_ID` and `YOUR_SELLER_ID`):

```
https://sellercentral.amazon.com/apps/authorize/consent
  ?application_id=YOUR_CLIENT_ID
  &state=random_string
  &version=beta
```

   Authorise the app → Amazon redirects you to your callback URL with a  
   `spapi_oauth_code` parameter. Exchange it:

```bash
curl -X POST https://api.amazon.com/auth/o2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=<spapi_oauth_code>" \
  -d "client_id=<YOUR_CLIENT_ID>" \
  -d "client_secret=<YOUR_CLIENT_SECRET>" \
  -d "redirect_uri=<YOUR_REDIRECT_URI>"
```

   The response contains `refresh_token` — save that permanently.

---

## Step 2 — Installation

```bash
# Python 3.10+ required
pip install -r requirements.txt
```

---

## Step 3 — Configure `config.yaml`

Open `config.yaml` and fill in the marked fields:

```yaml
sp_api:
  lwa_app_id:        "amzn1.application-oa2-client.XXXX"   # ← your Client ID
  lwa_client_secret: "XXXX"                                 # ← your Client Secret
  refresh_token:     "Atzr|XXXX"                            # ← your Refresh Token

paths:
  workbook:  "/Users/you/Documents/bookkeeping.xlsx"        # ← path to your Excel file
```

Everything else has sensible defaults you can adjust at any time.

### Cost Master sheet

Your workbook must contain a sheet named **Cost Master** (or whatever you set in
`config.yaml → paths.cost_master_tab`) with **at least** these columns:

| SKU | COGS | Supplier |
|---|---|---|
| B07XYZ | 4.99 | HDS Trading Corp |

Column names must match `config.yaml → cost_master`.

### Profit-share base ⚠️

Before your first live run, confirm which figure the 12 % / 10 % is applied to
and update `config.yaml → profit_share.base`:

| Value | Meaning |
|---|---|
| `net_profit` | (net proceeds − COGS) — **default, confirm with owner** |
| `gross_profit` | gross sales − COGS |
| `net_sales` | gross sales − promotions − refunds |

---

## Step 4 — Running the tool

```bash
# One-shot sync (recommended to start)
python main.py

# Run now, then automatically every day at midnight
python main.py --schedule

# Re-pull everything from the initial lookback window
python main.py --reset-sync

# Re-run reconciliation only (no new data pull)
python main.py --reconcile-only

# Use a different config file
python main.py --config /path/to/config.yaml
```

### Scheduling without `--schedule` flag

**macOS/Linux (cron):**
```
0 6 * * * /usr/bin/python3 /path/to/main.py >> /path/to/data/cron.log 2>&1
```

**Windows (Task Scheduler):**  
Create a Basic Task → Action: `python C:\path\to\main.py`

---

## Output

| File / Tab | Contents |
|---|---|
| `Transactions` tab | One row per financial transaction, all fields |
| `Monthly Summary` tab | Totals by month (sales, fees, COGS, profit-share, net) |
| `data/sync.log` | Full audit trail of every sync, warnings, flags |
| `data/last_sync.json` | Incremental sync marker (don't delete manually) |

---

## Reconciliation

After each **closed** settlement cycle, the tool compares its computed net total
to Amazon's actual deposited amount:

- **VERIFIED** — matches to the cent (within $0.01 tolerance) ✓  
- **DISCREPANCY** — gap details printed to console and logged; **action required**

If you see a discrepancy, check `data/sync.log` for any lines beginning with
`UNKNOWN financial event type` — those are transaction types not yet mapped.

---

## Libraries used

| Library | Purpose |
|---|---|
| `requests` | SP-API HTTP calls |
| `openpyxl` | Excel read/write |
| `pandas` | (available for future analytics) |
| `PyYAML` | Config file |
| `schedule` | Daily scheduling |
| `python-dateutil` | Date parsing |

---

## v2 roadmap (out of scope for v1)

- Walmart Marketplace API module (parallel to Amazon)
- Dashboard / charts view
- Alerts: negative-margin sales, fee spikes, missing COGS
