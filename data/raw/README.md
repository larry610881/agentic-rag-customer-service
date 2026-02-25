# Kaggle Olist Dataset

## Quick Start

```bash
make seed-status       # Check current data state
make seed-kaggle       # Download Kaggle CSV + import (~100k rows, <15s)
make seed-mock         # Force mock data (3 orders)
make seed-reset        # Clear Olist tables only (preserve App data)
make seed-reset-all    # Clear everything (Olist + App)
```

## Manual Download (if Kaggle CLI unavailable)

1. Go to <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>
2. Click **Download** (Kaggle login required)
3. Unzip CSV files into this directory (`data/raw/`)
4. Run: `make seed-data` (auto-detects CSV and imports)

## Kaggle CLI Setup (optional)

```bash
pip install kaggle
# Place API key at ~/.kaggle/kaggle.json
# Then:
make seed-kaggle
```

## Expected CSV Files

- `olist_customers_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_products_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `product_category_name_translation.csv`

## Modes

| Mode | Command | Description |
|------|---------|-------------|
| Auto | `make seed-data` | CSV if present, else mock |
| Mock | `make seed-mock` | 3 demo customers/orders/products |
| Kaggle | `make seed-kaggle` | Download + import ~100k rows |

## Notes

- CSV files are `.gitignore`-d (not committed to repo)
- Demo orders `ord-001` ~ `ord-003` are always inserted for E2E tests
- Use `make seed-reset` before re-importing to avoid "already has data" skips
