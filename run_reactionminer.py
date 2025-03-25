import gc
import os
import json
import logging
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, wait

import torch

from segmentation.segmentor import TopicSegmentor
from extraction.extractor import ReactionExtractor
from extraction.extract_postprocess import extract_postprocess

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logger = logging.getLogger('run_reactionminer')
logger.setLevel(LOG_LEVEL)

# TODO: EXPERIMENTAL
# If MAX_WORKERS > 1, use process pool
# If MAX_WORKERS is 0, 1, or negative, then run synchronously in a loop
REACTIONMINER_MAX_WORKERS = int(os.getenv('REACTIONMINER_MAX_WORKERS', '1'))

# You can override these if needed
REACTIONMINER_SCRATCH_DIR = os.getenv('REACTIONMINER_SCRATCH_DIR', 'extraction/results')
REACTIONMINER_OUTPUT_DIR = os.getenv('REACTIONMINER_OUTPUT_DIR', 'extraction/results_filtered')

# Phase 2/3 use these shared resources
# These are expensive, so we reuse them across all loop iterations
segmentor = TopicSegmentor()
extractor = ReactionExtractor('8b')


# Run pdf2text and then ReactionMiner
def process_file(root, filename):
    tasklogger = logging.getLogger(f'reactionminer:process_file[{filename}]')

    tasklogger.info("########## Stage I: Reading File ##########")
    file_path = os.path.join(root, filename)
    with open(file_path, 'r', encoding='utf-8') as json_file:
        tasklogger.debug(f"JSON file found! Processing {file_path}...")
        result = json.load(json_file)

        # full_text = result['fullText']  # Text without paragraph information
        paragraphs = result['content']  # Text with paragraph boundaries

        # Stage II: text segmentation
        tasklogger.info("########## Stage II: Text Segmentation ##########")
        seg_texts = segmentor.segment(paragraphs)

        # Stage III: reaction extraction
        tasklogger.info("########## Stage III: Reaction Extraction ##########")
        tasklogger.debug("Now extracting...")
        reactions = extractor.extract(seg_texts)
        tasklogger.debug("Done extracting!")

        # Write JSON output file
        write_path = REACTIONMINER_SCRATCH_DIR
        os.makedirs(write_path, exist_ok=True)
        reaction_path = os.path.basename(file_path)
        full_path = os.path.join(write_path, reaction_path)
        tasklogger.info(f"Writing outputs: {full_path}")
        with open(full_path, 'w', encoding='utf-8') as f:
            tasklogger.debug(f"Writing file: {full_path}")
            json.dump(reactions, f, indent=4, ensure_ascii=False)
        tasklogger.debug(f"Done writing!")

    return True


if __name__ == "__main__":
    # The results will be automatically saved to pdf2text/results
    directory = 'results'
    logger.info(f"Searching {directory}")
    logger.debug(f"   Max Workers = {REACTIONMINER_MAX_WORKERS}")
    FILES = []

    try:
        for root, _, files in os.walk(directory):  # Walk through directory tree
            for filename in files:
                logger.debug(f"Checking {filename}")
                if filename.endswith(".json"):
                    if REACTIONMINER_MAX_WORKERS > 1:
                        # Run with process pool
                        FILES.append(filename)
                    else:
                        # Run synchronously:
                        process_file(root=root, filename=filename)
                else:
                    logger.warning(f"Skipping {filename}: JSON format required")

            # TODO: EXPERIMENTAL
            # If max workers > 1, run asynchronously using a process pool
            if REACTIONMINER_MAX_WORKERS > 1:
                with ProcessPoolExecutor(max_workers=REACTIONMINER_MAX_WORKERS) as executor:
                    logger.info(f'Starting tasks...')
                    futures = [executor.submit(process_file, root, file) for file in FILES]
                    logger.debug(f'Finished submission!')

                    logger.debug('Waiting for tasks to complete...')
                    wait(futures)
                    logger.info('All tasks are done!')

            # Run postprocessing
            logger.info('Running postprocessing...')
            extract_postprocess(REACTIONMINER_SCRATCH_DIR, REACTIONMINER_OUTPUT_DIR)
            logger.info('File processing complete!')
            logger.info(f"The results are stored in {REACTIONMINER_SCRATCH_DIR}")

    except Exception as ex:
        logger.error(f'ERROR: {ex}')
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        logger.warning(f'Cleaning up model & resources...')
        del segmentor
        del extractor
        collected_count = gc.collect()
        logger.warning(f'Cleaned up resources: {collected_count}')
        torch.cuda.empty_cache()
        logger.warning(f'Cache has been emptied. Shutting down...')

