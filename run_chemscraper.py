import logging
import os
import requests
import sys
from typing import BinaryIO
from io import BytesIO

from chemscraper.fast_api_client import Client
from chemscraper.fast_api_client.types import File
from chemscraper.fast_api_client.api.default import index_pdfs_reactions_batch_index_pdfs_reactions_batch_post as index_pdfs_reactions_batch
from chemscraper.fast_api_client.api.default.index_pdfs_reactions_batch_index_pdfs_reactions_batch_post import BodyIndexPdfsReactionsBatchIndexPdfsReactionsBatchPost as IndexPdfsReactionsBatchPostBody

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG
)
logger = logging.getLogger('run_chemscraper')

# Path to input PDFs for RM+CS
CHEMSCRAPER_PDF_INPUT_DIR = os.environ.get('CHEMSCRAPER_PDF_INPUT_DIR', '/workspace/10test')

# Path to output JSONs from ReactionMiner
CHEMSCRAPER_REACTIONMINER_JSON_DIR = os.environ.get('CHEMSCRAPER_REACTIONMINER_JSON_DIR', '/workspace/extraction/results_filtered')

# Path to output from full RM+CS workflow
CHEMSCRAPER_OUTPUT_DIR = os.environ.get('CHEMSCRAPER_OUTPUT_DIR', '/workspace/extraction/results_filtered')

# Path to output from full RM+CS workflow
CHEMSCRAPER_INDEX_NAME = os.environ.get('CHEMSCRAPER_INDEX_NAME', os.environ.get('JOB_ID'))

# Base URL to ChemScraper API
CHEMSCRAPER_BASE_URL = os.environ.get('CHEMSCRAPER_BASE_URL', 'http://chemscraper-services-staging.staging.svc.cluster.local:8000')

# Read PDFs + locate matching JSONs from disk
def locate_matching_files(pdf_input_dir):
    # Loop to build up CSV mapping and file lists
    mapping = {}
    pdf_files = []
    json_files = []
    file_uploads = []

    for root, _, files in os.walk(pdf_input_dir):
        logger.info(f"Current directory: {root}")
        for file in files:
            if file.endswith(".pdf"):
                logger.info(f"  PDF File: {file}")
                pdf_file_name = file
                pdf_file_path = os.path.join(root, file)
                json_file_name = file.replace('.pdf', '.json')
                json_file_path = os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, json_file_name)
                if os.path.exists(json_file_path):
                    # For each matching PDF-JSON pair, add to CSV mapping
                    logger.info(f"  Matching JSON file found: {json_file_name}")
                    mapping[file] = json_file_name
                    file_uploads.append(('pdf_files', (pdf_file_name, open(pdf_file_path, 'rb'), 'application/pdf')))
                    pdf_files.append(pdf_file_path)
                    file_uploads.append(('json_files', (json_file_name, open(json_file_path, 'rb'), 'application/json')))
                    json_files.append(json_file_path)
                else:
                    logger.warning(f"  No matching JSON file found: {file}")
            else:
                logger.debug(f"  Skipping non-PDF File: {file}")

        logger.debug('PDF Files: ' + str(pdf_files))
        logger.debug('JSON Files: ' + str(json_files))
        logger.debug('Mapping: ' + str(mapping))

        # Return lists of files and CSV mapping
        return pdf_files, json_files, mapping, file_uploads


# Write mapping.csv to file, and submit this file with our request
def write_mapping_csv(mapping):
    index = 0
    with open(os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, 'mapping.csv'), 'w') as f:
        f.write(f'id,pdf_name,json_name\n')
        for pdf_file in mapping:
            json_file = mapping[pdf_file]
            f.write(f'{index},{pdf_file},{json_file}\n')
            index += 1

# Submit mapping + related files to Chemscraper API
def submit_to_chemscraper(index_name, pdf_files, json_files, mapping):
    try:
        with Client(base_url=CHEMSCRAPER_BASE_URL) as client:
            response = index_pdfs_reactions_batch.sync(client=client, index_name=index_name, body=IndexPdfsReactionsBatchPostBody(
                pdf_files=[File(
                    file_name=file.split('/')[-1],
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_PDF_INPUT_DIR, file)),
                    mime_type='application/pdf'
                ) for file in pdf_files],
                json_reaction_files=[File(
                    file_name=file.split('/')[-1],
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, file)),
                    mime_type='application/json'
                ) for file in json_files],
                mapping_file=File(
                    file_name='mapping.csv',
                    payload=read_file_bytes(os.path.join(CHEMSCRAPER_REACTIONMINER_JSON_DIR, 'mapping.csv')),
                    mime_type='text/csv'
                ),
            ))

            logger.debug("Response: " + str(response))
    except Exception as ex:
        logger.error(f'ERROR: {ex}')
        sys.exit(1)

# TODO: Read large files in chunks?
def read_file_bytes(path) -> BinaryIO:
    with open(path, mode='rb') as f:
        return BytesIO(f.read())
    #return open(path, mode='rb')


def main():
    logger.info(f'Submitting these files to ChemScraper')
    logger.info(f'  Index Name: {CHEMSCRAPER_INDEX_NAME}')
    logger.info(f'  PDF  Input Dir: {CHEMSCRAPER_PDF_INPUT_DIR}')
    logger.info(f'  JSON Input Dir: {CHEMSCRAPER_REACTIONMINER_JSON_DIR}')
    logger.info(f'  Output Dir: {CHEMSCRAPER_OUTPUT_DIR}')

    pdf_files, json_files, mapping, file_uploads = locate_matching_files(pdf_input_dir=CHEMSCRAPER_PDF_INPUT_DIR)
    write_mapping_csv(mapping)
    submit_to_chemscraper(index_name=CHEMSCRAPER_INDEX_NAME, pdf_files=pdf_files, json_files=json_files, mapping=mapping)

if __name__ == "__main__":
    main()



#
# try:
#     params = {
#         'index_name': CHEMSCRAPER_INDEX_NAME
#     }
#     print('Params: ' + str(params))
#     file_uploads.append(('mapping_file', mapping_file))
#     print('File Uploads: ' + str(file_uploads))
#     response = requests.post(url=url, params=params, data=file_uploads)
#
#     #  Wait for response
#     if response.ok:
#         print('Upload successful. Saving response locally...')
#         # TODO: Save output files to disk so they are uploaded to MinIO
#         output_file_path = os.path.join('/workspace/extraction/results_filtered', 'reactionminer-chemscraper-output.json')
#         print(response.text)
#         with open(output_file_path, 'w') as f:
#             f.write(response.text)
#     else:
#         print(f'Error: Upload failed - {response.status_code} - ')
#         response.raise_for_status()
#
# except requests.exceptions.HTTPError as errh:
#     print(f"HTTP Error: {errh}")
# except requests.exceptions.ConnectionError as errc:
#     print(f"Connection Error: {errc}")
# except requests.exceptions.Timeout as errt:
#     print(f"Timeout Error: {errt}")
# except requests.exceptions.RequestException as err:
#     print(f"Something went wrong: {err}")
#
#
#
