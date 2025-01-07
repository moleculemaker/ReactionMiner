import os
import json
from os.path import join

# from pdf2text.generalParser import parseFile
from segmentation.segmentor import TopicSegmentor
from extraction.extractor import ReactionExtractor
from extraction.extract_postprocess import extract_postprocess
# pdf_path = "copper_acetate.pdf"

# Stage I: pdf to text
# The results will be automatically saved to pdf2text/results
directory = 'pdf2text/results'
for root, _, files in os.walk(directory):  # Walk through directory tree
    for filename in files:
        if filename.endswith(".json"):
            file_path = os.path.join(root, filename)
            print("########## Stage I: Reading File ##########")
            with open(file_path, 'r', encoding='utf-8') as json_file:
                result = json.load(json_file)
                full_text = result['fullText']  # Text without paragraph information
                paragraphs = result['content']  # Text with paragraph boundaries

# Stage II: text segmentation
                print("########## Stage II: Text Segmentation ##########")
                segmentor = TopicSegmentor()
                seg_texts = segmentor.segment(paragraphs)

# Stage III: reaction extraction
                print("########## Stage III: Reaction Extraction ##########")
                extractor = ReactionExtractor('8b')
                reactions = extractor.extract(seg_texts)
                write_path = 'extraction/results'
                os.makedirs(write_path, exist_ok=True)
                reaction_path = os.path.basename(file_path)
                full_path = join(write_path, reaction_path)
                with open(full_path, 'w', encoding='utf-8') as f:
                    json.dump(reactions, f, indent=4, ensure_ascii=False)
                extract_postprocess(full_path, 'extraction/results_filtered')
                print(f"The results are stored in {full_path}")