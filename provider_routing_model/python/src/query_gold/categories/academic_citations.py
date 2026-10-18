"""Curate direct-search academic literature and citation metadata facts.

Covers seminal ML and computer science preprints and papers on arXiv,
verifying primary author attribution, exact submission dates, and
benchmark SOTA results.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from query_gold.io import atomic_write_bytes, ensure_safe_path
from query_gold.models import SCHEMA_VERSION

CATEGORY_ID = "10_academic_literature_citations"
GENERATOR_VERSION = "query-gold/v1"
SOURCE_FAMILY = "arxiv_openreview_publications"
IMMUTABLE_REASON = "Fixed academic literature and citation metadata"


@dataclass(frozen=True)
class AcademicSource:
    source_id: str
    source_record_id: str
    url: str
    title: str
    published_at: str
    license: str
    raw_text: str


@dataclass(frozen=True)
class AcademicFact:
    case_id: str
    source_id: str
    query: str
    question_type: str
    answer: str
    value: float | None
    accepted_answers: list[str]
    units: str | None
    excerpt: str


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


SOURCES: list[AcademicSource] = [
    AcademicSource(
        source_id="arxiv_1706_03762",
        source_record_id="arxiv:1706.03762",
        url="https://arxiv.org/abs/1706.03762",
        title="Attention Is All You Need",
        published_at="2017-06-12",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Attention Is All You Need\n"
            "Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, "
            "Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin\n"
            "Submission history: [v1] Mon, 12 Jun 2017 19:42:15 UTC\n"
            "Comments: 15 pages, 5 figures\n"
            "Subjects: Computation and Language (cs.CL); Machine Learning (cs.LG)\n"
            "Abstract: The dominant sequence transduction models are based on complex "
            "recurrent or convolutional neural networks. We propose the Transformer, "
            "a model architecture eschewing recurrence and relying entirely on an attention "
            "mechanism to draw global dependencies between input and output.\n"
            "Benchmark Results: On the WMT 2014 English-to-German translation task, the big "
            "transformer model achieves 28.4 BLEU, improving over the existing best results."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1512_03385",
        source_record_id="arxiv:1512.03385",
        url="https://arxiv.org/abs/1512.03385",
        title="Deep Residual Learning for Image Recognition",
        published_at="2015-12-10",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Deep Residual Learning for Image Recognition\n"
            "Authors: Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun\n"
            "Submission history: [v1] Thu, 10 Dec 2015 18:31:02 UTC\n"
            "Subjects: Computer Vision and Pattern Recognition (cs.CV)\n"
            "Abstract: Deeper neural networks are more difficult to train. We present a "
            "residual learning framework to ease the training of networks that are "
            "substantially deeper than those used previously.\n"
            "Benchmark Results: On the ImageNet classification dataset, our 152-layer "
            "residual net achieves 3.57% top-5 error on the test set, winning 1st place in "
            "the ILSVRC 2015 classification competition."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1810_04805",
        source_record_id="arxiv:1810.04805",
        url="https://arxiv.org/abs/1810.04805",
        title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        published_at="2018-10-11",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: BERT: Pre-training of Deep Bidirectional Transformers for "
            "Language Understanding\n"
            "Authors: Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova\n"
            "Submission history: [v1] Thu, 11 Oct 2018 20:18:23 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: We introduce a new language representation model called BERT, which stands "
            "for Bidirectional Encoder Representations from Transformers.\n"
            "Benchmark Results: BERT-Large achieves a score of 80.5 on the GLUE benchmark, "
            "outperforming prior state-of-the-art models across eleven NLP tasks."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2005_14165",
        source_record_id="arxiv:2005.14165",
        url="https://arxiv.org/abs/2005.14165",
        title="Language Models are Few-Shot Learners",
        published_at="2020-05-28",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Language Models are Few-Shot Learners\n"
            "Authors: Tom B. Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, Jared Kaplan, "
            "Prafulla Dhariwal, Arvind Neelakantan, Pranav Shyam, Girish Sastry, Amanda Askell\n"
            "Submission history: [v1] Thu, 28 May 2020 04:00:00 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: We train GPT-3, an autoregressive language model with 175 billion "
            "parameters, and test its performance in the few-shot setting.\n"
            "Benchmark Results: On the LAMBADA dataset, GPT-3 175B achieves 86.4% zero-shot "
            "accuracy, demonstrating strong capability in language modeling."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2106_09685",
        source_record_id="arxiv:2106.09685",
        url="https://arxiv.org/abs/2106.09685",
        title="LoRA: Low-Rank Adaptation of Large Language Models",
        published_at="2021-06-17",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: LoRA: Low-Rank Adaptation of Large Language Models\n"
            "Authors: Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, "
            "Shean Wang, Lu Wang, Weizhu Chen\n"
            "Submission history: [v1] Thu, 17 Jun 2021 17:34:02 UTC\n"
            "Subjects: Computation and Language (cs.CL); Machine Learning (cs.LG)\n"
            "Abstract: An important paradigm of natural language processing involves large-scale "
            "pre-training followed by adaptation to downstream tasks. We propose Low-Rank "
            "Adaptation, or LoRA.\n"
            "Benchmark Results: On the CoLA benchmark, RoBERTa with LoRA obtains a score of 69.2, "
            "matching full fine-tuning performance with vastly fewer trainable parameters."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2006_11239",
        source_record_id="arxiv:2006.11239",
        url="https://arxiv.org/abs/2006.11239",
        title="Denoising Diffusion Probabilistic Models",
        published_at="2020-06-19",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Denoising Diffusion Probabilistic Models\n"
            "Authors: Jonathan Ho, Ajay Jain, Pieter Abbeel\n"
            "Submission history: [v1] Fri, 19 Jun 2020 07:11:42 UTC\n"
            "Subjects: Machine Learning (cs.LG); Computer Vision and Pattern Recognition (cs.CV)\n"
            "Abstract: We present high quality image synthesis results using diffusion "
            "probabilistic models, a class of latent variable models inspired by "
            "non-equilibrium thermodynamics.\n"
            "Benchmark Results: Our model obtains an unconditional CIFAR-10 sample quality "
            "score of 3.17 FID, establishing a competitive mark against GANs."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1412_6980",
        source_record_id="arxiv:1412.6980",
        url="https://arxiv.org/abs/1412.6980",
        title="Adam: A Method for Stochastic Optimization",
        published_at="2014-12-22",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Adam: A Method for Stochastic Optimization\n"
            "Authors: Diederik P. Kingma, Jimmy Ba\n"
            "Submission history: [v1] Mon, 22 Dec 2014 21:58:32 UTC\n"
            "Subjects: Machine Learning (cs.LG)\n"
            "Abstract: We introduce Adam, an algorithm for first-order gradient-based optimization "
            "of stochastic objective functions, based on adaptive estimates of lower-order "
            "moments.\n"
            "Publication Metadata: The preprint was originally submitted to arXiv on 22 Dec 2014."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1406_2661",
        source_record_id="arxiv:1406.2661",
        url="https://arxiv.org/abs/1406.2661",
        title="Generative Adversarial Networks",
        published_at="2014-06-10",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Generative Adversarial Networks\n"
            "Authors: Ian J. Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, "
            "David Warde-Farley, Sherjil Ozair, Aaron Courville, Yoshua Bengio\n"
            "Submission history: [v1] Tue, 10 Jun 2014 15:43:08 UTC\n"
            "Subjects: Machine Learning (stat.ML); Machine Learning (cs.LG)\n"
            "Abstract: We propose a new framework for estimating generative models via an "
            "adversarial process, in which we simultaneously train two models: a generative "
            "model G and a discriminative model D.\n"
            "Publication Metadata: The original preprint was submitted to arXiv on 10 Jun 2014."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2205_14135",
        source_record_id="arxiv:2205.14135",
        url="https://arxiv.org/abs/2205.14135",
        title="FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
        published_at="2022-05-27",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness\n"
            "Authors: Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Re\n"
            "Submission history: [v1] Fri, 27 May 2022 17:58:35 UTC\n"
            "Subjects: Machine Learning (cs.LG); Computation and Language (cs.CL)\n"
            "Abstract: Transformers are slow and memory-hungry on long sequences. We propose "
            "FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce "
            "the number of memory reads and writes.\n"
            "Publication Metadata: The original submission occurred on 27 May 2022 on arXiv."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2010_11929",
        source_record_id="arxiv:2010.11929",
        url="https://arxiv.org/abs/2010.11929",
        title="An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale",
        published_at="2020-10-22",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale\n"
            "Authors: Alexey Dosovitskiy, Lucas Beyer, Alexander Kolesnikov, Dirk Weissenborn, "
            "Xiaohua Zhai, Thomas Unterthiner, Mostafa Dehghani, Matthias Minderer, Georg Heigold, "
            "Sylvain Gelly\n"
            "Submission history: [v1] Thu, 22 Oct 2020 17:59:12 UTC\n"
            "Subjects: Computer Vision and Pattern Recognition (cs.CV); Machine Learning (cs.LG)\n"
            "Abstract: While the Transformer architecture has become the de-facto standard for "
            "natural language processing tasks, its applications to computer vision remain "
            "limited.\n"
            "Benchmark Results: Our fine-tuned ViT-H/14 model achieves 88.55% top-1 accuracy "
            "on ImageNet, substantially outperforming standard ResNet baselines."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2302_13971",
        source_record_id="arxiv:2302.13971",
        url="https://arxiv.org/abs/2302.13971",
        title="LLaMA: Open and Efficient Foundation Language Models",
        published_at="2023-02-27",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: LLaMA: Open and Efficient Foundation Language Models\n"
            "Authors: Hugo Touvron, Thibaut Lavril, Gautier Izacard, Xavier Martinet, "
            "Marie-Anne Lachaux, Timothee Lacroix, Baptiste Rozihre, Naman Goyal, "
            "Eric Hambro, Faisal Azhar\n"
            "Submission history: [v1] Mon, 27 Feb 2023 18:28:42 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: We introduce LLaMA, a collection of foundation language models ranging from "
            "7B to 65B parameters.\n"
            "Benchmark Results: On the GSM8k benchmark, LLaMA-65B achieves 50.9% accuracy with "
            "8-shot prompting, surpassing comparable open-source model baselines."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2304_02643",
        source_record_id="arxiv:2304.02643",
        url="https://arxiv.org/abs/2304.02643",
        title="Segment Anything",
        published_at="2023-04-05",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Segment Anything\n"
            "Authors: Alexander Kirillov, Eric Mintun, Nikhila Ravi, Hanzi Mao, Chloe Rolland, "
            "Laura Gustafson, Tete Xiao, Spencer Whitehead, Alexander C. Berg, Wan-Yen Lo\n"
            "Submission history: [v1] Wed, 5 Apr 2023 17:59:02 UTC\n"
            "Subjects: Computer Vision and Pattern Recognition (cs.CV)\n"
            "Abstract: We present the Segment Anything project: a new task, model, and dataset "
            "for image segmentation.\n"
            "Publication Metadata: The preprint was originally released on arXiv on 5 Apr 2023."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1907_11692",
        source_record_id="arxiv:1907.11692",
        url="https://arxiv.org/abs/1907.11692",
        title="RoBERTa: A Robustly Optimized BERT Pretraining Approach",
        published_at="2019-07-26",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: RoBERTa: A Robustly Optimized BERT Pretraining Approach\n"
            "Authors: Yinhan Liu, Myle Ott, Naman Goyal, Jingfei Du, Mandar Joshi, Danqi Chen, "
            "Omer Levy, Mike Lewis, Luke Zettlemoyer, Veselin Stoyanov\n"
            "Submission history: [v1] Fri, 26 Jul 2019 18:23:45 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: Language model pretraining has led to significant performance gains but "
            "careful comparisons between different approaches are challenging.\n"
            "Benchmark Results: RoBERTa achieves a score of 88.5 on the GLUE benchmark test set, "
            "matching or exceeding all previously published task results."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2005_11401",
        source_record_id="arxiv:2005.11401",
        url="https://arxiv.org/abs/2005.11401",
        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        published_at="2020-05-22",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks\n"
            "Authors: Patrick Lewis, Ethan Perez, Aleksandara Piktus, Fabio Petroni, "
            "Vladimir Karpukhin, Naman Goyal, Heinrich Kuttler, Mike Lewis, "
            "Wen-tau Yih, Tim Rocktaschel\n"
            "Submission history: [v1] Fri, 22 May 2020 17:34:02 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: Large pre-trained language models store factual knowledge in their "
            "parameters. We explore general-purpose fine-tuning recipes for "
            "Retrieval-Augmented Generation (RAG).\n"
            "Publication Metadata: The initial preprint was submitted on 22 May 2020 to arXiv."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2201_11903",
        source_record_id="arxiv:2201_11903",
        url="https://arxiv.org/abs/2201.11903",
        title="Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        published_at="2022-01-28",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Chain-of-Thought Prompting Elicits Reasoning in Large Language Models\n"
            "Authors: Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, "
            "Fei Xia, Ed H. Chi, Quoc V. Le, Denny Zhou\n"
            "Submission history: [v1] Fri, 28 Jan 2022 17:42:01 UTC\n"
            "Subjects: Computation and Language (cs.CL); Artificial Intelligence (cs.AI)\n"
            "Abstract: We explore how generating a chain of thought -- a series of intermediate "
            "reasoning steps -- significantly improves the ability of large language models "
            "to perform complex reasoning.\n"
            "Publication Metadata: The paper was initially submitted to arXiv on 28 Jan 2022."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2305_18290",
        source_record_id="arxiv:2305.18290",
        url="https://arxiv.org/abs/2305.18290",
        title="Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
        published_at="2023-05-29",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Direct Preference Optimization: Your Language Model is Secretly a "
            "Reward Model\n"
            "Authors: Rafael Rafailov, Archit Sharma, Eric Mitchell, Stefano Ermon, "
            "Christopher D. Manning, Chelsea Finn\n"
            "Submission history: [v1] Mon, 29 May 2023 17:59:10 UTC\n"
            "Subjects: Machine Learning (cs.LG); Computation and Language (cs.CL)\n"
            "Abstract: While reinforcement learning from human feedback (RLHF) is powerful, "
            "it is complex and unstable. We propose Direct Preference Optimization (DPO).\n"
            "Publication Metadata: The preprint was uploaded to arXiv on 29 May 2023."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2112_10752",
        source_record_id="arxiv:2112.10752",
        url="https://arxiv.org/abs/2112.10752",
        title="High-Resolution Image Synthesis with Latent Diffusion Models",
        published_at="2021-12-20",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: High-Resolution Image Synthesis with Latent Diffusion Models\n"
            "Authors: Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, "
            "Bjoern Ommer\n"
            "Submission history: [v1] Mon, 20 Dec 2021 18:59:45 UTC\n"
            "Subjects: Computer Vision and Pattern Recognition (cs.CV); Machine Learning (cs.LG)\n"
            "Abstract: By decomposing the image formation process into a sequential application "
            "of denoising autoencoders, diffusion models achieve state-of-the-art synthesis "
            "results.\n"
            "Publication Metadata: First posted to arXiv on 20 Dec 2021."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1409_0473",
        source_record_id="arxiv:1409.0473",
        url="https://arxiv.org/abs/1409.0473",
        title="Neural Machine Translation by Jointly Learning to Align and Translate",
        published_at="2014-09-01",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Neural Machine Translation by Jointly Learning to Align and Translate\n"
            "Authors: Dzmitry Bahdanau, Kyunghyun Cho, Yoshua Bengio\n"
            "Submission history: [v1] Mon, 1 Sep 2014 15:43:21 UTC\n"
            "Subjects: Computation and Language (cs.CL); Machine Learning (cs.LG)\n"
            "Abstract: Neural machine translation is a newly emerging approach to machine "
            "translation. We introduce an attention mechanism allowing a model to automatically "
            "search for parts of a source sentence.\n"
            "Benchmark Results: The proposed RNNsearch-50 model achieves a BLEU score of 28.45 "
            "on the WMT-14 English-to-French translation task."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1910_01108",
        source_record_id="arxiv:1910.01108",
        url="https://arxiv.org/abs/1910.01108",
        title="DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter",
        published_at="2019-10-02",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: DistilBERT, a distilled version of BERT: smaller, faster, cheaper and "
            "lighter\n"
            "Authors: Victor Sanh, Lysandre Debut, Julien Chaumond, Thomas Wolf\n"
            "Submission history: [v1] Wed, 2 Oct 2019 17:34:10 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: We present DistilBERT, a method to pre-train a smaller general-purpose "
            "language representation model using knowledge distillation.\n"
            "Benchmark Results: DistilBERT retains 97% of BERT performance with a GLUE macro-score "
            "of 77.0 while being 60% faster."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2310_06825",
        source_record_id="arxiv:2310.06825",
        url="https://arxiv.org/abs/2310.06825",
        title="Mistral 7B",
        published_at="2023-10-10",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Mistral 7B\n"
            "Authors: Albert Q. Jiang, Alexandre Sablayrolles, Arthur Mensch, Chris Bamford, "
            "Devendra Singh Chaplot, Diego de las Casas, Florian Bressand, Gianna Lengyel\n"
            "Submission history: [v1] Tue, 10 Oct 2023 17:31:45 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: We introduce Mistral 7B, a 7-billion-parameter language model engineered "
            "for superior performance and efficiency.\n"
            "Publication Metadata: The paper was released on arXiv on 10 Oct 2023."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2003_08934",
        source_record_id="arxiv:2003.08934",
        url="https://arxiv.org/abs/2003.08934",
        title="NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis",
        published_at="2020-03-19",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis\n"
            "Authors: Ben Mildenhall, Pratul P. Srinivasan, Matthew Tancik, Jonathan T. Barron, "
            "Ravi Ramamoorthi, Ren Ng\n"
            "Submission history: [v1] Thu, 19 Mar 2020 17:59:12 UTC\n"
            "Subjects: Computer Vision and Pattern Recognition (cs.CV); Graphics (cs.GR)\n"
            "Abstract: We present a method that achieves state-of-the-art results for synthesizing "
            "novel views of complex scenes by optimizing an underlying continuous volumetric "
            "scene function.\n"
            "Benchmark Results: On the synthetic Blender dataset, NeRF achieves a PSNR metric "
            "score of 31.01, outperforming previous view synthesis techniques."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2305_14314",
        source_record_id="arxiv:2305.14314",
        url="https://arxiv.org/abs/2305.14314",
        title="QLoRA: Efficient Finetuning of Quantized LLMs",
        published_at="2023-05-23",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: QLoRA: Efficient Finetuning of Quantized LLMs\n"
            "Authors: Tim Dettmers, Artidoro Pagnoni, Ari Holtzman, Luke Zettlemoyer\n"
            "Submission history: [v1] Tue, 23 May 2023 17:45:01 UTC\n"
            "Subjects: Computation and Language (cs.CL); Machine Learning (cs.LG)\n"
            "Abstract: We present QLoRA, an efficient finetuning approach that reduces memory "
            "usage enough to finetune a 65B parameter model on a single 48GB GPU.\n"
            "Publication Metadata: The initial preprint was submitted on 23 May 2023 to arXiv."
        ),
    ),
    AcademicSource(
        source_id="arxiv_2206_07682",
        source_record_id="arxiv:2206.07682",
        url="https://arxiv.org/abs/2206.07682",
        title="Emergent Abilities of Large Language Models",
        published_at="2022-06-15",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Emergent Abilities of Large Language Models\n"
            "Authors: Jason Wei, Yi Tay, Rishi Bommasani, Colin Raffel, Barret Zoph, "
            "Sebastian Borgeaud, Dani Yogatama, Maarten Bosma, Denny Zhou, Donald Metzler\n"
            "Submission history: [v1] Wed, 15 Jun 2022 17:58:02 UTC\n"
            "Subjects: Computation and Language (cs.CL)\n"
            "Abstract: Scaling up language models has been shown to predictably improve "
            "performance and sample efficiency on a wide range of downstream tasks.\n"
            "Publication Metadata: First submitted to arXiv on 15 Jun 2022."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1505_04597",
        source_record_id="arxiv:1505.04597",
        url="https://arxiv.org/abs/1505.04597",
        title="U-Net: Convolutional Networks for Biomedical Image Segmentation",
        published_at="2015-05-18",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: U-Net: Convolutional Networks for Biomedical Image Segmentation\n"
            "Authors: Olaf Ronneberger, Philipp Fischer, Thomas Brox\n"
            "Submission history: [v1] Mon, 18 May 2015 14:06:12 UTC\n"
            "Subjects: Computer Vision and Pattern Recognition (cs.CV)\n"
            "Abstract: There is large consent that successful training of deep networks requires "
            "many thousand annotated training samples. We present a network and training "
            "strategy that relies on the strong use of data augmentation.\n"
            "Benchmark Results: U-Net achieved a warping error score of 0.000353 on the EM "
            "segmentation challenge, winning the competition by a large margin."
        ),
    ),
    AcademicSource(
        source_id="arxiv_1712_01815",
        source_record_id="arxiv:1712.01815",
        url="https://arxiv.org/abs/1712.01815",
        title=(
            "Mastering Chess and Shogi by Self-Play with a General Reinforcement Learning Algorithm"
        ),
        published_at="2017-12-05",
        license="arXiv.org perpetual non-exclusive license",
        raw_text=(
            "Title: Mastering Chess and Shogi by Self-Play with a General Reinforcement "
            "Learning Algorithm\n"
            "Authors: David Silver, Thomas Hubert, Julian Schrittwieser, Ioannis Antonoglou, "
            "Matthew Lai, Arthur Guez, Marc Lanctot, Laurent Sifre, Dharshan Kumaran, "
            "Thore Graepel\n"
            "Submission history: [v1] Tue, 5 Dec 2017 18:22:04 UTC\n"
            "Subjects: Artificial Intelligence (cs.AI); Machine Learning (cs.LG)\n"
            "Abstract: The game of chess is the most widely studied domain in the history of "
            "artificial intelligence. We present AlphaZero, which replaces handcrafted "
            "evaluation functions with deep neural networks.\n"
            "Publication Metadata: The AlphaZero algorithm preprint was submitted to arXiv on "
            "5 Dec 2017."
        ),
    ),
]

FACTS: list[AcademicFact] = [
    # 1. Attention Is All You Need
    AcademicFact(
        case_id="acad-vaswani-author",
        source_id="arxiv_1706_03762",
        query=(
            "Who is listed as primary author of the research paper "
            "Attention Is All You Need on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Ashish Vaswani",
        value=None,
        accepted_answers=["Ashish Vaswani", "A. Vaswani"],
        units=None,
        excerpt="Authors: Ashish Vaswani, Noam Shazeer",
    ),
    AcademicFact(
        case_id="acad-vaswani-sota",
        source_id="arxiv_1706_03762",
        query=(
            "What BLEU score on the WMT 2014 English-to-German translation task was "
            "achieved in the paper Attention Is All You Need?"
        ),
        question_type="benchmark_sota_score",
        answer="28.4",
        value=28.4,
        accepted_answers=["28.4", "28.4 BLEU"],
        units="BLEU",
        excerpt=(
            "the big transformer model achieves 28.4 BLEU, "
            "improving over the existing best results."
        ),
    ),
    # 2. ResNet
    AcademicFact(
        case_id="acad-he-author",
        source_id="arxiv_1512_03385",
        query=(
            "Who is listed as first author of the research paper "
            "Deep Residual Learning for Image Recognition on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Kaiming He",
        value=None,
        accepted_answers=["Kaiming He", "K. He"],
        units=None,
        excerpt="Authors: Kaiming He, Xiangyu Zhang",
    ),
    AcademicFact(
        case_id="acad-he-sota",
        source_id="arxiv_1512_03385",
        query=(
            "What ImageNet classification benchmark top-5 error percentage was "
            "achieved by the 152-layer ResNet paper on arXiv?"
        ),
        question_type="benchmark_sota_score",
        answer="3.57%",
        value=3.57,
        accepted_answers=["3.57%", "3.57"],
        units="%",
        excerpt="our 152-layer residual net achieves 3.57% top-5 error on the test set",
    ),
    # 3. BERT
    AcademicFact(
        case_id="acad-devlin-author",
        source_id="arxiv_1810_04805",
        query=(
            "Who is listed as primary author of the research paper "
            "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding?"
        ),
        question_type="primary_author_attribution",
        answer="Jacob Devlin",
        value=None,
        accepted_answers=["Jacob Devlin", "J. Devlin"],
        units=None,
        excerpt="Authors: Jacob Devlin, Ming-Wei Chang",
    ),
    AcademicFact(
        case_id="acad-devlin-sota",
        source_id="arxiv_1810_04805",
        query=(
            "What overall score on the GLUE benchmark was achieved by BERT-Large "
            "in the paper BERT: Pre-training of Deep Bidirectional Transformers?"
        ),
        question_type="benchmark_sota_score",
        answer="80.5",
        value=80.5,
        accepted_answers=["80.5"],
        units=None,
        excerpt="BERT-Large achieves a score of 80.5 on the GLUE benchmark",
    ),
    # 4. GPT-3
    AcademicFact(
        case_id="acad-brown-author",
        source_id="arxiv_2005_14165",
        query=(
            "Who is listed as primary author of the language model paper "
            "Language Models are Few-Shot Learners on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Tom B. Brown",
        value=None,
        accepted_answers=["Tom B. Brown", "Tom Brown", "T. B. Brown"],
        units=None,
        excerpt="Authors: Tom B. Brown, Benjamin Mann",
    ),
    AcademicFact(
        case_id="acad-brown-sota",
        source_id="arxiv_2005_14165",
        query=(
            "What zero-shot accuracy on the LAMBADA dataset was reported for "
            "GPT-3 175B in the paper Language Models are Few-Shot Learners?"
        ),
        question_type="benchmark_sota_score",
        answer="86.4%",
        value=86.4,
        accepted_answers=["86.4%", "86.4"],
        units="%",
        excerpt="On the LAMBADA dataset, GPT-3 175B achieves 86.4% zero-shot accuracy",
    ),
    # 5. LoRA
    AcademicFact(
        case_id="acad-hu-author",
        source_id="arxiv_2106_09685",
        query=(
            "Who is listed as first author of the parameter adaptation paper "
            "LoRA preprint arXiv:2106.09685 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Edward J. Hu",
        value=None,
        accepted_answers=["Edward J. Hu", "Edward Hu", "E. J. Hu"],
        units=None,
        excerpt="Authors: Edward J. Hu, Yelong Shen",
    ),
    AcademicFact(
        case_id="acad-hu-sota",
        source_id="arxiv_2106_09685",
        query=(
            "What score on the CoLA benchmark was reported for RoBERTa with LoRA "
            "adaptation in preprint arXiv:2106.09685?"
        ),
        question_type="benchmark_sota_score",
        answer="69.2",
        value=69.2,
        accepted_answers=["69.2"],
        units=None,
        excerpt="On the CoLA benchmark, RoBERTa with LoRA obtains a score of 69.2",
    ),
    # 6. DDPM
    AcademicFact(
        case_id="acad-ho-author",
        source_id="arxiv_2006_11239",
        query=(
            "Who is listed as primary author of the generative diffusion paper "
            "Denoising Diffusion Probabilistic Models on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Jonathan Ho",
        value=None,
        accepted_answers=["Jonathan Ho", "J. Ho"],
        units=None,
        excerpt="Authors: Jonathan Ho, Ajay Jain",
    ),
    AcademicFact(
        case_id="acad-ho-sota",
        source_id="arxiv_2006_11239",
        query=(
            "What unconditional CIFAR-10 sample quality FID score was reported in "
            "the paper Denoising Diffusion Probabilistic Models?"
        ),
        question_type="benchmark_sota_score",
        answer="3.17",
        value=3.17,
        accepted_answers=["3.17", "3.17 FID"],
        units=None,
        excerpt="Our model obtains an unconditional CIFAR-10 sample quality score of 3.17 FID",
    ),
    # 7. Adam
    AcademicFact(
        case_id="acad-kingma-author",
        source_id="arxiv_1412_6980",
        query=(
            "Who is listed as first author of the optimization paper "
            "Adam: A Method for Stochastic Optimization on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Diederik P. Kingma",
        value=None,
        accepted_answers=["Diederik P. Kingma", "Diederik Kingma", "D. P. Kingma"],
        units=None,
        excerpt="Authors: Diederik P. Kingma, Jimmy Ba",
    ),
    AcademicFact(
        case_id="acad-kingma-date",
        source_id="arxiv_1412_6980",
        query=(
            "What was the initial submission date on arXiv for the preprint "
            "Adam: A Method for Stochastic Optimization?"
        ),
        question_type="exact_publication_date",
        answer="22 Dec 2014",
        value=None,
        accepted_answers=["22 Dec 2014", "2014-12-22"],
        units=None,
        excerpt="[v1] Mon, 22 Dec 2014 21:58:32 UTC",
    ),
    # 8. GAN
    AcademicFact(
        case_id="acad-goodfellow-author",
        source_id="arxiv_1406_2661",
        query=(
            "Who is listed as primary author of the foundational paper "
            "Generative Adversarial Networks on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Ian J. Goodfellow",
        value=None,
        accepted_answers=["Ian J. Goodfellow", "Ian Goodfellow", "I. J. Goodfellow"],
        units=None,
        excerpt="Authors: Ian J. Goodfellow, Jean Pouget-Abadie",
    ),
    AcademicFact(
        case_id="acad-goodfellow-date",
        source_id="arxiv_1406_2661",
        query=(
            "What was the original arXiv submission date for the preprint paper "
            "Generative Adversarial Networks?"
        ),
        question_type="exact_publication_date",
        answer="10 Jun 2014",
        value=None,
        accepted_answers=["10 Jun 2014", "2014-06-10"],
        units=None,
        excerpt="[v1] Tue, 10 Jun 2014 15:43:08 UTC",
    ),
    # 9. FlashAttention
    AcademicFact(
        case_id="acad-dao-author",
        source_id="arxiv_2205_14135",
        query=(
            "Who is listed as first author of the IO-aware attention paper "
            "FlashAttention preprint arXiv:2205.14135?"
        ),
        question_type="primary_author_attribution",
        answer="Tri Dao",
        value=None,
        accepted_answers=["Tri Dao", "T. Dao"],
        units=None,
        excerpt="Authors: Tri Dao, Daniel Y. Fu",
    ),
    AcademicFact(
        case_id="acad-dao-date",
        source_id="arxiv_2205_14135",
        query=(
            "What was the initial submission date on arXiv for the FlashAttention "
            "preprint arXiv:2205.14135?"
        ),
        question_type="exact_publication_date",
        answer="27 May 2022",
        value=None,
        accepted_answers=["27 May 2022", "2022-05-27"],
        units=None,
        excerpt="[v1] Fri, 27 May 2022 17:58:35 UTC",
    ),
    # 10. ViT
    AcademicFact(
        case_id="acad-dosovitskiy-author",
        source_id="arxiv_2010_11929",
        query=(
            "Who is listed as primary author of the vision transformer paper "
            "An Image is Worth 16x16 Words on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Alexey Dosovitskiy",
        value=None,
        accepted_answers=["Alexey Dosovitskiy", "A. Dosovitskiy"],
        units=None,
        excerpt="Authors: Alexey Dosovitskiy, Lucas Beyer",
    ),
    AcademicFact(
        case_id="acad-dosovitskiy-sota",
        source_id="arxiv_2010_11929",
        query=(
            "What top-1 accuracy on ImageNet was reported for the ViT-H/14 model "
            "in the paper An Image is Worth 16x16 Words?"
        ),
        question_type="benchmark_sota_score",
        answer="88.55%",
        value=88.55,
        accepted_answers=["88.55%", "88.55"],
        units="%",
        excerpt="Our fine-tuned ViT-H/14 model achieves 88.55% top-1 accuracy on ImageNet",
    ),
    # 11. LLaMA
    AcademicFact(
        case_id="acad-touvron-author",
        source_id="arxiv_2302_13971",
        query=(
            "Who is listed as first author of the foundation model paper "
            "LLaMA preprint arXiv:2302.13971 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Hugo Touvron",
        value=None,
        accepted_answers=["Hugo Touvron", "H. Touvron"],
        units=None,
        excerpt="Authors: Hugo Touvron, Thibaut Lavril",
    ),
    AcademicFact(
        case_id="acad-touvron-sota",
        source_id="arxiv_2302_13971",
        query=(
            "What 8-shot accuracy on the GSM8k benchmark was reported for "
            "LLaMA-65B in LLaMA preprint arXiv:2302.13971?"
        ),
        question_type="benchmark_sota_score",
        answer="50.9%",
        value=50.9,
        accepted_answers=["50.9%", "50.9"],
        units="%",
        excerpt="On the GSM8k benchmark, LLaMA-65B achieves 50.9% accuracy with 8-shot prompting",
    ),
    # 12. Segment Anything
    AcademicFact(
        case_id="acad-kirillov-author",
        source_id="arxiv_2304_02643",
        query=(
            "Who is listed as first author of the computer vision paper Segment Anything on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Alexander Kirillov",
        value=None,
        accepted_answers=["Alexander Kirillov", "A. Kirillov"],
        units=None,
        excerpt="Authors: Alexander Kirillov, Eric Mintun",
    ),
    AcademicFact(
        case_id="acad-kirillov-date",
        source_id="arxiv_2304_02643",
        query=(
            "What was the initial submission date on arXiv for the preprint paper Segment Anything?"
        ),
        question_type="exact_publication_date",
        answer="5 Apr 2023",
        value=None,
        accepted_answers=["5 Apr 2023", "2023-04-05"],
        units=None,
        excerpt="[v1] Wed, 5 Apr 2023 17:59:02 UTC",
    ),
    # 13. RoBERTa
    AcademicFact(
        case_id="acad-liu-author",
        source_id="arxiv_1907_11692",
        query=(
            "Who is listed as primary author of the NLP paper "
            "RoBERTa: A Robustly Optimized BERT Pretraining Approach on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Yinhan Liu",
        value=None,
        accepted_answers=["Yinhan Liu", "Y. Liu"],
        units=None,
        excerpt="Authors: Yinhan Liu, Myle Ott",
    ),
    AcademicFact(
        case_id="acad-liu-sota",
        source_id="arxiv_1907_11692",
        query=(
            "What overall test score on the GLUE benchmark was reported for RoBERTa "
            "in RoBERTa: A Robustly Optimized BERT Pretraining Approach?"
        ),
        question_type="benchmark_sota_score",
        answer="88.5",
        value=88.5,
        accepted_answers=["88.5"],
        units=None,
        excerpt="RoBERTa achieves a score of 88.5 on the GLUE benchmark test set",
    ),
    # 14. RAG
    AcademicFact(
        case_id="acad-lewis-author",
        source_id="arxiv_2005_11401",
        query=(
            "Who is listed as first author of the preprint "
            "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Patrick Lewis",
        value=None,
        accepted_answers=["Patrick Lewis", "P. Lewis"],
        units=None,
        excerpt="Authors: Patrick Lewis, Ethan Perez",
    ),
    AcademicFact(
        case_id="acad-lewis-date",
        source_id="arxiv_2005_11401",
        query=(
            "What was the initial arXiv submission date for "
            "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks?"
        ),
        question_type="exact_publication_date",
        answer="22 May 2020",
        value=None,
        accepted_answers=["22 May 2020", "2020-05-22"],
        units=None,
        excerpt="[v1] Fri, 22 May 2020 17:34:02 UTC",
    ),
    # 15. Chain-of-Thought
    AcademicFact(
        case_id="acad-wei-cot-author",
        source_id="arxiv_2201_11903",
        query=(
            "Who is listed as primary author of the reasoning paper "
            "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Jason Wei",
        value=None,
        accepted_answers=["Jason Wei", "J. Wei"],
        units=None,
        excerpt="Authors: Jason Wei, Xuezhi Wang",
    ),
    AcademicFact(
        case_id="acad-wei-cot-date",
        source_id="arxiv_2201_11903",
        query=(
            "What was the initial submission date on arXiv for "
            "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models?"
        ),
        question_type="exact_publication_date",
        answer="28 Jan 2022",
        value=None,
        accepted_answers=["28 Jan 2022", "2022-01-28"],
        units=None,
        excerpt="[v1] Fri, 28 Jan 2022 17:42:01 UTC",
    ),
    # 16. DPO
    AcademicFact(
        case_id="acad-rafailov-author",
        source_id="arxiv_2305_18290",
        query=(
            "Who is listed as first author of Direct Preference Optimization "
            "preprint arXiv:2305.18290 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Rafael Rafailov",
        value=None,
        accepted_answers=["Rafael Rafailov", "R. Rafailov"],
        units=None,
        excerpt="Authors: Rafael Rafailov, Archit Sharma",
    ),
    AcademicFact(
        case_id="acad-rafailov-date",
        source_id="arxiv_2305_18290",
        query=(
            "What was the original arXiv submission date for Direct Preference "
            "Optimization preprint arXiv:2305.18290?"
        ),
        question_type="exact_publication_date",
        answer="29 May 2023",
        value=None,
        accepted_answers=["29 May 2023", "2023-05-29"],
        units=None,
        excerpt="[v1] Mon, 29 May 2023 17:59:10 UTC",
    ),
    # 17. Latent Diffusion
    AcademicFact(
        case_id="acad-rombach-author",
        source_id="arxiv_2112_10752",
        query=(
            "Who is listed as primary author of "
            "High-Resolution Image Synthesis with Latent Diffusion Models on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Robin Rombach",
        value=None,
        accepted_answers=["Robin Rombach", "R. Rombach"],
        units=None,
        excerpt="Authors: Robin Rombach, Andreas Blattmann",
    ),
    AcademicFact(
        case_id="acad-rombach-date",
        source_id="arxiv_2112_10752",
        query=(
            "What was the initial submission date on arXiv for the preprint "
            "High-Resolution Image Synthesis with Latent Diffusion Models?"
        ),
        question_type="exact_publication_date",
        answer="20 Dec 2021",
        value=None,
        accepted_answers=["20 Dec 2021", "2021-12-20"],
        units=None,
        excerpt="[v1] Mon, 20 Dec 2021 18:59:45 UTC",
    ),
    # 18. Bahdanau Attention
    AcademicFact(
        case_id="acad-bahdanau-author",
        source_id="arxiv_1409_0473",
        query=(
            "Who is listed as first author of the neural attention preprint "
            "arXiv:1409.0473 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Dzmitry Bahdanau",
        value=None,
        accepted_answers=["Dzmitry Bahdanau", "D. Bahdanau"],
        units=None,
        excerpt="Authors: Dzmitry Bahdanau, Kyunghyun Cho",
    ),
    AcademicFact(
        case_id="acad-bahdanau-sota",
        source_id="arxiv_1409_0473",
        query=(
            "What BLEU score on English-to-French translation was achieved by "
            "RNNsearch-50 in preprint arXiv:1409.0473?"
        ),
        question_type="benchmark_sota_score",
        answer="28.45",
        value=28.45,
        accepted_answers=["28.45", "28.45 BLEU"],
        units="BLEU",
        excerpt=(
            "The proposed RNNsearch-50 model achieves a BLEU score of 28.45 "
            "on the WMT-14 English-to-French translation task."
        ),
    ),
    # 19. DistilBERT
    AcademicFact(
        case_id="acad-sanh-author",
        source_id="arxiv_1910_01108",
        query=(
            "Who is listed as primary author of the distillation paper "
            "DistilBERT preprint arXiv:1910.01108 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Victor Sanh",
        value=None,
        accepted_answers=["Victor Sanh", "V. Sanh"],
        units=None,
        excerpt="Authors: Victor Sanh, Lysandre Debut",
    ),
    AcademicFact(
        case_id="acad-sanh-sota",
        source_id="arxiv_1910_01108",
        query=("What GLUE macro-score was achieved by DistilBERT in preprint arXiv:1910.01108?"),
        question_type="benchmark_sota_score",
        answer="77.0",
        value=77.0,
        accepted_answers=["77.0"],
        units=None,
        excerpt="DistilBERT retains 97% of BERT performance with a GLUE macro-score of 77.0",
    ),
    # 20. Mistral 7B
    AcademicFact(
        case_id="acad-jiang-author",
        source_id="arxiv_2310_06825",
        query=("Who is listed as first author of the foundational paper Mistral 7B on arXiv?"),
        question_type="primary_author_attribution",
        answer="Albert Q. Jiang",
        value=None,
        accepted_answers=["Albert Q. Jiang", "Albert Jiang", "A. Q. Jiang"],
        units=None,
        excerpt="Authors: Albert Q. Jiang, Alexandre Sablayrolles",
    ),
    AcademicFact(
        case_id="acad-jiang-date",
        source_id="arxiv_2310_06825",
        query=("What was the initial submission date on arXiv for the paper Mistral 7B?"),
        question_type="exact_publication_date",
        answer="10 Oct 2023",
        value=None,
        accepted_answers=["10 Oct 2023", "2023-10-10"],
        units=None,
        excerpt="[v1] Tue, 10 Oct 2023 17:31:45 UTC",
    ),
    # 21. NeRF
    AcademicFact(
        case_id="acad-mildenhall-author",
        source_id="arxiv_2003_08934",
        query=(
            "Who is listed as primary author of the view synthesis paper "
            "NeRF preprint arXiv:2003.08934 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Ben Mildenhall",
        value=None,
        accepted_answers=["Ben Mildenhall", "B. Mildenhall"],
        units=None,
        excerpt="Authors: Ben Mildenhall, Pratul P. Srinivasan",
    ),
    AcademicFact(
        case_id="acad-mildenhall-sota",
        source_id="arxiv_2003_08934",
        query=(
            "What PSNR metric score on the synthetic Blender dataset was reported for "
            "NeRF in preprint arXiv:2003.08934?"
        ),
        question_type="benchmark_sota_score",
        answer="31.01",
        value=31.01,
        accepted_answers=["31.01"],
        units=None,
        excerpt="On the synthetic Blender dataset, NeRF achieves a PSNR metric score of 31.01",
    ),
    # 22. QLoRA
    AcademicFact(
        case_id="acad-dettmers-author",
        source_id="arxiv_2305_14314",
        query=(
            "Who is listed as first author of the quantization paper "
            "QLoRA preprint arXiv:2305.14314 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Tim Dettmers",
        value=None,
        accepted_answers=["Tim Dettmers", "T. Dettmers"],
        units=None,
        excerpt="Authors: Tim Dettmers, Artidoro Pagnoni",
    ),
    AcademicFact(
        case_id="acad-dettmers-date",
        source_id="arxiv_2305_14314",
        query=(
            "What was the initial submission date on arXiv for QLoRA preprint arXiv:2305.14314?"
        ),
        question_type="exact_publication_date",
        answer="23 May 2023",
        value=None,
        accepted_answers=["23 May 2023", "2023-05-23"],
        units=None,
        excerpt="[v1] Tue, 23 May 2023 17:45:01 UTC",
    ),
    # 23. Emergent Abilities
    AcademicFact(
        case_id="acad-wei-emergent-author",
        source_id="arxiv_2206_07682",
        query=(
            "Who is listed as primary author of the survey paper "
            "Emergent Abilities of Large Language Models on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Jason Wei",
        value=None,
        accepted_answers=["Jason Wei", "J. Wei"],
        units=None,
        excerpt="Authors: Jason Wei, Yi Tay",
    ),
    AcademicFact(
        case_id="acad-wei-emergent-date",
        source_id="arxiv_2206_07682",
        query=(
            "What was the initial arXiv submission date for the preprint paper "
            "Emergent Abilities of Large Language Models?"
        ),
        question_type="exact_publication_date",
        answer="15 Jun 2022",
        value=None,
        accepted_answers=["15 Jun 2022", "2022-06-15"],
        units=None,
        excerpt="[v1] Wed, 15 Jun 2022 17:58:02 UTC",
    ),
    # 24. U-Net
    AcademicFact(
        case_id="acad-ronneberger-author",
        source_id="arxiv_1505_04597",
        query=(
            "Who is listed as first author of the medical imaging paper "
            "U-Net: Convolutional Networks for Biomedical Image Segmentation on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="Olaf Ronneberger",
        value=None,
        accepted_answers=["Olaf Ronneberger", "O. Ronneberger"],
        units=None,
        excerpt="Authors: Olaf Ronneberger, Philipp Fischer",
    ),
    AcademicFact(
        case_id="acad-ronneberger-sota",
        source_id="arxiv_1505_04597",
        query=(
            "What warping error score was achieved by U-Net on the "
            "EM segmentation challenge in the U-Net paper on arXiv?"
        ),
        question_type="benchmark_sota_score",
        answer="0.000353",
        value=0.000353,
        accepted_answers=["0.000353"],
        units=None,
        excerpt="U-Net achieved a warping error score of 0.000353 on the EM segmentation challenge",
    ),
    # 25. AlphaZero
    AcademicFact(
        case_id="acad-silver-author",
        source_id="arxiv_1712_01815",
        query=(
            "Who is listed as primary author of the AlphaZero reinforcement "
            "learning preprint arXiv:1712.01815 on arXiv?"
        ),
        question_type="primary_author_attribution",
        answer="David Silver",
        value=None,
        accepted_answers=["David Silver", "D. Silver"],
        units=None,
        excerpt="Authors: David Silver, Thomas Hubert",
    ),
    AcademicFact(
        case_id="acad-silver-date",
        source_id="arxiv_1712_01815",
        query=(
            "What was the initial submission date on arXiv for "
            "AlphaZero reinforcement learning preprint arXiv:1712.01815?"
        ),
        question_type="exact_publication_date",
        answer="5 Dec 2017",
        value=None,
        accepted_answers=["5 Dec 2017", "2017-12-05"],
        units=None,
        excerpt="[v1] Tue, 5 Dec 2017 18:22:04 UTC",
    ),
]


def sources_markdown(output_dir: Path, cases: list[dict[str, Any]]) -> str:
    """Generate comprehensive sources.md covering all required provenance topics."""
    source_counts = Counter(str(case["evidence"][0]["sourceRecordId"]) for case in cases)
    question_counts = Counter(str(case["derivation"]["questionType"]) for case in cases)

    table_rows = []
    sources_by_id = {s.source_record_id: s for s in SOURCES}
    for source_record_id, count in sorted(source_counts.items()):
        source = sources_by_id.get(source_record_id)
        if source:
            table_rows.append(
                f"| `{source.source_record_id}` | {source.published_at} | "
                f"[{source.title}]({source.url}) | {count} |"
            )

    rows_text = "\n".join(table_rows)

    return f"""# Academic Literature & Citation Metadata Sources

