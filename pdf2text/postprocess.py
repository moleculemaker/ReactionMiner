import json
import os

def postprocess_file(file_path, output_dir):
    """
    Process a single JSON file to extract relevant data and save it.
    """
    
    with open(file_path, "r", encoding="utf-8") as file:
        # Read content and decode Unicode escape sequences
        raw_content = file.read()
        # decoded_content = raw_content.encode("utf-8").decode("unicode_escape")
        data = json.loads(raw_content)

    # Extract `text` from abstract and body_text
    texts = []

    # From abstract
    if "pdf_parse" in data and "abstract" in data["pdf_parse"]:
        for abstract_section in data["pdf_parse"]["abstract"]:
            texts.append(abstract_section.get("text", ""))

    # From body_text
    if "pdf_parse" in data and "body_text" in data["pdf_parse"]:
        for body_section in data["pdf_parse"]["body_text"]:
            texts.append(body_section.get("text", ""))

    # Prepare output data
    output = {
        "fullText": " ".join(texts),  # Concatenate all text into one string
        "content": texts              # Keep each text as a separate entry
    }

    # Generate output file path
    output_file_path = os.path.join(output_dir, os.path.basename(file_path))
    with open(output_file_path, "w", encoding="utf-8") as output_file:
        json.dump(output, output_file, ensure_ascii=False, indent=4)
    print(f"Processed and saved: {output_file_path}")

def postprocess_directory(input_dir, output_dir):
    """
    Process all JSON files in a given directory and save the outputs.
    """
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Iterate through all files in the directory
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                postprocess_file(file_path, output_dir)

projectPath = os.path.dirname(os.path.abspath(__file__)) + "/../"

output_dir = projectPath + "/results"
final_output = projectPath + "/results/"
if __name__ == "__main__":
    postprocess_directory(output_dir, final_output)