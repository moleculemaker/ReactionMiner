# 🧪 ReactionMiner V2
This is the updated version of ReactionMiner. We have updated the pdf2txt module with Grobid + s2orc for better preprocessing. We have also updated the extraction module finetuned Llama 3.1 8b with LoRA and vLLM implementation.

**Official Repository for the EMNLP 2023 Demo Paper**  
[Reaction Miner: An Integrated System for Chemical Reaction Extraction from Textual Data](https://aclanthology.org/2023.emnlp-demo.36/)

## 🛠️ Environment
To get started, install the necessary packages:
```
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```
For using the PDF-to-Text module in Reaction Miner, install the submodule:
```
git submodule update --init
```
Then follow the instructions from [s2orc](https://github.com/allenai/s2orc-doc2json?tab=readme-ov-file) to install Grobid and relevant environment setup.

## 📖 How to Use Reaction Miner
Current updated version requires two different environments. The pdf2txt module is running under the environment described in [s2orc](https://github.com/allenai/s2orc-doc2json?tab=readme-ov-file).
The rest is running under our [environment](environment.yml).
### Step 1: PDF-to-Text Conversion
Ensure Grobid server is running, then execute
```
bash pdf2text/pdf2txt.sh
```
This will process all the PDF files indicated by the defaulty directory `defaultDir` in pdf2text/config.py.

Given a PDF file, please refer to [example.py](./example.py) to run the rest of our system. It can be broken down into the following 2 steps:

### Step 2: Text Segmentation
Identifies paragraphs about chemical reactions and segments them:

```python
from segmentation.segmentor import TopicSegmentor
segmentor = TopicSegmentor()
seg_texts = segmentor.segment(paragraphs)
```

### Step 3: Reaction Extraction
Extracts structured chemical reactions from each segment:

```python
from extraction.extractor import ReactionExtractor
extractor = ReactionExtractor('8b')
reactions = extractor.extract(seg_texts)
```


## 📚 Citation
If you find Reaction Miner helpful, please kindly cite our paper:
```
@inproceedings{zhong2023reaction,
  title={Reaction Miner: An Integrated System for Chemical Reaction Extraction from Textual Data},
  author={Zhong, Ming and Ouyang, Siru and Jiao, Yizhu and Kargupta, Priyanka and Luo, Leo and Shen, Yanzhen and Zhou, Bobby and Zhong, Xianrui and Liu, Xuan and Li, Hongxiang and others},
  booktitle={Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing: System Demonstrations},
  pages={389--402},
  year={2023}
}
```