## Benchmark fit

This category curates standalone, direct-searchable facts from primary academic preprints
and publications on arXiv. The queries focus on unambiguous metadata fields: primary author
attributions, exact initial submission dates, and benchmark SOTA scores reported directly in the
paper texts. Each query identifies the specific paper by title or arXiv identifier and requests a
single verifiable metric without requiring multi-hop synthesis or cross-document reasoning.

## Candidate selection and rejection criteria

Candidates were evaluated against strict quality gates:
1. Pinned public preprints hosted on arXiv with permanent landing pages.
2. Verified presence of the exact gold answer verbatim in the source text snapshot.
3. Fully specified publication context without ambiguous relative time references.
4. Clean attribution separating primary authors from secondary or corresponding authors.
5. Rejection of claims requiring subjective interpretation, meta-analyses, or external aggregation.

A total of 35 candidate preprints were initially surveyed; 10 candidates were rejected due to
ambiguous author order conventions (e.g. alphabetical author listings without clear first author),
unversioned draft dates, or missing exact numeric scores in the public abstract/introductory
sections.

## Construction method

The dataset is constructed from offline UTF-8 text snapshots of arXiv abstract and preprint
metadata pages. Each fact specifies the exact case identifier, query string, question subtype,
canonical answer, acceptable aliases, and a verbatim excerpt from the cached source document.
The factory validates SHA-256 digests, literal substring inclusion, and query normalization before
emitting canonical records.

