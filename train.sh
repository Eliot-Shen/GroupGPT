#!/bin/bash

BASE_MODEL=/path-to-your-base-model
DATA_PATH=./dataset/MUIR_training_data.json
OUTPUT_DIR=./outputs/intervention-lora

python train.py \
    --base_model $BASE_MODEL \
    --data_path $DATA_PATH \
    --output_dir $OUTPUT_DIR \
    --batch_size 2 \
    --grad_accum 4 \
    --epochs 2 \
    --lr 2e-4 