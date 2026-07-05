"""Invoice parsing — extract line items from PDF/Excel/CSV invoices."""
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from .models import InvoiceLineItem

log = logging.getLogger(__name__)

_UPC_COLS = ["upc", "gtin", "ean", "barcode", "upc code", "upc/ean"]
_DESC_COLS = ["description", "item description", "product name", "item", "product", "title"]
_COST_COLS = ["unit cost", "cost per unit", "cost/unit", "unit price", "wholesale price", "cost", "price"]
_QTY_COLS = ["qty ordered", "order qty", "qty", "quantity", "units"]
_SKU_COLS = ["supplier sku", "item number", "item no", "item #", "sku", "model"]


def parse_invoice(path: str) -> list[InvoiceLineItem]:
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(path, dtype=str)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    elif ext == ".pdf":
        df = _parse_pdf_table(path)
    else:
        raise ValueError(f"Unsupported invoice format: {ext}")

    return _rows_to_line_items(df)


def _parse_pdf_table(path: str) -> pd.DataFrame:
    import pdfplumber

    frames = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or len(table) < 2:
                    continue
                header, *rows = table
                frames.append(pd.DataFrame(rows, columns=header))

    if not frames:
        raise ValueError(f"No tables found in PDF: {path}")
    return pd.concat(frames, ignore_index=True)


def _find_col(columns: list, candidates: list[str]) -> Optional[str]:
    cols_lower = {c.lower().strip(): c for c in columns if isinstance(c, str)}
    for cand in candidates:
        if cand in cols_lower:
            return cols_lower[cand]
    for col_lower, col in cols_lower.items():
        if any(cand in col_lower for cand in candidates):
            return col
    return None


def _rows_to_line_items(df: pd.DataFrame) -> list[InvoiceLineItem]:
    columns = list(df.columns)
    upc_col = _find_col(columns, _UPC_COLS)
    desc_col = _find_col(columns, _DESC_COLS)
    cost_col = _find_col(columns, _COST_COLS)
    qty_col = _find_col(columns, _QTY_COLS)
    sku_col = _find_col(columns, _SKU_COLS)

    if not upc_col or not cost_col:
        raise ValueError(f"Could not find UPC and cost columns. Found columns: {columns}")

    items = []
    for _, row in df.iterrows():
        upc = _clean_upc(row.get(upc_col, ""))
        if not upc:
            continue
        cost = _to_float(row.get(cost_col, 0))
        qty = int(_to_float(row.get(qty_col, 1))) if qty_col else 1
        items.append(InvoiceLineItem(
            upc=upc,
            description=str(row.get(desc_col, "") or "").strip() if desc_col else "",
            cost_per_unit=cost,
            quantity=max(qty, 1),
            supplier_sku=str(row.get(sku_col, "") or "").strip() if sku_col else "",
        ))

    log.info("Parsed %d line items from invoice", len(items))
    return items


def _clean_upc(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) >= 8 else ""


def _to_float(value) -> float:
    s = re.sub(r"[^\d.\-]", "", str(value or ""))
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0
