import gc
import json
import logging
import os
from urllib.error import HTTPError

import requests
import sys
import traceback
from typing import BinaryIO, Tuple
from io import BytesIO

import torch

from chemscraper.fast_api_client import Client
from chemscraper.fast_api_client.models import HTTPValidationError
from chemscraper.fast_api_client.types import File
from chemscraper.fast_api_client.api.default import index_pdfs_reactions_batch_index_pdfs_reactions_batch_post as index_pdfs_reactions_batch
from chemscraper.fast_api_client.api.default.index_pdfs_reactions_batch_index_pdfs_reactions_batch_post import BodyIndexPdfsReactionsBatchIndexPdfsReactionsBatchPost as IndexPdfsReactionsBatchPostBody

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logger = logging.getLogger('run_chemscraper')
logger.setLevel(LOG_LEVEL)

# Path to input PDFs for RM+CS
# Files in this path will be automatically downloaded from MinIO before running the AlphaSynthesis job
CHEMSCRAPER_PDF_INPUT_DIR = os.environ.get('CHEMSCRAPER_PDF_INPUT_DIR', '/workspace/10test')

# Path to output JSONs from ReactionMiner
# Files in this path will be automatically uploaded to MinIO after running the AlphaSynthesis job
CHEMSCRAPER_REACTIONMINER_JSON_DIR = os.environ.get('CHEMSCRAPER_REACTIONMINER_JSON_DIR', '/workspace/extraction/results_filtered')

# Path to output from full RM+CS workflow
# We store to the same path as ReactionMiner outputs, so that this is also uploaded to MinIO
CHEMSCRAPER_OUTPUT_DIR = os.environ.get('CHEMSCRAPER_OUTPUT_DIR', CHEMSCRAPER_REACTIONMINER_JSON_DIR)

# A unique string identifier for this searchable index
# Used when submitting to the /search endpoint
CHEMSCRAPER_INDEX_NAME = os.environ.get('CHEMSCRAPER_INDEX_NAME', os.environ.get('JOB_ID', 'test'))

# Maximum number of PDFs to send for each batch of ChemScraper requests
# Setting this to 0 or a negative number will run all PDFs in a single batch
CHEMSCRAPER_BATCH_SIZE = int(os.environ.get('CHEMSCRAPER_BATCH_SIZE', '10'))

# Base URL to ChemScraper API
# We will override this default in production
CHEMSCRAPER_BASE_URL = os.environ.get('CHEMSCRAPER_BASE_URL', 'http://chemscraper-services-staging.staging.svc.cluster.local:8000')


# Read PDFs + locate matching JSONs on disk
# Create a mapping of PDF file -> JSON file
def parse_input_files(pdf_input_dir) -> list[Tuple[list[str], list[str], dict[str, str]]]:
    # Loop to build up CSV mapping and file lists
    mapping = {}
    pdf_files = []
    json_files = []
    batches = []

    # Walk input PDF directory looking for PDF files
    for root, _, files in os.walk(pdf_input_dir):
        logger.info(f"Current directory: {root}")
        for file in files:
            # Skip non-PDF files
            if not file.endswith(".pdf"):
                logger.debug(f"  Skipping non-PDF File: {file}")
            else:
                # If a PDF is found, check for a matching JSON file
                pdf_file_name = file
                logger.info(f"  PDF File: {pdf_file_name}")
                pdf_file_path = os.path.join(root, file)
                json_file_name = pdf_file_name.replace('.pdf', '.json')
                json_file_path = os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, json_file_name)

                # Skip processing PDFs where no matching JSON is found
                if not os.path.exists(json_file_path):
                    logger.warning(f"  No matching JSON file found: {file}")
                else:
                    # For each matching PDF-JSON pair, add to CSV mapping
                    logger.info(f"     Matching JSON file found: {json_file_name}")

                    # If this batch is too large, add it to our running list of batches
                    if CHEMSCRAPER_BATCH_SIZE > 0 and len(pdf_files) <= CHEMSCRAPER_BATCH_SIZE:
                        batches.append((pdf_files[:], json_files[:], mapping.copy()))
                        pdf_files = []
                        json_files = []
                        mapping = {}

                    # Maintain lists of these pairs to submit at the end
                    mapping[pdf_file_name] = json_file_name
                    pdf_files.append(pdf_file_path)
                    json_files.append(json_file_path)

                    # Make sure to add in the last batch every time
                    batches.append((pdf_files, json_files, mapping))

        logger.debug('PDF Files: ' + str(pdf_files))
        logger.debug('JSON Files: ' + str(json_files))
        logger.debug('Mapping: ' + str(mapping))

        # Return lists of files and CSV mapping
        return batches


# Write mapping.csv to file, and submit this file with our request
def save_mapping_csv(file_path: str, mapping: dict[str, str]):
    index = 0
    with open(file_path, 'w') as f:
        # Write CSV headers - this is important
        f.write(f'id,pdf_name,json_name\n')
        for pdf_file in mapping:
            # Read mapping to write CSV line by line
            json_file = mapping[pdf_file]
            f.write(f'{index},{pdf_file},{json_file}\n')
            index += 1


