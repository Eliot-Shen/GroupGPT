import os
import json
import torch
import argparse
import wandb
from tqdm import tqdm
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model

from prompts.intervene_prompt import interleave_prompt


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", type=str, required=True)
    parser.add_argument("--data_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="output")
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--wandb_project", type=str, default="Intervention")
    return parser.parse_args()


def load_and_convert_dataset(json_path, tokenizer):
    with open(json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    records = []
    for item in tqdm(raw_data):
        context = item.get("context", [])
        intervention = item.get("intervention", {})

        cleaned_context = []
        for msg in context:
            if "Intervention" in msg:
                msg_copy = {k: v for k, v in msg.items() if k != "Response"}
                cleaned_context.append(msg_copy)
            else:
                cleaned_context.append(msg)

        user_content = json.dumps(cleaned_context, ensure_ascii=False, indent=2)

        assistant_output = {
            "choice": intervention.get("Intervention", "")
        }

        if assistant_output["choice"] != "Stay Silent":
            assistant_output["reason"] = intervention.get("Reason", "")

        chat = [
            {"role": "system", "content": interleave_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(assistant_output, ensure_ascii=False)}
        ]

        formatted_text = tokenizer.apply_chat_template(chat, tokenize=False)
        records.append({"text": formatted_text})

    return Dataset.from_list(records)


def main():
    args = parse_args()

    os.environ["WANDB_MODE"] = "offline"
    wandb.init(project=args.wandb_project)

    # dtype
    torch_dtype = torch.bfloat16

    # model
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        device_map="auto",
        torch_dtype=torch_dtype,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({'pad_token': '[PAD]'})
        model.resize_token_embeddings(len(tokenizer))

    # dataset
    dataset = load_and_convert_dataset(args.data_path, tokenizer)

    # max length
    token_lens = []
    for t in dataset["text"]:
        token_lens.append(len(tokenizer(t)["input_ids"]))
    max_len = max(token_lens)

    dataset = dataset.shuffle(seed=42)

    def tokenize_fn(examples):
        tokens = tokenizer(
            examples["text"],
            truncation=True,
            padding="max_length",
            max_length=max_len
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    dataset = dataset.map(tokenize_fn, batched=True)
    dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])

    # LoRA
    peft_config = LoraConfig(
        r=16,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj", "k_proj", "v_proj",
            "down_proj", "up_proj", "o_proj", "gate_proj"
        ],
    )
    model = get_peft_model(model, peft_config)

    # training args
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        logging_steps=1,
        bf16=True,
        report_to="wandb",
    )

    trainer = Trainer(
        model=model,
        train_dataset=dataset,
        tokenizer=tokenizer,
        args=training_args,
    )

    trainer.train()
    trainer.model.save_pretrained(args.output_dir)

    wandb.finish()


if __name__ == "__main__":
    main()