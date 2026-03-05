"""
BTSO CAPTCHA Gelişmiş Model
-----------------------------
Çoklu sınıflandırıcı karşılaştırma (KNN, SVM, RandomForest)
ile en yüksek doğruluklu modeli seçer.

Gelişmiş özellikler:
- HOG benzeri gradient histogram
- Çok ölçekli grid (3x3, 4x4, 5x5)
- Kontur ve kenar yoğunluğu
- Zonal özellikler
"""

import os
import csv
import pickle
import numpy as np
from PIL import Image, ImageFilter
from collections import defaultdict
from scipy import ndimage
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import json


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
LABELS_FILE = os.path.join(DATASET_DIR, "labels.csv")
MODEL_DIR = os.path.join(DATASET_DIR, "model")
MODEL_FILE = os.path.join(MODEL_DIR, "captcha_knn.pkl")
STATS_FILE = os.path.join(MODEL_DIR, "training_stats.json")

DIGIT_H = 28
DIGIT_W = 16


def load_labels():
    labels = {}
    if os.path.exists(LABELS_FILE):
        with open(LABELS_FILE, "r") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2 and row[1].strip() and len(row[1].strip()) == 6:
                    labels[row[0]] = row[1].strip()
    return labels


def img_to_binary(img):
    arr = np.array(img.convert("L"))
    return (arr < 128).astype(np.uint8)


def clean_noise_advanced(binary, min_size=3):
    """Connected component + komşuluk analizi ile gürültü temizleme"""
    labeled, num_features = ndimage.label(binary)
    cleaned = np.zeros_like(binary)

    for i in range(1, num_features + 1):
        component_mask = (labeled == i)
        size = np.sum(component_mask)
        if size >= min_size:
            # Bileşenin boyutlarını kontrol et (çok dar/uzun çizgileri kaldır)
            coords = np.argwhere(component_mask)
            h = coords[:, 0].max() - coords[:, 0].min() + 1
            w = coords[:, 1].max() - coords[:, 1].min() + 1
            aspect = max(h, w) / (min(h, w) + 1)
            # Çok ince çizgi değilse ve yeterince büyükse
            if size >= min_size and (aspect < 10 or size > 15):
                cleaned[component_mask] = 1

    # İzole pikselleri kaldır
    h, w = cleaned.shape
    result = cleaned.copy()
    for y in range(h):
        for x in range(w):
            if cleaned[y, x] == 1:
                y_min, y_max = max(0, y - 1), min(h, y + 2)
                x_min, x_max = max(0, x - 1), min(w, x + 2)
                if np.sum(cleaned[y_min:y_max, x_min:x_max]) <= 2:
                    result[y, x] = 0

    return result


def segment_digits(binary, num_digits=6):
    """Gelişmiş digit segmentasyonu: profil analizi"""
    h, w = binary.shape

    # Dikey profil
    v_profile = np.sum(binary, axis=0)

    # Sabit genişlik bölme (ana yöntem)
    digit_width = w / num_digits
    digits = []

    for i in range(num_digits):
        x_start = int(round(i * digit_width))
        x_end = int(round((i + 1) * digit_width))

        # Sınırları biraz ayarla: boşluk noktalarını bul
        margin = int(digit_width * 0.15)
        best_start = x_start
        best_end = x_end

        if i > 0:
            search_start = max(0, x_start - margin)
            search_end = min(w, x_start + margin)
            if search_end > search_start:
                segment = v_profile[search_start:search_end]
                best_idx = np.argmin(segment) + search_start
                best_start = best_idx

        if i < num_digits - 1:
            search_start = max(0, x_end - margin)
            search_end = min(w, x_end + margin)
            if search_end > search_start:
                segment = v_profile[search_start:search_end]
                best_idx = np.argmin(segment) + search_start
                best_end = best_idx

        digit = binary[:, best_start:best_end].copy()
        if digit.shape[1] > 0:
            digits.append(digit)

    # Eksik digit varsa sabit bölme
    if len(digits) != 6:
        digits = []
        for i in range(num_digits):
            x_start = int(round(i * digit_width))
            x_end = int(round((i + 1) * digit_width))
            digits.append(binary[:, x_start:x_end].copy())

    return digits


def normalize_digit(digit_arr):
    h, w = digit_arr.shape
    rows = np.any(digit_arr, axis=1)
    cols = np.any(digit_arr, axis=0)

    if not rows.any() or not cols.any():
        return np.zeros((DIGIT_H, DIGIT_W), dtype=np.float32)

    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    cropped = digit_arr[y_min:y_max + 1, x_min:x_max + 1]
    img = Image.fromarray((cropped * 255).astype(np.uint8))
    img = img.resize((DIGIT_W, DIGIT_H), Image.LANCZOS)
    return np.array(img).astype(np.float32) / 255.0


