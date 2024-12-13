import json
import os
import subprocess
import config
projectPath = os.path.dirname(os.path.abspath(__file__)) + "/../"
output_dir = projectPath + "/results/"
temp_dir = projectPath + "/xml/"
def doc2json(input_dir, output_dir, temp_dir):
    """
    Recursively process all PDF files in a directory using doc2json/grobid2json/process_pdf.py.
    Args:
        input_dir (str): Path to the directory containing PDF files.
        output_dir (str): Path to the output directory for parsed JSON files.
        temp_dir (str): Path to the temporary directory for intermediate files.
    """
    # Ensure output and temporary directories exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Walk through the input directory
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                
                # Output JSON file path
                relative_path = os.path.relpath(pdf_path, input_dir)
                output_file = os.path.join(output_dir, f"{os.path.splitext(relative_path)[0]}.json")

                # Ensure the output directory structure is maintained
                os.makedirs(os.path.dirname(output_file), exist_ok=True)

                # Construct the command to process the PDF
                command = [
                    "python", os.path.join(projectPath,"s2orc-doc2json/doc2json/grobid2json/process_pdf.py"),
                    "-i", pdf_path,
                    "-t", temp_dir,
                    "-o", os.path.dirname(output_file)
                ]

                try:
                    print(f"Processing: {pdf_path}")
                    subprocess.run(command, check=True)
                    print(f"Output saved to: {output_file}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to process {pdf_path}: {e}")

def postprocess_file(file_path, output_dir):
    """
    Process a single JSON file to extract relevant data and save it.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            # Read content and decode Unicode escape sequences
            raw_content = file.read()
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

    except json.JSONDecodeError as e:
        # Handle JSON-specific errors
        print(f"Error decoding JSON in file {file_path}: {e}")
        print(f"Skipping file: {file_path}")
    except Exception as e:
        # Catch all other exceptions
        print(f"Unexpected error while processing file {file_path}: {e}")
        

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

if __name__ == "__main__":
    # Define input and output directories
    pdf_dir = os.path.join(projectPath, config.defaultDir )
    doc2json(pdf_dir, output_dir, temp_dir)
    # Process all files in the input directory
    postprocess_directory(output_dir, output_dir)
