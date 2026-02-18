"""
Food Image Classifier for UGA Nutrition App
Uses a YOLOv8 classifier trained on UGA dining hall food pictures
to identify food items and their portion sizes.
"""

import os
from typing import Dict, Optional

from ultralytics import YOLO

# Nutrition data per 1 cup serving (values from USDA)
FOOD_NUTRITION = {
    "baked potato":      {"calories": 161, "protein": 4.3, "carbs": 36.6, "fat": 0.2, "fiber": 3.8, "food_group": "Grains & Starches"},
    "black beans":       {"calories": 227, "protein": 15.2, "carbs": 40.8, "fat": 0.9, "fiber": 15.0, "food_group": "Protein"},
    "broccoli":          {"calories": 55,  "protein": 3.7, "carbs": 11.2, "fat": 0.6, "fiber": 5.1, "food_group": "Vegetables"},
    "cherry tomato":     {"calories": 27,  "protein": 1.3, "carbs": 5.8,  "fat": 0.3, "fiber": 1.8, "food_group": "Vegetables"},
    "chickpea":          {"calories": 269, "protein": 14.5, "carbs": 45.0, "fat": 4.2, "fiber": 12.5, "food_group": "Protein"},
    "cucumber":          {"calories": 16,  "protein": 0.7, "carbs": 3.1,  "fat": 0.2, "fiber": 0.5, "food_group": "Vegetables"},
    "grapefruit":        {"calories": 74,  "protein": 1.5, "carbs": 18.6, "fat": 0.2, "fiber": 2.5, "food_group": "Fruits"},
    "grapes":            {"calories": 104, "protein": 1.1, "carbs": 27.3, "fat": 0.2, "fiber": 1.4, "food_group": "Fruits"},
    "hash browns":       {"calories": 326, "protein": 3.2, "carbs": 35.1, "fat": 20.0, "fiber": 3.2, "food_group": "Grains & Starches"},
    "lettuce":           {"calories": 5,   "protein": 0.5, "carbs": 1.0,  "fat": 0.1, "fiber": 0.5, "food_group": "Vegetables"},
    "mixed plate":       {"calories": 250, "protein": 12.0, "carbs": 30.0, "fat": 8.0, "fiber": 4.0, "food_group": "Mixed"},
    "peach slices":      {"calories": 60,  "protein": 1.4, "carbs": 14.7, "fat": 0.4, "fiber": 2.3, "food_group": "Fruits"},
    "pineapple chunks":  {"calories": 82,  "protein": 0.9, "carbs": 21.6, "fat": 0.2, "fiber": 2.3, "food_group": "Fruits"},
    "red bell peppers":  {"calories": 46,  "protein": 1.5, "carbs": 9.0,  "fat": 0.5, "fiber": 3.1, "food_group": "Vegetables"},
    "sweet potato":      {"calories": 180, "protein": 4.0, "carbs": 41.4, "fat": 0.3, "fiber": 6.6, "food_group": "Grains & Starches"},
}


def _parse_class_name(class_name: str):
    """Parse a trained model class name like 'black_beans_half_cup' into (food_name, portion_cups)."""
    if class_name.endswith("_half_cup"):
        food = class_name[:-len("_half_cup")]
        portion = 0.5
    elif class_name.endswith("_1_cup"):
        food = class_name[:-len("_1_cup")]
        portion = 1.0
    else:
        food = class_name
        portion = 1.0
    return food.replace("_", " "), portion


class FoodClassifier:
    """YOLOv8-based food classifier trained on UGA dining hall food pictures."""

    def __init__(self, model_path: str = None):
        if model_path is None:
            base = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base, "food_classifier.pt")

        self.model = YOLO(model_path)
        self.class_names = self.model.names

    def predict(self, image_path: str) -> Optional[Dict]:
        """
        Classify a food image. Returns dict with food_name, portion, confidence,
        and full nutrition breakdown, or None if confidence is too low.
        """
        results = self.model.predict(
            image_path,
            imgsz=224,
            verbose=False,
            device="cpu",
        )

        if not results or results[0].probs is None:
            return None

        probs = results[0].probs
        top1_idx = int(probs.top1)
        top1_conf = float(probs.top1conf)

        if top1_conf < 0.15:
            return None

        class_name = self.class_names[top1_idx]
        food_name, portion_cups = _parse_class_name(class_name)

        # Look up base nutrition (per 1 cup), scale by detected portion
        base = FOOD_NUTRITION.get(food_name, {
            "calories": 80, "protein": 3, "carbs": 15, "fat": 2, "fiber": 2,
            "food_group": "Other",
        })

        portion_label = "0.5 cup" if portion_cups == 0.5 else "1 cup"

        return {
            "food_name": food_name.title(),
            "portion_cups": portion_cups,
            "portion_label": portion_label,
            "confidence": round(top1_conf, 2),
            "calories": round(base["calories"] * portion_cups),
            "protein": round(base["protein"] * portion_cups, 1),
            "carbs": round(base["carbs"] * portion_cups, 1),
            "fat": round(base["fat"] * portion_cups, 1),
            "fiber": round(base["fiber"] * portion_cups, 1),
            "food_group": base["food_group"],
        }

    @property
    def food_count(self) -> int:
        return len({_parse_class_name(n)[0] for n in self.class_names.values()})


if __name__ == "__main__":
    classifier = FoodClassifier()
    print(f"Model loaded with {len(classifier.class_names)} classes ({classifier.food_count} foods)")
    for idx, name in sorted(classifier.class_names.items()):
        food, portion = _parse_class_name(name)
        print(f"  [{idx}] {food.title()} - {portion} cup")
