import gc
import json
import logging
import os
from urllib.error import HTTPError

import requests
import sys
import traceback
from typing import BinaryIO, Tuple, Any
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

full_mapping = {}


# Read PDFs + locate matching JSONs on disk
# Create a mapping of PDF file -> JSON file
def parse_input_files(pdf_input_dir) -> Tuple[list[str], list[str]]:  # , dict[str, str]]:
    # Loop to collect lists of PDF/JSON file names
    pdf_files = []
    json_files = []

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
                json_file_name = pdf_file_name.replace('.pdf', '.json')
                json_file_path = os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, json_file_name)

                # Skip processing PDFs where no matching JSON is found
                if not os.path.exists(json_file_path):
                    logger.warning(f"  No matching JSON file found: {file}")
                else:
                    # For each matching PDF-JSON pair, add to CSV mapping
                    logger.info(f"     Matching JSON file found: {json_file_name}")

                    # Maintain lists of these pairs to submit at the end
                    pdf_files.append(pdf_file_name)
                    json_files.append(json_file_name)

        logger.debug('PDF Files: ' + str(pdf_files))
        logger.debug('JSON Files: ' + str(json_files))

        # Return lists of files and CSV mapping
        return pdf_files, json_files


def split_into_batches(data: list[Any], batch_size=CHEMSCRAPER_BATCH_SIZE) -> list[Any]:
    return [data[i:i + batch_size] for i in range(0, len(data), batch_size)]


# Write mapping as CSV or JSON to file
def save_mapping_file(file_path: str, mapping: dict[str, str], format: str = 'csv'):
    index = 0
    with open(file_path, 'w') as f:
        if format == 'json':
            # Write as JSON to file
            json.dump(mapping, f, indent=4)
        elif format == 'csv':
            # Write CSV headers - this is important
            f.write(f'id,pdf_name,json_name\n')

            # Read mapping to write CSV line by line
            for pdf_file in mapping:
                json_file = mapping[pdf_file]
                f.write(f'{index},{pdf_file},{json_file}\n')
                index += 1


# Submit mapping + related files to Chemscraper API
def submit_to_chemscraper(index_name: str, pdf_files: list[str], json_files: list[str]):
    logger.debug(f'Submitting the following inputs to ChemScraper')
    logger.debug(f'PDF Files: {str(pdf_files)}')
    logger.debug(f'JSON Files: {str(json_files)}')

    # Fail if there is a mismatch at this point between PDF and JSON input sizes
    if len(pdf_files) != len(json_files):
        raise ValueError("PDF -> JSON size mismatch")

    # Build a mapping from the files we are given
    mapping = dict(zip(pdf_files, json_files))

    # Save mapping.csv to disk, upload to MinIO later
    mapping_csv_file_path = os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, 'mapping.csv')
    save_mapping_file(file_path=mapping_csv_file_path, mapping=mapping)

    logger.debug(f'Mapping: {str(mapping)}')

    # Create a new ChemScraper API client and submit the
    # PDF + JSON files and the mapping that links them
    with Client(base_url=CHEMSCRAPER_BASE_URL) as client:
        return index_pdfs_reactions_batch.sync(
            client=client,
            index_name=index_name,
            body=IndexPdfsReactionsBatchPostBody(
                # Our list of ReactionMiner PDF inputs
                pdf_files=[File(
                    file_name=filename,
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_PDF_INPUT_DIR, filename)),
                    mime_type='application/pdf'
                ) for filename in pdf_files],

                # Our list of ReactionMiner JSON outputs
                json_reaction_files=[File(
                    file_name=filename,
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, filename)),
                    mime_type='application/json'
                ) for filename in json_files],

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
def write_json_output(output_path: str, data: object):
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
        pdf_files, json_files = parse_input_files(pdf_input_dir=CHEMSCRAPER_PDF_INPUT_DIR)

        batched_pdfs = split_into_batches(data=pdf_files)
        batched_json = split_into_batches(data=json_files)
        num_batches = len(batched_pdfs)

        for index in range(num_batches):
            pdf_batch_files = batched_pdfs[index]
            json_batch_files = batched_json[index]

            logger.info(f'Submitting ChemScraper batch ({index+1}/{num_batches})')

            # Extract input for each batch and submit to chemscraper API
            resp = submit_to_chemscraper(
                index_name=CHEMSCRAPER_INDEX_NAME,
                pdf_files=pdf_batch_files,
                json_files=json_batch_files
            )

            # Raise error status if no response body
            logger.debug("Response: " + str(resp))

            # Write JSON response to file
            if resp is not None:
                # Convert response dictionary to JSON
                output_file_path = os.path.join(CHEMSCRAPER_OUTPUT_DIR, f'chemscraper-output-batch-{index+1}.json')
                logger.info(f'Writing ChemScraper (batch {index+1}/{num_batches}) output to file: {output_file_path}')
                write_json_output(output_path=output_file_path, data={
                    f'batch-{index+1}': resp
                })
            else:
                # TODO: Handle response errors?
                # raise ValueError('Empty response encountered')
                logger.warning(f'Empty response encountered from ChemScraper API: {resp} - skipped writing output JSON')

        # Zip all JSON outputs into a single JSON file for the frontend
        merged_output = {}
        for root, _, files in os.walk(CHEMSCRAPER_OUTPUT_DIR):
            for filename in files:
                if filename.startswith('chemscraper-output-batch-'):
                    batch_output_file = os.path.join(CHEMSCRAPER_OUTPUT_DIR, filename)
                    try:
                        with open(batch_output_file) as f:
                            json_content = json.loads(f.read())
                            merged_output = merged_output | json_content
                    except FileNotFoundError as ex:
                        logger.warning(f'WARNING - batch output was expected, but not found: {batch_output_file}')
                        pass
                else:
                    logger.warning('Skipping file that is not ChemScraper output: ' + filename)

        # Write the merged ChemScraper JSON to output folder
        if len(merged_output) > 0:
            output_file_path = os.path.join(CHEMSCRAPER_OUTPUT_DIR, 'chemscraper-output.json')
            logger.info(f'Writing full ChemScraper output to file: {output_file_path}')
            write_json_output(output_path=output_file_path, data=merged_output)

            # Write full CSV mapping to file
            logger.info(f'Writing full ChemScraper mapping CSV to file: {output_file_path}')
            csv_mapping_path = os.path.join(CHEMSCRAPER_OUTPUT_DIR, 'mapping.csv')
            save_mapping_file(file_path=csv_mapping_path, mapping=full_mapping)

            # Save mapping.json to file as well
            logger.info(f'Writing full ChemScraper mapping JSON to file: {output_file_path}')
            json_mapping_path = os.path.join(CHEMSCRAPER_OUTPUT_DIR, 'mapping.json')
            save_mapping_file(file_path=json_mapping_path, mapping=full_mapping, format='json')
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
