import os
import json
from os.path import join

from segmentation.segmentor import TopicSegmentor
from extraction.extractor import ReactionExtractor
from extraction.extract_postprocess import extract_postprocess

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG
)
logger = logging.getLogger('run_reactionminer')

# Run pdf2text and then ReactionMiner
def process_file(filename):
    logger.debug(f"JSON file found! Processing {filename}...")
    file_path = os.path.join(root, filename)
    logger.info("########## Stage I: Reading File ##########")
    with open(file_path, 'r', encoding='utf-8') as json_file:
        result = json.load(json_file)
        #full_text = result['fullText']  # Text without paragraph information
        paragraphs = result['content']  # Text with paragraph boundaries

        # Stage II: text segmentation
        logger.info("########## Stage II: Text Segmentation ##########")
        segmentor = TopicSegmentor()
        seg_texts = segmentor.segment(paragraphs)

        # Stage III: reaction extraction
        logger.info("########## Stage III: Reaction Extraction ##########")
        extractor = ReactionExtractor('8b')
        logger.debug("Now extracting...")
        reactions = extractor.extract(seg_texts)
        logger.debug("Done extracting!")
        write_path = 'extraction/results'
        os.makedirs(write_path, exist_ok=True)
        reaction_path = os.path.basename(file_path)
        full_path = join(write_path, reaction_path)
        logger.info(f"Writing outputs: {write_path}")
        with open(full_path, 'w', encoding='utf-8') as f:
            logger.debug(f"Writing file: {full_path}")
            json.dump(reactions, f, indent=4, ensure_ascii=False)
        logger.debug(f"Done writing!")
        extract_postprocess(write_path, 'extraction/results_filtered')
        logger.info(f"The results are stored in {full_path}")

        return True

if __name__ == "__main":
    # The results will be automatically saved to pdf2text/results
    directory = 'results'
    logger.info(f"Searching for {directory}")
    FILES = []

    try:
        for root, _, files in os.walk(directory):  # Walk through directory tree
            for filename in files:
                logger.debug(f"Checking {filename}")
                if filename.endswith(".json"):
                    FILES.append(filename)
                else:
                    logger.warning(f"Skipping {filename}: JSON format required")

            with concurrent.futures.ProcessPoolExecutor() as executor:
                for filename, in zip(FILES, executor.map(process_file, FILES)):
    except Exception as ex:
        logger.error(f'ERROR: {ex}')
        sys.exit(1)