def compute_gradient_features(norm):
    """HOG benzeri gradient özellik"""
    # Basit sobel gradientleri
    gy = np.diff(norm, axis=0, prepend=0)
    gx = np.diff(norm, axis=1, prepend=0)

    magnitude = np.sqrt(gx ** 2 + gy ** 2)
    angle = np.arctan2(gy, gx + 1e-10)

    # 4 yönlü histogram (4x4 hücre)
    n_bins = 8
    n_cells_y, n_cells_x = 4, 4
    cell_h = DIGIT_H // n_cells_y
    cell_w = DIGIT_W // n_cells_x
    bins = np.linspace(-np.pi, np.pi, n_bins + 1)

    features = []
    for cy in range(n_cells_y):
        for cx in range(n_cells_x):
            cell_mag = magnitude[cy * cell_h:(cy + 1) * cell_h, cx * cell_w:(cx + 1) * cell_w]
            cell_ang = angle[cy * cell_h:(cy + 1) * cell_h, cx * cell_w:(cx + 1) * cell_w]
            hist, _ = np.histogram(cell_ang, bins=bins, weights=cell_mag)
            features.extend(hist)

    return np.array(features)


def extract_features(digit_arr):
    """Gelişmiş çoklu özellik vektörü"""
    norm = normalize_digit(digit_arr)

    # 1. Düz piksel (downsampled)
    small = Image.fromarray((norm * 255).astype(np.uint8)).resize((10, 14), Image.LANCZOS)
    flat = np.array(small).astype(np.float32).flatten() / 255.0

    # 2. Yatay/dikey projeksiyonlar
    h_proj = np.mean(norm, axis=1)
    v_proj = np.mean(norm, axis=0)

    # 3. Multi-scale grid (3x3)
    grid3 = []
    for gy in range(3):
        for gx in range(3):
            r = norm[gy * (DIGIT_H // 3):(gy + 1) * (DIGIT_H // 3),
                      gx * (DIGIT_W // 3):(gx + 1) * (DIGIT_W // 3)]
            grid3.append(np.mean(r))

    # 4. Grid 4x4
    grid4 = []
    for gy in range(4):
        for gx in range(4):
            r = norm[gy * (DIGIT_H // 4):(gy + 1) * (DIGIT_H // 4),
                      gx * (DIGIT_W // 4):(gx + 1) * (DIGIT_W // 4)]
            grid4.append(np.mean(r))

    # 5. HOG benzeri gradient
    gradient = compute_gradient_features(norm)

    # 6. Profil özellikler
    center_h = norm[DIGIT_H // 4:3 * DIGIT_H // 4, :]
    center_v = norm[:, DIGIT_W // 4:3 * DIGIT_W // 4]
    profile = np.array([
        np.mean(center_h),
        np.mean(center_v),
        np.mean(norm[:DIGIT_H // 2, :]),  # üst yarı
        np.mean(norm[DIGIT_H // 2:, :]),  # alt yarı
        np.mean(norm[:, :DIGIT_W // 2]),  # sol yarı
        np.mean(norm[:, DIGIT_W // 2:]),  # sağ yarı
        np.mean(norm),                     # toplam yoğunluk
        np.std(norm),                      # standart sapma
    ])

    # 7. Geçiş sayıları (yatay/dikey)
    transitions_h = []
    for row in (norm > 0.5).astype(int):
        transitions_h.append(np.sum(np.abs(np.diff(row))))
    transitions_v = []
    for col in (norm > 0.5).astype(int).T:
        transitions_v.append(np.sum(np.abs(np.diff(col))))

    trans_h_mean = np.mean(transitions_h)
    trans_v_mean = np.mean(transitions_v)
    trans = np.array([trans_h_mean, trans_v_mean])

    features = np.concatenate([
        flat,                    # 140
        h_proj,                  # 28
        v_proj,                  # 16
        np.array(grid3),         # 9
        np.array(grid4),         # 16
        gradient,                # 128
        profile,                 # 8
        trans,                   # 2
    ])
    return features


def prepare_dataset(labels):
    X, y = [], []
    skipped = 0
    for fname, label in labels.items():
        fpath = os.path.join(IMAGES_DIR, fname)
        if not os.path.exists(fpath):
            skipped += 1
            continue
        img = Image.open(fpath)
        binary = img_to_binary(img)
        cleaned = clean_noise_advanced(binary, min_size=3)
        digits = segment_digits(cleaned, num_digits=6)
        for i, digit_arr in enumerate(digits):
            features = extract_features(digit_arr)
            X.append(features)
            y.append(int(label[i]))
    X, y = np.array(X), np.array(y)
    if skipped:
        print(f"  ⚠ {skipped} dosya bulunamadı")
    return X, y


def train_and_evaluate():
    os.makedirs(MODEL_DIR, exist_ok=True)

    print("=" * 60)
    print("  BTSO CAPTCHA Gelişmiş Model Eğitimi")
    print("=" * 60)

    labels = load_labels()
    print(f"\n📊 Dataset: {len(labels)} CAPTCHA, {len(labels) * 6} digit")

    X, y = prepare_dataset(labels)
    print(f"📊 Özellik boyutu: {X.shape[1]}")
    print(f"📊 Digit dağılımı:")
    for d in range(10):
        count = np.sum(y == d)
        bar = '█' * max(1, count // 4)
        print(f"   {d}: {bar} {count}")

    # =====================================
    # Çoklu Model Karşılaştırma
    # =====================================
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    models = {
        "KNN(K=5)": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", KNeighborsClassifier(n_neighbors=5, weights="distance"))
        ]),
        "KNN(K=7)": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", KNeighborsClassifier(n_neighbors=7, weights="distance"))
        ]),
        "SVM(rbf)": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", SVC(kernel="rbf", C=10, gamma="scale"))
        ]),
        "SVM(C=50)": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", SVC(kernel="rbf", C=50, gamma="scale"))
        ]),
        "RandomForest": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=200, max_depth=None, random_state=42, n_jobs=1))
        ]),
    }

    print(f"\n{'─'*60}")
    print("Model Karşılaştırma (5-Fold Cross-Validation)")
    print("─" * 60)

    best_name = None
    best_score = 0
    results = {}

    for name, model in models.items():
        scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy", n_jobs=1)
        mean = scores.mean()
        std = scores.std()
        bar = "█" * int(mean * 40)
        print(f"  {name:20s}: {mean:.3f} (±{std:.3f}) {bar}")
        results[name] = mean
        if mean > best_score:
            best_score = mean
            best_name = name

    print(f"\n  🏆 En iyi: {best_name} ({best_score:.3f})")

    # =====================================
    # Final model: en iyi model ile eğit
    # =====================================
    print(f"\n{'─'*60}")
    print(f"Final Model: {best_name}")
    print("─" * 60)

    best_model = models[best_name]
    best_model.fit(X, y)

    y_pred = best_model.predict(X)
    train_acc = np.mean(y_pred == y) * 100
    print(f"  Digit doğruluk (train): {train_acc:.1f}%")

    # CAPTCHA bazlı doğruluk
    print(f"\n{'─'*60}")
    print("CAPTCHA Bazlı Doğrulama")
    print("─" * 60)

    correct_captchas = 0
    total_captchas = 0
    correct_digits = 0
    total_digits = 0
    errors = []

    for fname, label in labels.items():
        fpath = os.path.join(IMAGES_DIR, fname)
        if not os.path.exists(fpath):
            continue
        img = Image.open(fpath)
        prediction = predict_captcha(img, best_model)
        match = prediction == label
        correct_captchas += int(match)
        total_captchas += 1
        for p, g in zip(prediction, label):
            correct_digits += int(p == g)
            total_digits += 1
        if not match:
            diff = ""
            for p, g in zip(prediction, label):
                diff += g if p == g else f"[{g}→{p}]"
            errors.append(f"  ✗ {fname}: {diff}")

    # Sadece ilk 10 hata göster
    for e in errors[:10]:
        print(e)
    if len(errors) > 10:
        print(f"  ... ve {len(errors) - 10} hata daha")

    captcha_acc = correct_captchas / total_captchas * 100
    digit_acc = correct_digits / total_digits * 100
    print(f"\n  📈 Digit doğruluk:   {correct_digits}/{total_digits} ({digit_acc:.1f}%)")
    print(f"  📈 CAPTCHA doğruluk: {correct_captchas}/{total_captchas} ({captcha_acc:.1f}%)")
    print(f"  📈 CV doğruluk:      {best_score:.1%}")

    # Model kaydet
    model_data = {
        "classifier": best_model,
        "model_name": best_name,
        "best_k": 5,
        "feature_dim": X.shape[1],
        "digit_h": DIGIT_H,
        "digit_w": DIGIT_W,
        "train_samples": len(X),
        "captcha_accuracy": captcha_acc,
        "digit_accuracy": digit_acc,
        "cv_accuracy": best_score * 100,
    }
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(model_data, f)

    stats = {
        "model_name": best_name,
        "total_captchas": total_captchas,
        "total_digits": total_digits,
        "cv_accuracy": float(best_score),
        "train_digit_accuracy": float(digit_acc),
        "train_captcha_accuracy": float(captcha_acc),
        "all_results": {k: float(v) for k, v in results.items()},
    }
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n  ✓ Model kaydedildi: {MODEL_FILE}")
    return model_data


def predict_captcha(img, model_or_data):
    if isinstance(model_or_data, dict):
        classifier = model_or_data["classifier"]
    else:
        classifier = model_or_data

    binary = img_to_binary(img)
    cleaned = clean_noise_advanced(binary, min_size=3)
    digits = segment_digits(cleaned, num_digits=6)

    result = ""
    for digit_arr in digits:
        features = extract_features(digit_arr).reshape(1, -1)
        pred = classifier.predict(features)[0]
        result += str(pred)

    return result


def load_model():
    if not os.path.exists(MODEL_FILE):
        raise FileNotFoundError(f"Model bulunamadı: {MODEL_FILE}")
    with open(MODEL_FILE, "rb") as f:
        return pickle.load(f)


if __name__ == "__main__":
    train_and_evaluate()
