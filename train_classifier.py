"""
Train a YOLOv8 classifier on the UGA dining hall food pictures.
Organizes images into class folders, applies data augmentation, and fine-tunes.

Usage: python train_classifier.py
"""

import os
import re
import shutil
import random
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "AI Dining Hall Project - Food Pictures")
DATASET_DIR = os.path.join(BASE_DIR, "food_dataset")

# ── Parse filename into (food_name, portion_cups) ──────────────────────
def parse_filename(filename):
    stem = Path(filename).stem
    # Detect portion
    if re.search(r"0\.5\s*[Cc]up", stem):
        portion = "half_cup"
    elif re.search(r"1\s*[Cc]up", stem):
        portion = "1_cup"
    else:
        portion = "1_cup"  # default for items like "Baked Potato Top View"

    # Extract food name (everything before digits / Top View / Grouped / # / comma)
    food = re.split(r"\d|Top View|Grouped|#|,", stem, flags=re.IGNORECASE)[0]
    food = food.strip().lower().replace(" ", "_")
    return food, portion


# ── Data augmentation: generate extra images from a single source ──────
def augment_image(img, count=8):
    """Generate augmented copies: flips, rotations, brightness, crops."""
    h, w = img.shape[:2]
    augmented = []
    for i in range(count):
        aug = img.copy()

        # Random horizontal flip
        if random.random() > 0.5:
            aug = cv2.flip(aug, 1)

        # Random rotation (-15 to +15 degrees)
        angle = random.uniform(-15, 15)
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        aug = cv2.warpAffine(aug, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        # Random brightness adjustment
        factor = random.uniform(0.7, 1.3)
        aug = np.clip(aug * factor, 0, 255).astype(np.uint8)

        # Random center crop (80-100% of image)
        crop_frac = random.uniform(0.8, 1.0)
        ch, cw = int(h * crop_frac), int(w * crop_frac)
        y_off = random.randint(0, h - ch)
        x_off = random.randint(0, w - cw)
        aug = aug[y_off:y_off + ch, x_off:x_off + cw]
        aug = cv2.resize(aug, (w, h))

        augmented.append(aug)
    return augmented


# ── Step 1: Organize into class folders with augmentation ─────────────
def build_dataset():
    # Clean previous dataset
    if os.path.exists(DATASET_DIR):
        shutil.rmtree(DATASET_DIR)

    # Collect all images by class
    class_images = {}  # class_name -> list of file paths
    for fname in os.listdir(PHOTOS_DIR):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        food, portion = parse_filename(fname)
        class_name = f"{food}_{portion}"
        class_images.setdefault(class_name, []).append(
            os.path.join(PHOTOS_DIR, fname)
        )

    print(f"Found {len(class_images)} classes:")
    for cls, imgs in sorted(class_images.items()):
        print(f"  {cls}: {len(imgs)} images")

    # Split and write train/val with augmentation
    for cls, img_paths in class_images.items():
        random.shuffle(img_paths)
        # Use at least 1 for val
        n_val = max(1, len(img_paths) // 4)
        val_paths = img_paths[:n_val]
        train_paths = img_paths[n_val:] if len(img_paths) > 1 else img_paths

        for split, paths in [("train", train_paths), ("val", val_paths)]:
            split_dir = os.path.join(DATASET_DIR, split, cls)
            os.makedirs(split_dir, exist_ok=True)

            for idx, fpath in enumerate(paths):
                # Copy original
                dst = os.path.join(split_dir, f"orig_{idx}.jpg")
                shutil.copy2(fpath, dst)

                # Generate augmented copies (more for train)
                img = cv2.imread(fpath)
                if img is None:
                    continue
                n_aug = 12 if split == "train" else 4
                for j, aug_img in enumerate(augment_image(img, count=n_aug)):
                    aug_dst = os.path.join(split_dir, f"aug_{idx}_{j}.jpg")
                    cv2.imwrite(aug_dst, aug_img)

    # Count totals
    total_train = sum(len(os.listdir(os.path.join(DATASET_DIR, "train", d)))
                      for d in os.listdir(os.path.join(DATASET_DIR, "train")))
    total_val = sum(len(os.listdir(os.path.join(DATASET_DIR, "val", d)))
                    for d in os.listdir(os.path.join(DATASET_DIR, "val")))
    print(f"\nDataset built: {total_train} train images, {total_val} val images")
    return class_images


# ── Step 2: Train YOLOv8 classifier ──────────────────────────────────
def train_model():
    model = YOLO("yolov8n-cls.pt")  # pretrained classification backbone

    results = model.train(
        data=DATASET_DIR,
        epochs=50,
        imgsz=224,
        batch=16,
        patience=10,        # early stopping
        optimizer="AdamW",
        lr0=0.001,
        weight_decay=0.01,
        augment=True,        # ultralytics built-in augmentation on top of ours
        verbose=True,
        project=os.path.join(BASE_DIR, "runs"),
        name="food_classifier",
        exist_ok=True,
    )

    # Copy best model to project root
    best_path = os.path.join(BASE_DIR, "runs", "food_classifier", "weights", "best.pt")
    dest_path = os.path.join(BASE_DIR, "food_classifier.pt")
    if os.path.exists(best_path):
        shutil.copy2(best_path, dest_path)
        print(f"\nTrained model saved to: {dest_path}")
    else:
        print("Warning: best.pt not found, check training output")

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("UGA Food Classifier Training")
    print("=" * 60)

    print("\n--- Building dataset with augmentation ---")
    build_dataset()

    print("\n--- Training YOLOv8 classifier ---")
    train_model()

    print("\nDone! The trained model is saved as 'food_classifier.pt'")
