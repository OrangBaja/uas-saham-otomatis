import os
import csv
import json
import time
import logging
import argparse
import requests
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# === KONFIGURASI ===
CSV_FILE = "./profile/daftar_saham.csv"
OUTPUT_DIR = "./datasets"
LOG_FILE = "scraper_activity.log"
MAX_WORKERS = 8  # Jumlah thread paralel
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Setup Logging (Agar terlihat profesional di console dan file)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class StockScraper:
    def __init__(self, csv_path, output_dir):
        self.csv_path = csv_path
        self.output_dir = output_dir
        # User-Agent agar tidak dianggap bot oleh Yahoo
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def _get_unix_timestamp(self, dt: datetime) -> int:
        return int(dt.timestamp())

    def fetch_yahoo_data(self, symbol: str, start: datetime, end: datetime):
        """Mengambil data mentah dari API Yahoo Finance"""
        params = {
            "interval": "1d",
            "events": "capitalGain|div|split",
            "formatted": "true",
            "includeAdjustedClose": "true",
            "period1": self._get_unix_timestamp(start),
            "period2": self._get_unix_timestamp(end),
            "lang": "en-US",
            "region": "US"
        }
        
        url = BASE_URL.format(symbol=symbol)
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        
        if response.status_code != 200:
            raise ConnectionError(f"Gagal mengambil data. Status: {response.status_code}")
        
        return response.json()

    def save_daily_json(self, data, kode, nama):
        """Memecah data chart menjadi file JSON harian"""
        chart_result = data.get("chart", {}).get("result", [])
        if not chart_result:
            raise ValueError("JSON kosong atau format berubah")

        res = chart_result[0]
        timestamps = res.get("timestamp", [])
        indicators = res.get("indicators", {}).get("quote", [{}])[0]

        # Buat folder khusus per saham: ./datasets/BBCA/json/
        outdir_json = os.path.join(self.output_dir, kode, "json")
        os.makedirs(outdir_json, exist_ok=True)

        saved_count = 0
        
        for i, ts in enumerate(timestamps):
            dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)
            
            # Skip Sabtu (5) dan Minggu (6)
            if dt_obj.weekday() >= 5:
                continue

            date_str = dt_obj.strftime("%Y-%m-%d")
            json_file_path = os.path.join(outdir_json, f"{date_str}.json")

            # INCREMENTAL CHECK: Jika file tanggal ini sudah ada, skip (Hemat waktu!)
            if os.path.exists(json_file_path):
                continue

            # Struktur data yang disimpan
            record = {
                "kode": kode,
                "nama": nama,
                "date": date_str,
                "open": indicators.get("open", [None])[i],
                "high": indicators.get("high", [None])[i],
                "low": indicators.get("low", [None])[i],
                "close": indicators.get("close", [None])[i],
                "volume": indicators.get("volume", [None])[i],
            }

            try:
                with open(json_file_path, "w", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False, indent=2)
                saved_count += 1
            except Exception as e:
                logging.error(f"Gagal menyimpan file {json_file_path}: {e}")

        return saved_count

    def process_symbol(self, row, fetch_all=False):
        """Logic untuk memproses satu saham (Worker Function)"""
        kode = row["Kode"].strip()
        nama = row["Nama Perusahaan"].strip()
        symbol = f"{kode}.JK"  # Tambahkan suffix .JK untuk pasar Indonesia

        try:
            end_date = datetime.now(timezone.utc)
            
            # Jika --all, ambil dari 2004. Jika tidak, cukup 7 hari terakhir (update rutin)
            if fetch_all:
                start_date = datetime(2004, 1, 1, tzinfo=timezone.utc)
            else:
                start_date = end_date - timedelta(days=7)

            logging.info(f"[{kode}] Memulai scraping...")
            raw_data = self.fetch_yahoo_data(symbol, start_date, end_date)
            saved_files = self.save_daily_json(raw_data, kode, nama)
            
            if saved_files > 0:
                return f"[{kode}] Sukses! {saved_files} data baru disimpan."
            else:
                return f"[{kode}] Sudah up-to-date."

        except Exception as e:
            error_msg = f"[{kode}] Error: {e}"
            logging.error(error_msg)
            return error_msg

    def run(self, fetch_all=False):
        """Menjalankan scraper dengan Multi-threading"""
        if not os.path.exists(self.csv_path):
            logging.critical(f"File CSV tidak ditemukan di: {self.csv_path}")
            return

        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            total_saham = len(reader)
            logging.info(f"Memuat {total_saham} saham dari CSV. Mode Full: {fetch_all}")

        # ThreadPoolExecutor untuk jalan paralel (Concurrency)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self.process_symbol, row, fetch_all): row for row in reader}
            
            for future in as_completed(futures):
                result = future.result()
                logging.info(result)

if __name__ == "__main__":
    # Setup argument parser untuk opsi command line
    parser = argparse.ArgumentParser(description="Program Scraper Saham Otomatis")
    parser.add_argument("--all", action="store_true", help="Ambil semua data historis (sejak 2004)")
    args = parser.parse_args()

    # Jalankan Scraper
    scraper = StockScraper(CSV_FILE, OUTPUT_DIR)
    scraper.run(fetch_all=args.all)