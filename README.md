# InvoiceLens API

InvoiceLens is a lightweight invoice extraction API built on top of [`invoice-x/invoice2data`](https://github.com/invoice-x/invoice2data).

It accepts digital PDF invoices, matches them against proven supplier templates, and returns structured JSON with fields like issuer, invoice number, date, amount, currency, VAT, and line items.

## Why this is worth paying for

Finance teams and ops teams still waste time copy-pasting invoice fields into ERPs, spreadsheets, and bookkeeping tools. InvoiceLens packages a strong open-source parser behind a dead-simple REST API with usage controls.

## Endpoints

- `GET /health`
- `POST /extract`

## Auth and quotas

Send `X-API-Key`.

- Free: `100` requests/day
- Pro: `10,000` requests/day

Environment variables:

- `FREE_KEYS` (default: `free-demo-key`)
- `PRO_KEYS` (default: `pro-demo-key`)
- `FREE_LIMIT` (default: `100`)
- `PRO_LIMIT` (default: `10000`)
- `MAX_FILE_BYTES` (default: `10485760`)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8011
```

Example request:

```bash
curl -X POST \
  -H 'Content-Type: application/pdf' \
  -H 'X-API-Key: free-demo-key' \
  --data-binary @invoice.pdf \
  http://127.0.0.1:8011/extract
```

## Validation

- 10/10 sample invoices from the upstream test corpus matched expected fixture fields
- OpenAPI spec generated at `openapi.json`
- Dockerfile included for container deployment

## Security notes

- The app runs with explicit API keys and daily quotas.
- The extraction path prefers Poppler `pdftotext`, then falls back to `pdfminer` if needed.
- Current shipped stack versions were checked against OSV. Remaining notable transitive risk: `pdfminer.six` and `Pillow` advisories inherited via PDF tooling; mitigation is to keep versions current and run the service non-root in deployment.
