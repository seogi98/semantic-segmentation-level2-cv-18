import os
import random
import json
import yaml
import argparse
import warnings 
warnings.filterwarnings('ignore')

import torch
import torch.nn as nn # criterion, optimizer 모듈화 끝나면 삭제 가능


from importlib import import_module
from pprint import pprint

# For TTA
import ttach as tta

# IMPORT CUSTOM MODULES
from util.ploting import (
    plot_examples, plot_train_dist
)
from data.dataloader import (
    get_dataloaders
)
from train import (
    train, get_trainable_model
)
from inference import (
    create_submission, get_trained_model
)
from util.eda import (
    get_df_train_categories_counts, add_bg_index_to, eda
)
from config.read_config import (
    print_ver_n_settings, get_cfg_from, get_args
)
from config.fix_seed import (
    fix_seed_as
)
from config.wnb import (
    wnb_init
)

# GPU 사용 가능 여부에 따라 device 정보 저장
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


if __name__ == "__main__":
    cfg = get_cfg_from(get_args())
    fix_seed_as(cfg["SEED"])
    
    
    wnb_run = wnb_init(cfg)
    print_ver_n_settings()
    eda(cfg)
    pprint(cfg)
    
    df_train_categories_counts = get_df_train_categories_counts(cfg)
    plot_train_dist(cfg, df_train_categories_counts)
    sorted_df_train_categories_counts = add_bg_index_to(df_train_categories_counts)
    category_names = sorted_df_train_categories_counts["Categories"].to_list()
    
    model = get_trainable_model(cfg)
    train_dataloader, val_dataloader, test_dataloader = get_dataloaders(cfg, category_names)
    
    train(num_epochs=cfg["EXPERIMENTS"]["NUM_EPOCHS"], 
          model=model, 
          train_dataloader=train_dataloader, 
          val_dataloader=val_dataloader, 
          criterion=nn.CrossEntropyLoss(), 
          optimizer=torch.optim.Adam(params = model.parameters(), 
                                     lr=cfg["EXPERIMENTS"]["LEARNING_RATE"], 
                                     weight_decay=1e-6), 
          saved_dir=cfg["EXPERIMENTS"]["SAVED_DIR"]["BEST_MODEL"], 
          val_every=cfg["EXPERIMENTS"]["VAL_EVERY"], 
          device=DEVICE,
          category_names=category_names,
          cfg=cfg)
    
    model_trained = get_trained_model(cfg, DEVICE)
    if cfg["EXPERIMENTS"]["TTA_TURN_ON"]:
        tta_cfg = cfg["EXPERIMENTS"]["TTA_CFG"]
        tta_trans = tta.Compose([getattr(tta.transforms, trans)(**cfg) for trans, cfg in tta_cfg.items()])
        model_trained = tta.SegmentationTTAWrapper(model=model_trained, 
                                                   transforms=tta_trans,
                                                   merge_mode="mean")
        model_trained.to(DEVICE)
    
    create_submission(model=model_trained, 
                      test_dataloader=test_dataloader, 
                      device=DEVICE,
                      cfg=cfg)
    
    if wnb_run is not None:
        wnb_run.finish()
    