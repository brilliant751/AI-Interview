---
tags:
- ctranslate2
- translation
license: apache-2.0
---
# Repository General Information
## Inspired by and derived from the work of [Helsinki-NLP](https://huggingface.co/Helsinki-NLP), [CTranslate2](https://github.com/OpenNMT/CTranslate2), and [michaelfeil](https://huggingface.co/michaelfeil)!
- Link to Original Model ([Helsinki-NLP](https://huggingface.co/Helsinki-NLP)): [Model Link](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh)
- This respository was based on the work of [CTranslate2](https://github.com/OpenNMT/CTranslate2).
- This repository was based on the work of [michaelfeil](https://huggingface.co/michaelfeil).

# What is CTranslate2?
[CTranslate2](https://opennmt.net/CTranslate2/) is a C++ and Python library for efficient inference with Transformer models.

CTranslate2 implements a custom runtime that applies many performance optimization techniques such as weights quantization, layers fusion, batch reordering, etc., to accelerate and reduce the memory usage of Transformer models on CPU and GPU.

CTranslate2 is one of the most performant ways of hosting translation models at scale. Current supported models include:
- Encoder-decoder models: Transformer base/big, M2M-100, NLLB, BART, mBART, Pegasus, T5, Whisper
- Decoder-only models: GPT-2, GPT-J, GPT-NeoX, OPT, BLOOM, MPT, Llama, Mistral, Gemma, CodeGen, GPTBigCode, Falcon
- Encoder-only models: BERT, DistilBERT, XLM-RoBERTa

The project is production-oriented and comes with backward compatibility guarantees, but it also includes experimental features related to model compression and inference acceleration.

# CTranslate2 Benchmarks
Please note that the results presented below are only valid for the configuration used during this benchmark: absolute and relative performance may change with different settings. Tested against `newstest2014` (En -> De) dataset.

The benchmark reports the number of target tokens generated per second (higher is better). The results are aggregated over multiple runs. See the benchmark scripts for more details and reproduce these numbers.

Please note that the results presented below are only valid for the configuration used during this benchmark: absolute and relative performance may change with different settings.

## CPU Benchmarks for Generic Opus-MT Models
| Library | Tokens per Second | Max Memory Usage | BLEU |
| :----: | :----: | :----: | :----: |
| Transformers 4.26.1 (with PyTorch 1.13.1) | 147.3 | 2332MB | 27.90 |
| Marian 1.11.0 (int16) | 330.2 | 5901MB | 27.65 |
| Marian 1.11.0 (int8) | 355.8 | 4763MB | 27.27 |
| CTranslate2 3.6.0 (int16) | 596.1 | 660MB | 27.53 |
| CTranslate2 3.6.0 (int8) | 696.1 | 516MB | 27.65 |

## GPU Benchmarks for Generic Opus-MT Models
| Library | Tokens per Second | Max GPU Memory Usage  | Max Memory Usage | BLEU |
| :----: | :----: | :----: | :----: | :----: |
| Transformers 4.26.1 (with PyTorch 1.13.1) | 1022.9 | 4097MB | 2109MB | 27.90 |
| Marian 1.11.0 (float16) | 3962.4 | 3239MB | 1976MB | 27.94 |
| CTranslate2 3.6.0 (float16) | 9296.7 | 909MB | 814MB | 27.9 |
| CTranslate2 3.6.0 (int8 + float16) | 8362.7 | 813MB | 766MB | 27.9 |

`Executed with 4 threads on a c5.2xlarge Amazon EC2 instance equipped with an Intel(R) Xeon(R) Platinum 8275CL CPU.`

**Source to benchmark information can be found [here](https://github.com/OpenNMT/CTranslate2).**<br />
**Original model BLEU scores can be found [here](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh).**

## Internal Benchmarks
Internal testing on our end showed **inference times reduced by 6x-10x** on average compared the vanilla checkpoints using the *transformers* library. A **slight reduction on BLEU scores (~5%)** was also identified in comparison to the vanilla checkpoints with a few exceptions. This is likely due to several factors, one being the quantization applied. Further testing is needed from our end to better assess the reduction in translation quality. The command used to compile the vanilla checkpoint into a CTranslate2 model can be found below. Modifying this command can yield differing balances between inferencing performance and translation quality.


# CTranslate2 Installation
```bash
pip install hf-hub-ctranslate2>=1.0.0 ctranslate2>=3.13.0
```
### ct2-transformers-converter Command Used:
```bash
ct2-transformers-converter --model Helsinki-NLP/opus-mt-en-zh --output_dir ./ctranslate2/opus-mt-en-zh-ctranslate2 --force --copy_files README.md generation_config.json tokenizer_config.json vocab.json source.spm .gitattributes target.spm --quantization float16
```
# CTranslate2 Converted Checkpoint Information:
**Compatible With:**
- [ctranslate2](https://github.com/OpenNMT/CTranslate2)
- [hf-hub-ctranslate2](https://github.com/michaelfeil/hf-hub-ctranslate2)

**Compute Type:**
- `compute_type=int8_float16` for `device="cuda"`
- `compute_type=int8`  for `device="cpu"`

# Sample Code - ctranslate2
#### Clone the repository to the working directory or wherever you wish to store the model artifacts. ####
```bash
git clone https://huggingface.co/gaudi/opus-mt-en-zh-ctranslate2
```
#### Take the python code below and update the 'model_dir' variable to the location of the cloned repository. ####
```python
from ctranslate2 import Translator
import transformers

model_dir = "./opus-mt-en-zh-ctranslate2" # Path to model directory.
translator = Translator(
            model_path=model_dir,
            device="cuda", # cpu, cuda, or auto.
            inter_threads=1, # Maximum number of parallel translations.
            intra_threads=4, # Number of OpenMP threads per translator.
            compute_type="int8_float16", # int8 for cpu or int8_float16 for cuda.
)

tokenizer = transformers.AutoTokenizer.from_pretrained(model_dir)

source = tokenizer.convert_ids_to_tokens(tokenizer.encode("XXXXXX, XXX XX XXXXXX."))
results = translator.translate_batch([source])
target = results[0].hypotheses[0]

print(tokenizer.decode(tokenizer.convert_tokens_to_ids(target)))
```
# Sample Code - hf-hub-ctranslate2
**Derived From [michaelfeil](https://huggingface.co/michaelfeil):**
```python
from hf_hub_ctranslate2 import TranslatorCT2fromHfHub, GeneratorCT2fromHfHub
from transformers import AutoTokenizer

model_name = "gaudi/opus-mt-en-zh-ctranslate2"
model = TranslatorCT2fromHfHub(
        model_name_or_path=model_name,
        device="cuda",
        compute_type="int8_float16",
        tokenizer=AutoTokenizer.from_pretrained(model_name)
)
outputs = model.generate(
    text=["XXX XX XXX XXXXXXX XXXX?", "XX XX XXXX XX XXX!"],
)
print(outputs)
```
# License and other remarks:
License conditions are intended to be idential to [original huggingface repository](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh) by Helsinki-NLP.
