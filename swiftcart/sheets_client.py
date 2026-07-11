"""Google Sheets API — read/write the tracking spreadsheet."""
import logging
from datetime import date
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from . import config
from .models import BrandRecord

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "service_account.json"


def _get_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _fmt_date(d: Optional[date]) -> str:
    return d.isoformat() if d else ""


def ensure_header() -> None:
    svc = _get_service()
    sheet = svc.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=config.GOOGLE_SHEET_ID, range="Sheet1!A1:P1"
    ).execute()
    values = result.get("values", [])
    if not values or values[0] != config.SHEET_HEADERS:
        sheet.values().update(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [config.SHEET_HEADERS]},
        ).execute()
        log.info("Sheet header written")


def load_brands() -> list[BrandRecord]:
    """Read all rows from the sheet and return BrandRecord objects."""
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=config.GOOGLE_SHEET_ID, range="Sheet1!A2:Q"
    ).execute()
    rows = result.get("values", [])
    brands = []
    for row in rows:
        row += [""] * (17 - len(row))   # pad short rows
        try:
            brands.append(BrandRecord(
                name=row[0],
                parent=row[1],
                domain=row[2],
                est_monthly_revenue=float(row[3] or 0),
                avg_sellers=float(row[4] or 0),
                amazon_present_pct=float(row[5] or 0),
                qualifying_asins=int(row[6] or 0),
                units_per_month=int(row[7] or 0),
                score=float(row[8] or 0),
                contact_email=row[9],
                email_status=row[10] or "queued",
                send_date=_parse_date(row[11]),
                followup1_date=_parse_date(row[12]),
                followup2_date=_parse_date(row[13]),
                replied=(row[14].lower() in ("yes", "true", "1")),
                notes=row[15],
                description=row[16],
            ))
        except Exception as exc:
            log.warning("Skipping malformed row: %s", exc)
    return brands


def _parse_date(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s.strip())
    except Exception:
        return None


def upsert_brand(brand: BrandRecord) -> None:
    """Write or update one brand row (matched by brand name in column A)."""
    svc = _get_service()
    sheet = svc.spreadsheets()

    # Find existing row
    result = sheet.values().get(
        spreadsheetId=config.GOOGLE_SHEET_ID, range="Sheet1!A:A"
    ).execute()
    col_a = result.get("values", [])
    row_num = None
    for i, cell in enumerate(col_a):
        if cell and cell[0].strip().lower() == brand.name.lower():
            row_num = i + 1     # 1-indexed
            break

    row_data = [
        brand.name,
        brand.parent,
        brand.domain,
        f"{brand.est_monthly_revenue:.0f}",
        f"{brand.avg_sellers:.1f}",
        f"{brand.amazon_present_pct:.1f}",
        str(brand.qualifying_asins),
        str(brand.units_per_month),
        f"{brand.score:.3f}",
        brand.contact_email,
        brand.email_status,
        _fmt_date(brand.send_date),
        _fmt_date(brand.followup1_date),
        _fmt_date(brand.followup2_date),
        "Yes" if brand.replied else "No",
        brand.notes,
        brand.description,
    ]

    if row_num:
        range_str = f"Sheet1!A{row_num}:P{row_num}"
        sheet.values().update(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range=range_str,
            valueInputOption="RAW",
            body={"values": [row_data]},
        ).execute()
    else:
        sheet.values().append(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range="Sheet1!A:Q",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_data]},
        ).execute()
