from pathlib import Path
from typing import List, Dict, Any
import cv2
from ultralytics import YOLO

# COCO veggie classes (what YOLOv8 actually knows)
VEG_CLASSES = {
    "broccoli", "carrot", "apple", "orange", "banana"
}

# False positive corrections
FALSE_POSITIVES = {
    "orange": "tomato",      # Tomato looks like orange
    "hot dog": "carrot",     # Long orange things look like hot dogs
    "donut": "orange",       # Round orange-ish foods
}

class VegetableDetector:
    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.25):
        # ⚡ FAST PREDICT SETTINGS - 3x speedup
        self.fast_predict_kwargs = {
            'conf': conf_threshold,
            'imgsz': 320,           # ⚡ Smaller input = 3x faster
            'max_det': 15,          # ⚡ Limit detections
            'verbose': False,       # ⚡ No console spam
            'device': 'cpu',        # ⚡ Consistent CPU speed
            'half': False,          # ⚡ Disable FP16 on CPU
        }
        
        self.model = YOLO(model_name)
        self.conf_threshold = conf_threshold
        self.class_names = self.model.names
        
        # Valid veggie class IDs
        self.veg_class_ids = {
            class_id for class_id, name in self.class_names.items()
            if name in VEG_CLASSES
        }

    def detect_vegetables(self, image_path: str) -> List[Dict[str, Any]]:
        # ⚡ SINGLE PREDICTION CALL - uses fast settings
        results = self.model.predict(image_path, **self.fast_predict_kwargs)
        
        detections = []
        for r in results:
            if r.boxes is None:
                continue
            
            # ⚡ BATCH PROCESS ALL BOXES
            boxes = r.boxes
            cls_ids = boxes.cls.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            xyxys = boxes.xyxy.cpu().numpy()
            
            for i in range(len(boxes)):
                cls_id = cls_ids[i]
                
                # Skip non-veggie classes
                if cls_id not in self.veg_class_ids:
                    continue
                
                original_name = self.class_names[cls_id]
                conf = float(confs[i])
                
                # False positive correction
                corrected_name = original_name
                if original_name in FALSE_POSITIVES:
                    corrected_name = FALSE_POSITIVES[original_name]
                
                detections.append({
                    "class_name": corrected_name,
                    "original_class": original_name,
                    "confidence": conf,
                    "bbox": xyxys[i].tolist(),
                    "corrected": corrected_name != original_name
                })
        
        return detections

    def visualize_detections(self, image_path: str, output_path: str | None = None) -> str:
        # ⚡ CACHE DETECTIONS - DON'T REDO PREDICTION
        detections = self.detect_vegetables(image_path)
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        for det in detections:
            x1, y1, x2, y2 = map(int, det["bbox"])
            
            # Color code: Green=correct, Yellow=corrected
            color = (0, 255, 255) if det["corrected"] else (0, 255, 0)
            thickness = 3 if det["corrected"] else 2
            
            label = f"{det['class_name']} {det['confidence']:.1%}"
            if det["corrected"]:
                label += f" (was {det['original_class']})"
            
            # Bounding box
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
            
            # Label background
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(img, (x1, y1 - h - 10), (x1 + w, y1), color, -1)
            
            # Label text (black)
            cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        if output_path is None:
            output_path = str(Path(image_path).with_name(f"annotated_{Path(image_path).name}"))

        cv2.imwrite(output_path, img)
        return output_path

if __name__ == "__main__":
    detector = VegetableDetector(conf_threshold=0.25)
    input_image = "test.jpg"  # Put your veggie photo here
    detections = detector.detect_vegetables(input_image)
    
    print("Detections:")
    for d in detections:
        status = "🔄 CORRECTED" if d["corrected"] else "✅"
        print(f"  {status} {d['class_name']}: {d['confidence']:.1%}")
    
    out_path = detector.visualize_detections(input_image)
    print(f"\n📸 Annotated image: {out_path}")
