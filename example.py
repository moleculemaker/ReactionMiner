import os
import json
from os.path import join

# from pdf2text.generalParser import parseFile
from segmentation.segmentor import TopicSegmentor
from extraction.extractor import ReactionExtractor
from extraction.extract_postprocess import extract_postprocess
# pdf_path = "copper_acetate.pdf"

def main():
    # The results will be automatically saved to pdf2text/results
    directory = 'results'
    print(f"Searching for {directory}")
    filenames = []
    for root, _, files in os.walk(directory):  # Walk through directory tree
        for filename in files:
            if filename.endswith(".json"):
                # process_json_file(root, filename)
                filenames.append({'filename': filename, 'root': root})
            else:
                print(f"Skipping {filename}: JSON format required")

    with concurrent.futures.ProcessPoolExecutor() as executor:
        for filepath, rxns in zip(args, executor.map(process_json_file, args)):
            write_output_files(file_path=filepath, reactions=rxns)

def process_json_file(args):
    root = args['root']
    filename = args['filename']
    file_path, full_text, paragraphs = read_json_file(root=root, filename=filename)
    seg_texts = run_text_segmentation(paragraphs)
    reactions = extract_reactions(seg_texts)
    return file_path, reactions

# Stage I: pdf to text
def read_json_file(root, filename):
    print(f"Checking {filename}")
    print(f"JSON file found! Processing {filename}...")
    file_path = os.path.join(root, filename)
    print("########## Stage I: Reading File ##########")
    with open(file_path, 'r', encoding='utf-8') as json_file:
        result = json.load(json_file)
        full_text = result['fullText']  # Text without paragraph information
        paragraphs = result['content']  # Text with paragraph boundaries

    return file_path, full_text, paragraphs

# Stage II: text segmentation
def run_text_segmentation(paragraphs):
    print("########## Stage II: Text Segmentation ##########")
    segmentor = TopicSegmentor()
    seg_texts = segmentor.segment(paragraphs)
    return seg_texts

# Stage III: reaction extraction
def extract_reactions(seg_texts):
    print("########## Stage III: Reaction Extraction ##########")
    extractor = ReactionExtractor('8b')
    print("Now extracting...")
    reactions = extractor.extract(seg_texts)
    print("Done extracting!")
    return reactions

# Post-processing
def write_and_postprocess(file_path, reactions):
    write_path = 'extraction/results'
    os.makedirs(write_path, exist_ok=True)
    reaction_path = os.path.basename(file_path)
    full_path = join(write_path, reaction_path)
    print(f"Writing outputs: {write_path}")
    with open(full_path, 'w', encoding='utf-8') as f:
        print(f"Writing file: {full_path}")
        json.dump(reactions, f, indent=4, ensure_ascii=False)
    print(f"Done writing!")
    print(f"Running post-processing...")
    extract_postprocess(write_path, 'extraction/results_filtered')
    print(f"Post-processing completed successfully!\n")
    print(f"Job complete!")
    print(f"The results are stored in {full_path}")

    return full_path


if __name__=="__main__":
    main()