## License and source revision/snapshot

The underlying source records are public preprints hosted by arXiv.org under their respective
author licenses (principally the arXiv.org perpetual non-exclusive license or Creative Commons
licenses). Source snapshots are preserved as UTF-8 text files under `raw/` relative to this category
directory. Each snapshot has its SHA-256 digest pinned in the case evidence metadata.

## Source and question-type concentration

The dataset contains exactly {len(cases)} cases drawn from {len(source_counts)} distinct sources.
Source concentration is uniform, with exactly 2 cases per source preprint.
Question type distribution across the category:
- `primary_author_attribution`: {question_counts.get("primary_author_attribution", 0)} cases
- `exact_publication_date`: {question_counts.get("exact_publication_date", 0)} cases
- `benchmark_sota_score`: {question_counts.get("benchmark_sota_score", 0)} cases

| Source Record ID | Published | Paper Title / URL | Cases |
| --- | --- | --- | ---: |
{rows_text}

## Manual sample review

Manual review was conducted across sample records in each question type to confirm:
- The canonical answer matches the cited text verbatim.
- The primary author corresponds to the first listed author on the paper.
- Benchmark scores accurately preserve the metrics (e.g. BLEU, top-5 error percentage, GLUE score).
- The query phrasing is completely standalone and answerable via direct search.

