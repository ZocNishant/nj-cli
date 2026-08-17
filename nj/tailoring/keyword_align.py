from __future__ import annotations

import re
from collections import Counter

from nj.utils.logger import get_logger

logger = get_logger(__name__)

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "our",
    "your",
    "their",
    "its",
    "this",
    "that",
    "these",
    "those",
    "we",
    "you",
    "they",
    "it",
    "he",
    "she",
    "who",
    "which",
    "what",
    "not",
    "no",
    "nor",
    "so",
    "yet",
    "both",
    "either",
    "neither",
    "as",
    "if",
    "than",
    "then",
    "when",
    "where",
    "while",
    "although",
    "must",
    "also",
    "well",
    "such",
    "more",
    "other",
    "into",
    "through",
    "experience",
    "work",
    "team",
    "strong",
    "ability",
    "skills",
    "role",
    "position",
    "candidate",
    "join",
    "looking",
    "seeking",
    "years",
}


def extract_keywords(
    jd_text: str,
    existing_skills: list[str],
    top_n: int = 20,
) -> list[str]:
    tech_patterns = [
        r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\b",
        (
            r"\b(?:PyTorch|TensorFlow|scikit-learn|OpenCV|FastAPI|"
            r"Docker|Kubernetes|AWS|GCP|Azure|CUDA|MLflow|"
            r"HuggingFace|LangChain|ONNX|TensorRT|Ray|Spark|"
            r"Airflow|dbt|Snowflake|PostgreSQL|MongoDB|Redis|Kafka|"
            r"JAX|NumPy|Pandas|Matplotlib|Seaborn|Plotly|Streamlit|"
            r"Gradio|Flask|Django|React|TypeScript|Rust|Go|Scala|"
            r"C\+\+|MATLAB|Julia|Bash|Linux|Git|REST|"
            r"GraphQL|gRPC|Transformer|BERT|GPT|LLM|RAG|LoRA|PEFT|"
            r"ViT|ResNet|EfficientNet|YOLO|SAM|Diffusion|GAN|VAE|"
            r"RL|PPO|DQN|RLHF|FLAN|Llama|Mistral|"
            r"medical imaging|computer vision|NLP|speech|audio|"
            r"time series|tabular|recommendation|search|ranking|"
            r"segmentation|detection|classification|generation|"
            r"fine-tuning|pre-training|distillation|quantization|"
            r"MLOps|DataOps|feature store|model serving|inference|"
            r"A/B testing|experimentation|causal|Bayesian|"
            r"graph neural|GNN|point cloud|3D|multimodal|"
            r"federated|privacy|differential privacy)\b"
        ),
    ]

    found_terms: list[str] = []
    for pattern in tech_patterns:
        matches = re.findall(pattern, jd_text, re.IGNORECASE)
        found_terms.extend(matches)

    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.-]{2,}\b", jd_text)
    tokens = [t.lower() for t in tokens if t.lower() not in STOPWORDS]
    freq = Counter(tokens)
    freq_terms = [w for w, _ in freq.most_common(30) if len(w) > 3]

    existing_lower = {s.lower() for s in existing_skills}
    all_terms: list[str] = []
    seen: set[str] = set()
    for term in found_terms + freq_terms:
        term_lower = term.lower().strip()
        if (
            term_lower not in seen
            and term_lower not in existing_lower
            and len(term_lower) > 2
            and term_lower not in STOPWORDS
        ):
            seen.add(term_lower)
            all_terms.append(term.strip())

    logger.debug("keywords_extracted", count=len(all_terms[:top_n]), keywords=all_terms[:top_n])
    return all_terms[:top_n]


def flatten_skills(skills: dict) -> list[str]:
    flat = []
    for items in skills.values():
        if isinstance(items, list):
            flat.extend(items)
    return flat
