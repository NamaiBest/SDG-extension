"""
LoRA fine-tuning script for the remedies dataset.
Default base model is TinyLlama for lightweight local runs; switch to a larger model if you have GPU capacity.
"""
import argparse
import json
from pathlib import Path
from typing import Dict, Any

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


def build_prompt(example: Dict[str, Any]) -> str:
    parts = [
        "You are a remedies assistant. Answer with concise, safe, and practical guidance.",
        f"Problem: {example.get('problem', '').strip()}",
    ]
    if example.get("symptoms"):
        parts.append(f"Symptoms: {example['symptoms'].strip()}")
    if example.get("possible_causes"):
        parts.append(f"Possible causes: {example['possible_causes'].strip()}")
    if example.get("ingredients"):
        parts.append(f"Ingredients: {example['ingredients'].strip()}")
    if example.get("preparation"):
        parts.append(f"Preparation: {example['preparation'].strip()}")
    system_prompt = "\n".join(parts)
    answer = example.get("remedy", "").strip()
    return f"{system_prompt}\n\nRemedy: {answer}"


def tokenize_function(example, tokenizer, max_length: int):
    text = build_prompt(example)
    tokenized = tokenizer(
        text,
        truncation=True,
        max_length=max_length,
        padding="max_length",
    )
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_path",
        default="raw_data/merged_dataset.json",
        help="Path to the remedies JSON file",
    )
    parser.add_argument(
        "--model_name",
        default="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        help="Base model to fine-tune",
    )
    parser.add_argument(
        "--output_dir",
        default="outputs/remedy-llama-lora",
        help="Where to write LoRA adapter and tokenizer",
    )
    parser.add_argument("--num_epochs", type=float, default=2.0)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--gradient_accumulation", type=int, default=4)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_length", type=int, default=768)
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument("--use_qlora", action="store_true", help="Enable QLoRA (4-bit)")
    return parser.parse_args()


def main():
    args = parse_args()

    if not Path(args.data_path).exists():
        raise FileNotFoundError(f"Dataset not found at {args.data_path}")

    bnb_config = None
    if args.use_qlora:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map="auto",
    )

    if args.use_qlora:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    dataset = load_dataset("json", data_files=args.data_path)["train"]
    if args.max_samples:
        dataset = dataset.select(range(min(args.max_samples, len(dataset))))

    tokenized_dataset = dataset.map(
        lambda ex: tokenize_function(ex, tokenizer, args.max_length),
        remove_columns=dataset.column_names,
    )

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    use_cuda = torch.cuda.is_available()

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.learning_rate,
        fp16=use_cuda,
        bf16=use_cuda,
        logging_steps=10,
        save_strategy="epoch",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    print(f"LoRA adapter saved to {args.output_dir}")


if __name__ == "__main__":
    main()
