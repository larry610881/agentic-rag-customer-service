"""Download Kaggle Olist Brazilian E-Commerce dataset.

Tries kaggle CLI first; prints manual instructions on failure.
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"

DATASET = "olistbr/brazilian-ecommerce"
ZIP_NAME = "brazilian-ecommerce.zip"

EXPECTED_FILES = [
    "olist_customers_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "product_category_name_translation.csv",
]


def _all_csvs_exist() -> bool:
    return all((RAW_DIR / f).exists() for f in EXPECTED_FILES)


def _print_manual_instructions() -> None:
    print(
        "\n"
        "═══════════════════════════════════════════════════════\n"
        "  Kaggle CLI not available or download failed.\n"
        "  Please download manually:\n"
        "\n"
        "  1. Go to https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce\n"
        "  2. Click 'Download' (login required)\n"
        "  3. Unzip the CSV files into:\n"
        f"     {RAW_DIR}/\n"
        "\n"
        "  Expected files:\n"
    )
    for f in EXPECTED_FILES:
        print(f"     - {f}")
    print("═══════════════════════════════════════════════════════\n")


def main() -> None:
    if _all_csvs_exist():
        print(f"All {len(EXPECTED_FILES)} CSV files already exist in {RAW_DIR}. Skipping download.")
        return

    if not shutil.which("kaggle"):
        print("ERROR: 'kaggle' CLI not found.")
        _print_manual_instructions()
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / ZIP_NAME

    print(f"Downloading {DATASET} via kaggle CLI...")
    try:
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", DATASET, "-p", str(RAW_DIR)],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR: kaggle download failed (exit code {e.returncode}).")
        _print_manual_instructions()
        sys.exit(1)

    if zip_path.exists():
        print(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(RAW_DIR)
        zip_path.unlink()
        print("Zip removed.")

    if _all_csvs_exist():
        print(f"Download complete. {len(EXPECTED_FILES)} CSV files in {RAW_DIR}.")
    else:
        missing = [f for f in EXPECTED_FILES if not (RAW_DIR / f).exists()]
        print(f"WARNING: Missing files after download: {missing}")
        sys.exit(1)


if __name__ == "__main__":
    main()
