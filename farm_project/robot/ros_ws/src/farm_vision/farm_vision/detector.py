"""Shared real/sim detector. Geometry and capture metadata stay with each result."""
import numpy as np


class YoloSegmenter:
    def __init__(self, weights, config, device):
        from pathlib import Path
        import torch
        from ultralytics import YOLO
        if not Path(weights).is_file(): raise FileNotFoundError(f'Model not found: {weights}')
        if str(device).lower() != 'cpu' and not torch.cuda.is_available():
            raise RuntimeError('CUDA is unavailable in this Python environment; use --device cpu for a slow check')
        self.model = YOLO(str(weights),task='segment')
        self.config,self.device = config,device
        if self.model.task != 'segment': raise ValueError('A segmentation model is required')
        self.names = self.model.names

    def infer(self, network, valid, transform, original_shape):
        c = self.config
        result = self.model.predict(source=network, imgsz=c['input_size'], rect=False,
            conf=c['confidence'], iou=c['iou'], max_det=c['max_detections'],
            device=self.device, quantize=16 if c.get('half',False) and str(self.device) != 'cpu' else 32,
            retina_masks=True, augment=False, verbose=False, save=False)[0]
        if result.boxes is None or len(result.boxes) == 0: return [],[]
        if result.masks is None: raise RuntimeError('Model returned boxes without segmentation masks')
        rows = result.boxes.data.detach().cpu().numpy()
        masks = result.masks.data.detach().cpu().numpy() > .5
        if masks.shape[1:] != network.shape[:2] or len(masks) != len(rows):
            raise RuntimeError('Segmentation masks do not match the padded model input')
        detections,kept_masks = [],[]
        h,w = original_shape[:2]
        for row,mask in zip(rows,masks):
            mask = mask & valid
            yy,xx = np.nonzero(mask)
            if len(xx) < c['minimum_mask_pixels']: continue
            # Coordinates describe visible mask pixels inside B ROI, not simulator fruit IDs.
            box = transform.to_original([[xx.min(),yy.min()],[xx.max(),yy.max()]])
            box[:,0] = np.clip(box[:,0],0,w-1);box[:,1] = np.clip(box[:,1],0,h-1)
            class_id = int(row[-1])
            detections.append({'class_id':class_id,'class_name':str(self.names[class_id]),
                'confidence':float(row[-2]),'mask_box_original_xyxy':box.reshape(-1).tolist(),
                'mask_box_network_xyxy':[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())],
                'mask_pixels_network':len(xx)})
            kept_masks.append(mask)
        return detections,kept_masks