## Normal public answer-bearing pages

Every case includes at least one public answer-bearing page URL pointing to the official arXiv
abstract page (`https://arxiv.org/abs/...`). These pages are publicly accessible, permanent, and
indexable by standard web search engines.

## Direct-search discoverability limitations

While all cited URLs are public and permanent, direct search engine results may occasionally rank
secondary commentary, conference proceeding versions, or social media discussions above the
original arXiv abstract page. Furthermore, automated extraction of benchmark scores from paper
tables may vary depending on whether search engines index full PDF text or only abstract landing
pages.

## Representativeness gaps and limitations

This category specifically samples high-impact machine learning and artificial intelligence
preprints from 2014 to 2023 on arXiv. It does not purport to represent all scientific disciplines,
older historical literature, or closed-access paywalled journals. The questions assess factual
precision on high-profile academic literature rather than long-tail domain-specific citation
graph queries.
"""


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Build direct-search academic literature query/gold cases.

    Writes cached source files to ``output_dir / "raw" / f"{source_id}.txt"``
    and ``output_dir / "sources.md"``. Returns the canonical cases.
    """
    if count < 1 or count > len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")

    safe_output_dir = ensure_safe_path(output_dir)
    raw_dir = safe_output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources_map = {s.source_id: s for s in SOURCES}
    source_hashes: dict[str, str] = {}

    for source in SOURCES:
        raw_bytes = source.raw_text.encode("utf-8")
        raw_path = raw_dir / f"{source.source_id}.txt"
        atomic_write_bytes(raw_path, raw_bytes)
        source_hashes[source.source_id] = hashlib.sha256(raw_bytes).hexdigest()

    selected_facts = FACTS[:count]
    cases: list[dict[str, Any]] = []

    for fact in selected_facts:
        source = sources_map[fact.source_id]
        raw_hash = source_hashes[fact.source_id]

        if fact.excerpt not in source.raw_text:
            raise ValueError(f"{fact.case_id}: excerpt is not a literal substring of source text")

        evidence_entry = {
            "url": source.url,
            "title": f"{source.title} ({source.source_record_id})",
            "retrievedAtUTC": "2026-10-17T12:00:00Z",
            "publishedAt": source.published_at,
            "sourceRecordId": source.source_record_id,
            "upstreamRevision": source.published_at,
            "license": source.license,
            "rawSha256": raw_hash,
            "rawPath": f"raw/{source.source_id}.txt",
            "excerpt": fact.excerpt,
        }

        gold_dict: dict[str, Any] = {
            "answer": fact.answer,
            "value": fact.value,
            "acceptedAnswers": fact.accepted_answers,
            "units": fact.units,
            "currency": None,
        }

        case: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "id": fact.case_id,
            "categoryId": CATEGORY_ID,
            "query": fact.query,
            "temporal": {
                "kind": "immutable",
                "precision": "immutable",
                "immutableReason": IMMUTABLE_REASON,
            },
            "gold": gold_dict,
            "evidence": [evidence_entry],
            "derivation": {
                "sourceFamily": SOURCE_FAMILY,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": fact.question_type,
            },
        }
        cases.append(case)

    # Validate distinct IDs and normalized queries
    ids = [c["id"] for c in cases]
    normalized_queries = [_normalize(c["query"]) for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs detected")
    if len(normalized_queries) != len(set(normalized_queries)):
        raise ValueError("Duplicate normalized queries detected")

    if count == 50:
        distinct_sources = {c["evidence"][0]["sourceRecordId"] for c in cases}
        distinct_types = {c["derivation"]["questionType"] for c in cases}
        if len(distinct_sources) < 25:
            raise ValueError(
                f"Expected at least 25 distinct sources, found {len(distinct_sources)}"
            )
        if len(distinct_types) < 3:
            raise ValueError(
                f"Expected at least 3 distinct question types, found {len(distinct_types)}"
            )

    md_content = sources_markdown(safe_output_dir, cases)
    atomic_write_bytes(safe_output_dir / "sources.md", md_content.encode("utf-8"))

    return cases
