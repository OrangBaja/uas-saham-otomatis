import os
import csv
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# === KONFIGURASI ===
DATASETS_DIR = "./datasets"
LOG_FILE = "compiler_activity.log"
MAX_WORKERS = 8  # Sesuaikan dengan core CPU

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class StockCompiler:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        # Urutan kolom yang diinginkan di CSV akhir
        self.fieldnames = ['date', 'kode', 'nama', 'open', 'high', 'low', 'close', 'volume']

    def process_stock_folder(self, folder_name):
        """
        Membaca semua JSON dalam satu folder saham dan menyatukannya jadi satu CSV.
        """
        stock_path = os.path.join(self.root_dir, folder_name)
        json_dir = os.path.join(stock_path, "json")
        csv_output = os.path.join(stock_path, f"{folder_name}.csv")

        # Cek apakah folder json ada
        if not os.path.isdir(json_dir):
            return f"[{folder_name}] Skip: Folder json tidak ditemukan."

        all_records = []
        files = sorted(os.listdir(json_dir)) # Sort agar tanggal berurutan

        # Loop semua file JSON
        for filename in files:
            if not filename.endswith(".json"):
                continue
            
            filepath = os.path.join(json_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Normalisasi data agar sesuai kolom (mapping)
                    record = {
                        'date': data.get('date', ''),
                        'kode': data.get('kode', ''),
                        'nama': data.get('nama', ''),
                        'open': data.get('open', ''),
                        'high': data.get('high', ''),
                        'low': data.get('low', ''),
                        'close': data.get('close', ''),
                        'volume': data.get('volume', '')
                    }
                    all_records.append(record)
            except Exception as e:
                logging.warning(f"[{folder_name}] Gagal baca {filename}: {e}")

        # Tulis ke CSV Master jika ada data
        if all_records:
            try:
                with open(csv_output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                    writer.writeheader() # Tulis baris judul (Header)
                    writer.writerows(all_records) # Tulis semua data
                
                return f"[{folder_name}] Sukses! {len(all_records)} baris data dikompilasi ke CSV."
            except Exception as e:
                return f"[{folder_name}] Gagal menulis CSV: {e}"
        else:
            return f"[{folder_name}] Skip: Tidak ada data valid ditemukan."

    def run(self):
        """Menjalankan proses kompilasi secara paralel"""
        if not os.path.exists(self.root_dir):
            logging.critical(f"Folder dataset tidak ditemukan: {self.root_dir}")
            return

        # Ambil daftar folder saham (contoh: BBCA, BBRI)
        # Filter hanya yang direktori, bukan file
        stock_folders = [
            d for d in os.listdir(self.root_dir) 
            if os.path.isdir(os.path.join(self.root_dir, d))
        ]

        logging.info(f"Memulai kompilasi untuk {len(stock_folders)} saham...")

        # Eksekusi Paralel (Multithreading)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self.process_stock_folder, folder): folder for folder in stock_folders}
            
            for future in as_completed(futures):
                result = future.result()
                # Log hasilnya
                logging.info(result)

if __name__ == "__main__":
    compiler = StockCompiler(DATASETS_DIR)
    compiler.run()