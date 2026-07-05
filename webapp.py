#!/usr/bin/env python3
"""
Local web UI for the invoice → Amazon profitability scanner.

Usage:
    python webapp.py
    Then open http://localhost:5000 and upload a CSV/Excel/PDF invoice.

Single-user local tool — results are kept in memory for the CSV download
link, no database or session handling needed.
"""
import csv
import io
import logging
import os
import tempfile

from flask import Flask, render_template_string, request

from swiftcart.invoice_scanner import scan_invoice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = Flask(__name__)
_last_results = []

PAGE = """
<!doctype html>
<title>Invoice Scanner</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
  table { border-collapse: collapse; width: 100%; margin-top: 1.5rem; font-size: 0.9rem; }
  th, td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; text-align: right; }
  th:nth-child(-n+3), td:nth-child(-n+3) { text-align: left; }
  .buy { color: #0a7d2c; font-weight: 600; }
  .marginal { color: #a06a00; }
  .skip { color: #999; }
  .error { color: #b00020; }
  form { margin-top: 1rem; display: flex; gap: 0.5rem; align-items: center; }
</style>
<h1>Invoice &rarr; Amazon Profitability Scanner</h1>
<form method="post" enctype="multipart/form-data">
  <input type="file" name="invoice" accept=".csv,.xlsx,.xls,.pdf" required>
  <select name="channel">
    <option value="FBA">FBA</option>
    <option value="FBM">FBM</option>
  </select>
  <button type="submit">Scan</button>
</form>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{% if results %}
  <p>{{ buys }}/{{ results|length }} SKUs are BUY at current thresholds. <a href="/download.csv">Download CSV</a></p>
  <table>
    <tr>
      <th>UPC</th><th>ASIN</th><th>Description</th><th>Sell</th><th>Cost</th>
      <th>Fees</th><th>Profit</th><th>Margin %</th><th>ROI %</th><th>Verdict</th>
    </tr>
    {% for r in results %}
    <tr>
      <td>{{ r.upc }}</td><td>{{ r.asin }}</td><td>{{ r.description }}</td>
      <td>{{ "%.2f"|format(r.sell_price) }}</td><td>{{ "%.2f"|format(r.cost_per_unit) }}</td>
      <td>{{ "%.2f"|format(r.referral_fee + r.fulfillment_fee) }}</td>
      <td>{{ "%.2f"|format(r.profit_per_unit) }}</td>
      <td>{{ r.margin_pct }}</td><td>{{ r.roi_pct }}</td>
      <td class="{{ r.verdict }}">{{ r.verdict }}</td>
    </tr>
    {% endfor %}
  </table>
{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def index():
    global _last_results
    error = None
    results = _last_results

    if request.method == "POST":
        file = request.files.get("invoice")
        channel = request.form.get("channel", "FBA")
        if not file or not file.filename:
            error = "Please choose a file."
        else:
            suffix = os.path.splitext(file.filename)[1]
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
            try:
                results = scan_invoice(tmp_path, channel=channel)
                _last_results = results
                if not results:
                    error = "No SKUs matched to Amazon listings."
            except Exception as exc:
                logging.exception("Scan failed")
                error = f"Scan failed: {exc}"
            finally:
                os.unlink(tmp_path)

    buys = sum(1 for r in results if r.verdict == "buy")
    return render_template_string(PAGE, results=results, error=error, buys=buys)


@app.route("/download.csv")
def download_csv():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "UPC", "ASIN", "Description", "Channel", "Cost", "Sell Price",
        "Referral Fee", "Fulfillment Fee", "Profit/Unit", "Margin %",
        "ROI %", "Units/mo", "Verdict",
    ])
    for r in _last_results:
        writer.writerow([
            r.upc, r.asin, r.description, r.channel, r.cost_per_unit, r.sell_price,
            r.referral_fee, r.fulfillment_fee, r.profit_per_unit, r.margin_pct,
            r.roi_pct, r.units_per_month, r.verdict,
        ])
    return app.response_class(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoice_scan.csv"},
    )


if __name__ == "__main__":
    app.run(debug=False, port=5000)
