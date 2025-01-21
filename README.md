# 🧪 ReactionMiner V2
This is the updated version of ReactionMiner. We have updated the pdf2txt module with Grobid + s2orc for better preprocessing. We have also updated the extraction module by finetuning Llama-3.1-8b with LoRA and vLLM implementation.

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

## Running in Docker
Place any input files in `./inputs`

To run Grobid + ReactionMiner using our pre-built image:
```
docker compose up -d
```

Output files will be located in `./results`

When you're done using it, shut down related services using:
```
docker compose down
```

### Running with GPU
By default, this image will not utilize a GPU if one is present

To use a GPU, uncomment the `deploy` section in `docker-compose.yml`

### Building Docker Image
To build a Docker container for ReactionMiner:
```
docker compose build
```

You can build + run the image in one step using:
```
docker compose up -d --build
```

### Running in Kubernetes
We have also included a `kubernetes/` folder that contains experimental manifests for running in a Kubernetes cluster

You will need to adjust these manifests based on your own cluster.

First, create a Secret containing your HuggingFace API Token:
```
vi kubernetes/huggingface.secret.yml
kubectl apply -f kubernetes/huggingface.secret.yml
```

**Warning: Do not commit this API token to source control**

Next, start up Grobid:
```
kubectl apply -f kubernetes/grobid.yml
```

Finally, run a ReactionMiner Job:
```
kubectl apply -f kubernetes/reactionminer.job.yml
```

This will utilize your HuggingFace API Token secret and will make requests to the Grobid server.

To run an interactive shell with ReactionMiner for testing/debugging, you can use the Pod manifest:
```
kubectl apply -f kubernetes/reactionminer.pod.yml
kubectl exec -it reactionminer -- bash
```
