# Kaggle Olist Dataset

## Download Instructions

1. Install Kaggle CLI: `pip install kaggle`
2. Configure API key: `~/.kaggle/kaggle.json`
3. Download:

```bash
kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw/
unzip data/raw/brazilian-ecommerce.zip -d data/raw/
```

## Expected Files

- `olist_customers_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_products_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `product_category_name_translation.csv`

## Mock Data Fallback

If CSV files are not present, `make seed-data` will insert mock development data automatically.
