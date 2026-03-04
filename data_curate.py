import os
import json
import glob
from typing import List, Dict, Any

from llm_api import GPTAPI
from prompts.data_curate_prompt import curate_label_system_prompt


# =========================
# Stage 1: Label Generation
# =========================
def generate_interventions_with_sliding_window(
    chat_json_path: str,
    output_json_path: str,
    window_size: int = 50,
    overlap: int = 10,
):
    with open(chat_json_path, "r", encoding="utf-8") as f:
        chat_data = json.load(f)

    conversation = chat_data.get("conversation", [])
    output_conversation = []
    processed_ids = set()
    all_interventions = []

    start_idx = 0

    while start_idx < len(conversation):
        end_idx = min(start_idx + window_size, len(conversation))
        window_conversation = conversation[start_idx:end_idx]

        simplified_conversation = []

        for msg in window_conversation:
            simplified_conversation.append({
                "user": msg["user"],
                "message": msg["message"],
                "id": msg["id"]
            })

            # 插入历史 intervention
            for intervention in all_interventions:
                if intervention["id"] == msg["id"]:
                    simplified_conversation.append({
                        "Past_Intervention": intervention["choice"],
                        "Reason": intervention["reason"],
                        "Response": intervention["response"]
                    })

        prompt = f"### Input\n{json.dumps({'conversation': simplified_conversation}, ensure_ascii=False, indent=2)}\n\n### Output"

        try:
            gpt = GPTAPI() # Substitute with your LLM API
            response = gpt.chat(
                system_prompt=curate_label_system_prompt,
                content=prompt,
                max_token=4096,
                temperature=0.1
            )

            try:
                interventions = json.loads(response)
                if not isinstance(interventions, list):
                    interventions = interventions.get("interventions", [])
            except:
                interventions = []

            for msg in window_conversation:
                if msg["id"] not in processed_ids:
                    output_msg = {
                        "user": msg["user"],
                        "message": msg["message"],
                        "id": msg["id"]
                    }
                    output_conversation.append(output_msg)
                    processed_ids.add(msg["id"])

                    for inter in interventions:
                        if inter.get("id") == msg["id"]:
                            intervention_msg = {
                                "Intervention": inter.get("choice", ""),
                                "Reason": inter.get("reason", ""),
                                "Response": inter.get("response", "")
                            }
                            output_conversation.append(intervention_msg)

                            all_interventions.append({
                                "id": msg["id"],
                                "choice": inter.get("choice", ""),
                                "reason": inter.get("reason", ""),
                                "response": inter.get("response", "")
                            })

        except Exception as e:
            print(f"[Label Error] {chat_json_path}: {e}")

        start_idx += max(1, window_size - overlap)

        # 实时保存
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump({"conversation": output_conversation}, f, ensure_ascii=False, indent=2)

    return {"conversation": output_conversation}


def batch_label(input_folder: str, output_folder: str):
    os.makedirs(output_folder, exist_ok=True)

    for file in os.listdir(input_folder):
        if file.endswith(".json"):
            in_path = os.path.join(input_folder, file)
            out_path = os.path.join(output_folder, file.replace(".json", "_labeled.json"))

            print(f"[Labeling] {file}")
            generate_interventions_with_sliding_window(in_path, out_path)


# =========================
# Stage 2: Training Sample Construction
# =========================
def process_single_file(conversations: List[Dict], window_size: int, max_gap: int, file_name: str):
    training_data = []
    start_idx = 0

    while start_idx < len(conversations):
        window_end = min(start_idx + window_size, len(conversations))
        window = conversations[start_idx:window_end]

        last_idx = -1
        for i, item in enumerate(window):
            if "Intervention" in item:
                last_idx = i

        if last_idx == -1:
            training_data.append(create_sample(window, {"Intervention": "Stay Silent"}, file_name))
            start_idx = window_end
            continue

        distance = len(window) - 1 - last_idx

        if distance > max_gap:
            training_data.append(create_sample(window, {"Intervention": "Stay Silent"}, file_name))
            start_idx = window_end
        else:
            context = window[:last_idx]
            label = window[last_idx]
            training_data.append(create_sample(context, label, file_name))
            start_idx += last_idx + 1

    return training_data


def create_sample(context_data, intervention_data, file_name):
    context = []

    for item in context_data:
        if "user" in item:
            context.append({
                "user": item["user"],
                "message": item["message"]
            })
        elif "Intervention" in item:
            context.append({
                "Intervention": item["Intervention"],
                "Reason": item.get("Reason", ""),
                "Response": item.get("Response", "")
            })

    if intervention_data.get("Intervention") == "Stay Silent":
        label = {"Intervention": "Stay Silent"}
    else:
        label = {
            "Intervention": intervention_data["Intervention"],
            "Reason": intervention_data.get("Reason", ""),
            "Response": intervention_data.get("Response", "")
        }

    return {
        "source": file_name,
        "context": context,
        "intervention": label
    }


def build_training_data(input_folder: str, output_path: str, window_size=20, max_gap=5):
    all_data = []

    files = glob.glob(os.path.join(input_folder, "*.json"))

    for f in files:
        print(f"[Training Build] {f}")
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        conv = data.get("conversation", [])
        file_data = process_single_file(conv, window_size, max_gap, os.path.basename(f))
        all_data.extend(file_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"[Done] Total samples: {len(all_data)}")


# =========================
# Main Pipeline
# =========================
def main():
    """
    Full Data Curation Pipeline

    1. Raw Chat → Labeled Chat
    2. Labeled Chat → Training Samples
    """

    RAW_DATA = "./raw_data"
    LABELED_DATA = "./labeled_data"
    OUTPUT_DATA = "./training_data.json"

    print("\n=== Stage 1: Labeling ===")
    batch_label(RAW_DATA, LABELED_DATA)

    print("\n=== Stage 2: Training Data Construction ===")
    build_training_data(LABELED_DATA, OUTPUT_DATA)

    print("\nData Curation Pipeline Completed!")


if __name__ == "__main__":
    main()