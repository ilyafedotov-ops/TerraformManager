from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import re

from backend.llm_service import KBPassage

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

# Optional TF-IDF support (kept lightweight and in-process)
_tfidf_vectorizer = None  # type: ignore
_tfidf_matrix = None  # type: ignore
_doc_index: List[Path] = []


def _iter_markdown_files() -> List[Path]:
    if not KNOWLEDGE_DIR.exists():
        return []
    # Scan recursively to include external synced docs
    return [p for p in KNOWLEDGE_DIR.rglob("*.md") if p.is_file()]


def _load_docs() -> List[Tuple[str, str]]:
    docs: List[Tuple[str, str]] = []
    for p in _iter_markdown_files():
        try:
            docs.append((str(p.relative_to(KNOWLEDGE_DIR)), p.read_text(encoding="utf-8", errors="ignore")))
        except Exception:
            continue
    return docs


def _score_docs_keyword(query: str, top_k: int) -> List[Tuple[int, str, str]]:
    docs = _load_docs()
    if not docs:
        return []
    if not query.strip():
        return [(1, name, text) for name, text in docs[:top_k]]
    keywords = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
    scored: List[Tuple[int, str, str]] = []
    for name, text in docs:
        t = text.lower()
        score = sum(t.count(k) for k in keywords)
        scored.append((score, name, text))
    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[:top_k]


def _ensure_tfidf():
    global _tfidf_vectorizer, _tfidf_matrix, _doc_index
    if _tfidf_vectorizer is not None and _tfidf_matrix is not None and _doc_index:
        return
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    except Exception:
        # scikit-learn unavailable; fallback will be used
        _tfidf_vectorizer = None
        _tfidf_matrix = None
        _doc_index = []
        return

    docs = _iter_markdown_files()
    texts: List[str] = []
    for p in docs:
        try:
            texts.append(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            texts.append("")
    if not texts:
        _tfidf_vectorizer = None
        _tfidf_matrix = None
        _doc_index = []
        return
    vectorizer = TfidfVectorizer(stop_words="english", max_features=10000)
    matrix = vectorizer.fit_transform(texts)
    _tfidf_vectorizer = vectorizer
    _tfidf_matrix = matrix
    _doc_index = docs


def _score_docs_tfidf(query: str, top_k: int) -> List[Tuple[float, str, str]]:
    _ensure_tfidf()
    if _tfidf_vectorizer is None or _tfidf_matrix is None or not _doc_index:
        return []
    try:
        qvec = _tfidf_vectorizer.transform([query])
        import numpy as np  # type: ignore

        scores = (qvec @ _tfidf_matrix.T).toarray().ravel()
        top_idx = scores.argsort()[::-1][:top_k]
        results: List[Tuple[float, str, str]] = []
        for i in top_idx:
            p = _doc_index[int(i)]
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            results.append((float(scores[i]), str(p.relative_to(KNOWLEDGE_DIR)), text))
        return results
    except Exception:
        return []


def retrieve_passages(query: str, top_k: int = 3) -> List[KBPassage]:
    # Prefer TF-IDF if available, else simple keyword scoring
    scored_any = _score_docs_tfidf(query, top_k)
    passages: List[KBPassage] = []
    if not scored_any:
        for score, name, text in _score_docs_keyword(query, top_k):
            passages.append(KBPassage(source=name, content=text, score=float(score)))
        return passages
    for score, name, text in scored_any:
        passages.append(KBPassage(source=name, content=text, score=float(score)))
    return passages


def retrieve(query: str, top_k: int = 3) -> List[Tuple[str, str]]:
    return [(p.source, p.content) for p in retrieve_passages(query, top_k)]


def retrieve_snippets(query: str, top_k: int = 3, max_chars: Optional[int] = 800) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for passage in retrieve_passages(query, top_k):
        text = passage.content
        if max_chars is not None and len(text) > max_chars:
            text = text[:max_chars]
        results.append(
            {
                "source": passage.source,
                "content": text,
                "score": passage.score,
            }
        )
    return results


def warm_index() -> int:
    """Build the TF-IDF index eagerly and return number of documents indexed."""
    _ensure_tfidf()
    return len(_doc_index)


QUERIES = {
    "AWS-S3-SSE": "aws s3 server side encryption kms best practices",
    "AWS-S3-PUBLIC-ACL": "aws s3 public access block avoid public-read",
    "AWS-SG-OPEN-SSH": "security group 0.0.0.0/0 ssh 22 avoid",
    "AWS-IAM-WILDCARD": "iam policy least privilege avoid wildcard",
    "AWS-CLOUDTRAIL-MULTI-REGION": "aws cloudtrail multi region trail log file validation best practices",
    "AWS-CONFIG-RECORDER": "aws config recorder delivery channel all supported global resources",
    "AWS-VPC-FLOW-LOGS": "aws vpc flow logs enable cloudwatch best practices",
    "AWS-RDS-ENCRYPTION": "aws rds storage encryption kms best practices",
    "AWS-RDS-BACKUP": "aws rds automated backups retention policy",
    "AWS-RDS-PERF-INSIGHTS": "aws rds performance insights enable benefits",
    "AWS-ALB-HTTPS": "aws alb https listener redirect http 301 best practices",
    "AWS-WAF-ASSOCIATION": "aws waf associate alb best practices",
    "AZ-STORAGE-HTTPS": "azure storage account enable_https_traffic_only",
    "AZ-STORAGE-BLOB-PUBLIC": "azure storage account allow_blob_public_access false",
    "AZ-STORAGE-MIN-TLS": "azure storage min tls version TLS1_2",
    "AZ-NSG-OPEN-SSH": "azure nsg ssh open internet",
    "AZ-NET-FLOW-LOGS": "azure nsg flow logs log analytics traffic analytics",
    "AZ-AKS-PRIVATE-API": "azure aks private cluster disable public api",
    "AZ-KV-PURGE-PROTECTION": "azure key vault purge protection soft delete requirements",
    "AZ-KV-NETWORK": "azure key vault private endpoint public network access disabled",
    "K8S-IMAGE-NO-LATEST": "kubernetes avoid latest image tag",
    "K8S-POD-RUN-AS-NON-ROOT": "kubernetes securityContext runAsNonRoot best practices",
    "K8S-POD-RESOURCES-LIMITS": "kubernetes resources limits requests best practices",
    "K8S-NAMESPACE-NETPOL": "kubernetes default deny network policy namespace security",
    "K8S-PDB-REQUIRED": "kubernetes pod disruption budget ha best practices",
    "K8S-POD-PRIVILEGED": "kubernetes avoid privileged containers security context",
    "K8S-POD-HOSTPATH": "kubernetes hostpath volume security risks alternatives",
    "SYNTAX-HCL-PARSE": "terraform language syntax hcl validate fmt",
    "SYNTAX-TERRAFORM-VALIDATE": "terraform validate command failures troubleshooting",
}


def _query_for_rule(rule_id: str) -> str:
    return QUERIES.get(rule_id, rule_id)


def get_passages_for_rule(rule_id: str, top_k: int = 3) -> List[KBPassage]:
    return retrieve_passages(_query_for_rule(rule_id), top_k=top_k)


def explain(rule_id: str) -> str:
    passages = get_passages_for_rule(rule_id, top_k=2)
    bits = [f"From {p.source}:\n\n{p.content.strip()}" for p in passages if p.content.strip()]
    return "\n\n---\n\n".join(bits) if bits else "No local references found yet. Add content to knowledge/."