# Submit mapping + related files to Chemscraper API
def submit_to_chemscraper(index_name: str, pdf_files: list[str], json_files: list[str], mapping: dict[str, str]):
    # Save mapping.csv to disk, upload to MinIO later
    mapping_csv_file_path = os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, 'mapping.csv')
    save_mapping_csv(file_path=mapping_csv_file_path, mapping=mapping)

    # Create a new ChemScraper API client and submit the
    # PDF + JSON files and the mapping that links them
    with Client(base_url=CHEMSCRAPER_BASE_URL) as client:
        return index_pdfs_reactions_batch.sync(
            client=client,
            index_name=index_name,
            body=IndexPdfsReactionsBatchPostBody(
                # Our list of ReactionMiner PDF inputs
                pdf_files=[File(
                    file_name=file.split('/')[-1],
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_PDF_INPUT_DIR, file)),
                    mime_type='application/pdf'
                ) for file in pdf_files],

                # Our list of ReactionMiner JSON outputs
                json_reaction_files=[File(
                    file_name=file.split('/')[-1],
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, file)),
                    mime_type='application/json'
                ) for file in json_files],

                # The CSV created earlier that maps PDF file -> JSON file
                mapping_file=File(
                    file_name='mapping.csv',
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, 'mapping.csv')),
                    mime_type='text/csv'
                ),
            )
        )


# TODO: Read large files in chunks?
def read_file_bytes(path: str) -> BinaryIO:
    with open(path, mode='rb') as f:
        return BytesIO(f.read())


# Write ChemScraper JSON response to file
def write_json_output(output_path: str, data: object, batch_number: int = None, num_batches: int = None):
    with open(output_path, "w") as f:
        json_contents = json.dumps(data, indent=4, ensure_ascii=False)
        logger.debug("Writing JSON contents: " + json_contents)
        f.write(json_contents)


# Walk directory and build up a mapping to submit to ChemScraper
# exit with error code = 1 if any error encountered
# (error code = 0 indicates success)
if __name__ == "__main__":
    logger.info(f'Submitting these files to ChemScraper')
    logger.info(f'  Index Name: {CHEMSCRAPER_INDEX_NAME}')
    logger.info(f'  Batch Size: {CHEMSCRAPER_BATCH_SIZE}')
    logger.info(f'  PDF  Input Dir: {CHEMSCRAPER_PDF_INPUT_DIR}')
    logger.info(f'  JSON Input Dir: {CHEMSCRAPER_REACTIONMINER_JSON_DIR}')
    logger.info(f'  Output Dir: {CHEMSCRAPER_OUTPUT_DIR}')

    try:
        batches = parse_input_files(pdf_input_dir=CHEMSCRAPER_PDF_INPUT_DIR)
        num_batches = len(batches)
        logger.info(f"Submitting {num_batches} batches")
        logger.debug(str(batches))
        for index in range(num_batches):
            # Extract input for each batch and submit to chemscraper API
            pdf_files, json_files, mapping = batch = batches[index]
            num_files = len(pdf_files)
            logger.info(f"Batch {index+1} / {num_batches}")
            logger.debug(str(batch))
            resp = submit_to_chemscraper(index_name=CHEMSCRAPER_INDEX_NAME, pdf_files=pdf_files, json_files=json_files, mapping=mapping)

            # Raise error status if no response body
            logger.debug("Response: " + str(resp))

            # Write JSON response to file
            if resp is not None:
                # Convert response dictionary to JSON
                output_file_path = os.path.join(CHEMSCRAPER_OUTPUT_DIR, f'chemscraper-output-batch-{index}.json')
                logger.info(f'Writing ChemScraper (batch {index}/{num_batches}) output to file: {output_file_path}')
                write_json_output(output_path=output_file_path, data=resp)
            else:
                # Handle response errors
                raise HTTPError(code=500, msg='ERROR: Empty response encountered')

        # Zip all JSON outputs into a single JSON file for the frontend
        merged_output = {}
        for root, _, files in os.walk(CHEMSCRAPER_OUTPUT_DIR):
            for name in files:
                batch_output_file = os.path.join(CHEMSCRAPER_OUTPUT_DIR, name)
                try:
                    with open(batch_output_file) as f:
                        merged_output = merged_output | json.load(fp=f)
                except FileNotFoundError as ex:
                    logger.warning(f'WARNING - batch output was expected, but not found: {batch_output_file}')
                    pass

        # Write the merged JSON to output folder
        if len(merged_output) > 0:
            output_file_path = os.path.join(CHEMSCRAPER_OUTPUT_DIR, f'chemscraper-output.json')
            logger.info(f'Writing full ChemScraper output to file: {output_file_path}')
            write_json_output(output_path=output_file_path, data=merged_output)
        else:
            logger.error('ERROR: merged_output was empty - check that any batch produced a valid output file')

    except Exception as ex:
        logger.error(f'ERROR: {ex}')
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        logger.warning(f'Cleaning up resources...')
        collected_count = gc.collect()
        logger.warning(f'Cleaned up resources: {collected_count}')
        torch.cuda.empty_cache()
        logger.warning(f'Cache has been emptied. Shutting down...')
