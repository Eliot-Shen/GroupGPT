import os, json, torch, argparse, wandb
from tqdm import tqdm
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model
from prompts.privacy_prompt import message_prompt

os.environ["WANDB_MODE"] = "offline"

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--base_model", type=str, required=True)
    parser.add_argument("--data_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="outputs")
    parser.add_argument("--max_len", type=int, default=1024)

    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-4)

    return parser.parse_args()


def load_and_convert_dataset(json_path, tokenizer):
    with open(json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    records = []
    for item in tqdm(raw_data, desc="Processing"):
        original_sentence = item.get("original_sentence")
        chosen_spans = item.get("chosen_spans", [])
        generated_sentence = item.get("generated_sentence")
        sentence = item.get("sentence")

        if sentence: # use as positive examples
            user_content = sentence
            assistant_output = {
                "has_disclosure": "false",
                "spans": [],
                "message": ""
            }
        else:
            user_content = original_sentence
            assistant_output = {
                "has_disclosure": "true" if chosen_spans else "false",
                "spans": chosen_spans,
                "message": generated_sentence if chosen_spans else ""
            }

        chat = [
            {"role": "system", "content": message_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(assistant_output, ensure_ascii=False)}
        ]

        text = tokenizer.apply_chat_template(chat, tokenize=False)
        records.append({"text": text})

    return Dataset.from_list(records)


def main():
    args = parse_args()

    torch_dtype = torch.bfloat16

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        device_map="auto",
        torch_dtype=torch_dtype
    )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)

    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({'pad_token': '[PAD]'})
        model.resize_token_embeddings(len(tokenizer))

    dataset = load_and_convert_dataset(args.data_path, tokenizer)
    dataset = dataset.shuffle(seed=42)

    def tokenize_fn(examples):
        tokens = tokenizer(
            examples["text"],
            truncation=True,
            padding="max_length",
            max_length=args.max_len
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    dataset = dataset.map(tokenize_fn, batched=True)
    dataset.set_format(type="torch")

    # LoRA
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj","k_proj","v_proj",
            "o_proj","gate_proj","up_proj","down_proj"
        ],
    )

    model = get_peft_model(model, peft_config)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        logging_steps=10,
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
    model.save_pretrained(args.output_dir)

    wandb.finish()


if __name__ == "__main__":
    main()