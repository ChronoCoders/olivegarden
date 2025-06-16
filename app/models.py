"""
Zeytin Detection System - Custom Model Training Pipeline
"""

import os
import yaml
import torch
import logging
from ultralytics import YOLO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from datetime import datetime
import json
import shutil

logger = logging.getLogger(__name__)

class ZeytinModelTrainer:
    """Custom YOLOv8 model trainer for olive detection"""
    
    def __init__(self, base_model_path: str = "yolov8n.pt"):
        self.base_model_path = base_model_path
        self.model = None
        self.training_config = {
            'epochs': 100,
            'imgsz': 640,
            'batch': 16,
            'lr0': 0.01,
            'lrf': 0.01,
            'momentum': 0.937,
            'weight_decay': 0.0005,
            'warmup_epochs': 3,
            'warmup_momentum': 0.8,
            'warmup_bias_lr': 0.1,
            'box': 0.05,
            'cls': 0.5,
            'dfl': 1.5,
            'pose': 12.0,
            'kobj': 1.0,
            'label_smoothing': 0.0,
            'nbs': 64,
            'overlap_mask': True,
            'mask_ratio': 4,
            'dropout': 0.0,
            'val': True,
            'save': True,
            'save_period': -1,
            'cache': False,
            'device': '',
            'workers': 8,
            'project': 'models/training',
            'name': 'olive_detection',
            'exist_ok': False,
            'pretrained': True,
            'optimizer': 'auto',
            'verbose': True,
            'seed': 0,
            'deterministic': True,
            'single_cls': False,
            'rect': False,
            'cos_lr': False,
            'close_mosaic': 10,
            'resume': False,
            'amp': True,
            'fraction': 1.0,
            'profile': False,
            'freeze': None,
            'multi_scale': False,
            'overlap_mask': True,
            'mask_ratio': 4,
            'dropout': 0.0,
        }
    
    def create_dataset_config(self, dataset_path: str, train_ratio: float = 0.8) -> str:
        """Create YOLO dataset configuration file"""
        try:
            config = {
                'path': dataset_path,
                'train': 'images/train',
                'val': 'images/val',
                'test': 'images/test',
                'nc': 2,  # number of classes
                'names': ['olive_tree', 'olive_fruit']
            }
            
            config_path = os.path.join(dataset_path, 'dataset.yaml')
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            logger.info(f"Dataset config created: {config_path}")
            return config_path
            
        except Exception as e:
            logger.error(f"Dataset config creation error: {e}")
            raise
    
    def prepare_dataset(self, images_dir: str, annotations_dir: str, output_dir: str) -> str:
        """Prepare dataset in YOLO format"""
        try:
            # Create directory structure
            dataset_dirs = [
                'images/train', 'images/val', 'images/test',
                'labels/train', 'labels/val', 'labels/test'
            ]
            
            for dir_name in dataset_dirs:
                os.makedirs(os.path.join(output_dir, dir_name), exist_ok=True)
            
            # Get all image files
            image_files = []
            for ext in ['.jpg', '.jpeg', '.png']:
                image_files.extend(Path(images_dir).glob(f'*{ext}'))
                image_files.extend(Path(images_dir).glob(f'*{ext.upper()}'))
            
            # Split dataset
            np.random.shuffle(image_files)
            train_split = int(len(image_files) * 0.8)
            val_split = int(len(image_files) * 0.9)
            
            train_files = image_files[:train_split]
            val_files = image_files[train_split:val_split]
            test_files = image_files[val_split:]
            
            # Copy files to appropriate directories
            for split_name, files in [('train', train_files), ('val', val_files), ('test', test_files)]:
                for img_file in files:
                    # Copy image
                    dst_img = os.path.join(output_dir, 'images', split_name, img_file.name)
                    shutil.copy2(img_file, dst_img)
                    
                    # Copy corresponding annotation if exists
                    ann_file = os.path.join(annotations_dir, img_file.stem + '.txt')
                    if os.path.exists(ann_file):
                        dst_ann = os.path.join(output_dir, 'labels', split_name, img_file.stem + '.txt')
                        shutil.copy2(ann_file, dst_ann)
            
            logger.info(f"Dataset prepared: {len(train_files)} train, {len(val_files)} val, {len(test_files)} test")
            return self.create_dataset_config(output_dir)
            
        except Exception as e:
            logger.error(f"Dataset preparation error: {e}")
            raise
    
    def augment_dataset(self, dataset_path: str, augmentation_factor: int = 3):
        """Apply data augmentation to increase dataset size"""
        try:
            import albumentations as A
            
            # Define augmentation pipeline
            transform = A.Compose([
                A.HorizontalFlip(p=0.5),
                A.VerticalFlip(p=0.2),
                A.RandomRotate90(p=0.5),
                A.RandomBrightnessContrast(p=0.3),
                A.HueSaturationValue(p=0.3),
                A.GaussianBlur(p=0.2),
                A.RandomGamma(p=0.2),
                A.CLAHE(p=0.2),
            ], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))
            
            train_img_dir = os.path.join(dataset_path, 'images', 'train')
            train_label_dir = os.path.join(dataset_path, 'labels', 'train')
            
            image_files = list(Path(train_img_dir).glob('*.jpg'))
            
            for img_file in image_files:
                # Load image
                image = cv2.imread(str(img_file))
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                # Load annotations
                label_file = os.path.join(train_label_dir, img_file.stem + '.txt')
                bboxes = []
                class_labels = []
                
                if os.path.exists(label_file):
                    with open(label_file, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                class_id = int(parts[0])
                                x_center, y_center, width, height = map(float, parts[1:5])
                                bboxes.append([x_center, y_center, width, height])
                                class_labels.append(class_id)
                
                # Apply augmentations
                for i in range(augmentation_factor):
                    try:
                        augmented = transform(image=image, bboxes=bboxes, class_labels=class_labels)
                        
                        # Save augmented image
                        aug_img_name = f"{img_file.stem}_aug_{i}.jpg"
                        aug_img_path = os.path.join(train_img_dir, aug_img_name)
                        aug_image = cv2.cvtColor(augmented['image'], cv2.COLOR_RGB2BGR)
                        cv2.imwrite(aug_img_path, aug_image)
                        
                        # Save augmented annotations
                        aug_label_path = os.path.join(train_label_dir, f"{img_file.stem}_aug_{i}.txt")
                        with open(aug_label_path, 'w') as f:
                            for bbox, class_id in zip(augmented['bboxes'], augmented['class_labels']):
                                f.write(f"{class_id} {' '.join(map(str, bbox))}\n")
                                
                    except Exception as e:
                        logger.warning(f"Augmentation failed for {img_file.name}: {e}")
                        continue
            
            logger.info(f"Dataset augmentation completed with factor {augmentation_factor}")
            
        except ImportError:
            logger.warning("Albumentations not installed, skipping augmentation")
        except Exception as e:
            logger.error(f"Dataset augmentation error: {e}")
    
    def train_model(self, dataset_config_path: str, **kwargs) -> str:
        """Train custom olive detection model"""
        try:
            # Update training config with kwargs
            config = self.training_config.copy()
            config.update(kwargs)
            
            # Load base model
            self.model = YOLO(self.base_model_path)
            
            # Start training
            logger.info("Starting model training...")
            results = self.model.train(
                data=dataset_config_path,
                **config
            )
            
            # Get best model path
            best_model_path = os.path.join(config['project'], config['name'], 'weights', 'best.pt')
            
            # Save training results
            training_results = {
                'training_date': datetime.now().isoformat(),
                'dataset_config': dataset_config_path,
                'training_config': config,
                'best_model_path': best_model_path,
                'results': str(results)
            }
            
            results_path = os.path.join(config['project'], config['name'], 'training_results.json')
            with open(results_path, 'w') as f:
                json.dump(training_results, f, indent=2)
            
            logger.info(f"Model training completed. Best model: {best_model_path}")
            return best_model_path
            
        except Exception as e:
            logger.error(f"Model training error: {e}")
            raise
    
    def evaluate_model(self, model_path: str, test_dataset_path: str) -> Dict:
        """Evaluate trained model performance"""
        try:
            # Load trained model
            model = YOLO(model_path)
            
            # Run validation
            results = model.val(data=test_dataset_path)
            
            # Extract metrics
            metrics = {
                'mAP50': float(results.box.map50),
                'mAP50-95': float(results.box.map),
                'precision': float(results.box.mp),
                'recall': float(results.box.mr),
                'f1_score': 2 * (float(results.box.mp) * float(results.box.mr)) / (float(results.box.mp) + float(results.box.mr)) if (float(results.box.mp) + float(results.box.mr)) > 0 else 0,
                'evaluation_date': datetime.now().isoformat()
            }
            
            logger.info(f"Model evaluation completed: mAP50={metrics['mAP50']:.3f}")
            return metrics
            
        except Exception as e:
            logger.error(f"Model evaluation error: {e}")
            return {}
    
    def export_model(self, model_path: str, export_format: str = 'onnx') -> str:
        """Export model to different formats"""
        try:
            model = YOLO(model_path)
            
            # Export model
            export_path = model.export(format=export_format)
            
            logger.info(f"Model exported to {export_format}: {export_path}")
            return export_path
            
        except Exception as e:
            logger.error(f"Model export error: {e}")
            raise
    
    def create_training_pipeline(self, images_dir: str, annotations_dir: str, 
                                output_model_path: str = "models/olive_custom.pt") -> Dict:
        """Complete training pipeline"""
        try:
            # Prepare dataset
            dataset_dir = "data/olive_dataset"
            os.makedirs(dataset_dir, exist_ok=True)
            
            dataset_config = self.prepare_dataset(images_dir, annotations_dir, dataset_dir)
            
            # Augment dataset
            self.augment_dataset(dataset_dir)
            
            # Train model
            best_model_path = self.train_model(dataset_config)
            
            # Evaluate model
            metrics = self.evaluate_model(best_model_path, dataset_config)
            
            # Copy best model to final location
            os.makedirs(os.path.dirname(output_model_path), exist_ok=True)
            shutil.copy2(best_model_path, output_model_path)
            
            # Create model info file
            model_info = {
                'model_path': output_model_path,
                'training_date': datetime.now().isoformat(),
                'dataset_path': dataset_dir,
                'metrics': metrics,
                'classes': ['olive_tree', 'olive_fruit'],
                'model_type': 'YOLOv8_custom_olive'
            }
            
            info_path = output_model_path.replace('.pt', '_info.json')
            with open(info_path, 'w') as f:
                json.dump(model_info, f, indent=2)
            
            logger.info(f"Training pipeline completed. Model saved: {output_model_path}")
            return model_info
            
        except Exception as e:
            logger.error(f"Training pipeline error: {e}")
            raise

class ModelManager:
    """Manage multiple models and their versions"""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
    
    def list_available_models(self) -> List[Dict]:
        """List all available models"""
        models = []
        
        for model_file in Path(self.models_dir).glob("*.pt"):
            info_file = model_file.with_suffix('').with_suffix('_info.json')
            
            model_info = {
                'name': model_file.stem,
                'path': str(model_file),
                'size': model_file.stat().st_size,
                'created': datetime.fromtimestamp(model_file.stat().st_ctime).isoformat()
            }
            
            if info_file.exists():
                try:
                    with open(info_file, 'r') as f:
                        additional_info = json.load(f)
                        model_info.update(additional_info)
                except Exception as e:
                    logger.warning(f"Could not load model info for {model_file}: {e}")
            
            models.append(model_info)
        
        return sorted(models, key=lambda x: x['created'], reverse=True)
    
    def get_best_model(self) -> Optional[str]:
        """Get the best performing model"""
        models = self.list_available_models()
        
        # Filter models with metrics
        models_with_metrics = [m for m in models if 'metrics' in m and 'mAP50' in m['metrics']]
        
        if not models_with_metrics:
            # Return default model if no custom models
            default_path = os.path.join(self.models_dir, 'yolov8n.pt')
            return default_path if os.path.exists(default_path) else None
        
        # Sort by mAP50 score
        best_model = max(models_with_metrics, key=lambda x: x['metrics']['mAP50'])
        return best_model['path']
    
    def delete_model(self, model_name: str) -> bool:
        """Delete a model and its info file"""
        try:
            model_path = os.path.join(self.models_dir, f"{model_name}.pt")
            info_path = os.path.join(self.models_dir, f"{model_name}_info.json")
            
            if os.path.exists(model_path):
                os.remove(model_path)
            
            if os.path.exists(info_path):
                os.remove(info_path)
            
            logger.info(f"Model deleted: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Model deletion error: {e}")
            return False

# Global instances
model_trainer = ZeytinModelTrainer()
model_manager = ModelManager()