#!/usr/bin/env python
import torch
from ultralytics.nn.tasks import DetectionModel
from torch.nn.modules.container import Sequential

# 1) PyTorch’un “safe unpickler” listesine hem DetectionModel hem de Sequential’i ekleyelim
torch.serialization.add_safe_globals([DetectionModel, Sequential])

# 2) Sonra YOLO modelini yükleyelim
from ultralytics import YOLO

# Eğer load_yolo.py ile aynı klasördeyseniz sadece dosya adını kullanın:
model = YOLO("yolov8n.pt")
print("✅ YOLOv8n başarıyla yüklendi!")
