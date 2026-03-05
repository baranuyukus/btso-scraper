"""
PyInstaller Build Script
--------------------------
All-in-one executable build. Model ve gerekli dosyaları paketler.
"""

import PyInstaller.__main__
import os
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEPARATOR = ";" if sys.platform == "win32" else ":"


def build():
    # Model dosyası varsa ekle
    model_path = os.path.join(BASE_DIR, "dataset", "model", "captcha_knn.pkl")
    labels_path = os.path.join(BASE_DIR, "dataset", "labels.csv")

    add_data = []

    if os.path.exists(model_path):
        add_data.append(f"--add-data={model_path}{SEPARATOR}dataset/model")

    if os.path.exists(labels_path):
        add_data.append(f"--add-data={labels_path}{SEPARATOR}dataset")

    # Dataset images klasörü (boş da olsa oluşsun)
    os.makedirs(os.path.join(BASE_DIR, "dataset", "images"), exist_ok=True)

    args = [
        os.path.join(BASE_DIR, "gui.py"),
        "--name=BTSO-Scraper",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        # Hidden imports
        "--hidden-import=sklearn.neighbors",
        "--hidden-import=sklearn.svm",
        "--hidden-import=sklearn.ensemble",
        "--hidden-import=sklearn.preprocessing",
        "--hidden-import=sklearn.pipeline",
        "--hidden-import=sklearn.model_selection",
        "--hidden-import=sklearn.metrics",
        "--hidden-import=sklearn.utils",
        "--hidden-import=scipy.ndimage",
        "--hidden-import=PIL",
        "--hidden-import=bs4",
        "--hidden-import=lxml",
        "--hidden-import=lxml.etree",
        # Collect all sklearn
        "--collect-submodules=sklearn",
        # Ana modüller
        "--hidden-import=database",
        "--hidden-import=scraper",
        "--hidden-import=scraper_worker",
        "--hidden-import=captcha_model",
        "--hidden-import=captcha_solver",
    ] + add_data

    print("=" * 60)
    print("  BTSO Scraper Build")
    print("=" * 60)
    print(f"  Platform: {sys.platform}")
    print(f"  Python: {sys.version}")
    print(f"  Model: {'var' if os.path.exists(model_path) else 'yok'}")
    print("=" * 60)

    PyInstaller.__main__.run(args)

    print("\n" + "=" * 60)
    print("  Build tamamlandi!")
    print(f"  Cikti: dist/BTSO-Scraper{'.exe' if sys.platform == 'win32' else ''}")
    print("=" * 60)


if __name__ == "__main__":
    build()
