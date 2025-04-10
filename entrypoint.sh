#!/bin/bash

# Stop script if any error is encountered
set -e

# Replace GROBID_SERVER in conf file
sed -i -e "s/localhost/${GROBID_SERVER}/g" /workspace/s2orc-doc2json/doc2json/grobid2json/grobid/grobid_client.py

# Run pdf2text in the doc2json conda env
echo '######################################'
echo '#######    RUNNING pdf2text    #######'
echo '######################################'
cd /workspace/pdf2text
if [[ -z "${SKIP_PDF2TEXT}" ]]; then
  conda run --no-capture-output -n doc2json bash ./pdf2txt.sh
else
  echo 'SKIP_PDF2TEXT is set, skipping pdf2text stage'
fi


# TODO: move files?

# Run reactionminer example script in the base conda env
echo '###########################################'
echo '#######    RUNNING ReactionMiner    #######'
echo '###########################################'
cd /workspace
if [[ -z "${SKIP_REACTIONMINER}" ]]; then
  python ./run_reactionminer.py
else
  echo 'SKIP_REACTIONMINER is set, skipping ReactionMiner stage'
fi

# Run ChemScraper using input PDF and ReactionMiner JSON output
echo '###########################################'
echo '########    RUNNING ChemScraper    ########'
echo '###########################################'
if [[ -z "${SKIP_CHEMSCRAPER}" ]]; then
  python ./run_chemscraper.py
else
  echo 'SKIP_CHEMSCRAPER is set, skipping ChemScraper stage'
fi
