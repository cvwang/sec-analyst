"""Pure Python deterministic statistical and quantitative evaluation metrics for SEC EDGAR analyst."""

import re
from typing import List, Dict, Any, Optional, Set, Tuple


def extract_numbers_from_text(text: str) -> List[float]:
    """Extracts floating point and integer numbers from a text string."""
    if not text:
        return []
    # Match numbers formatted like 383,285.0 or 383285 or -$11,043.0 or -11,043 or 2.8%
    pattern = r'-?\s*\$?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    raw_matches = re.findall(pattern, text)
    numbers = []
    for match in raw_matches:
        cleaned = match.replace("$", "").replace(",", "").replace(" ", "")
        if not cleaned or cleaned == "-":
            continue
        try:
            val = float(cleaned)
            numbers.append(val)
        except ValueError:
            continue
    return numbers



def compute_numerical_accuracy(
    generated_narrative: str,
    expected_values: List[float],
    tolerance_pct: float = 0.5
) -> Dict[str, Any]:
    """Verifies presence and accuracy of expected numbers in generated narrative deterministically.
    
    Returns a dict with pass_rate (0.0 to 1.0), matched_values, missing_values, and is_100_percent_accurate.
    """
    if not expected_values:
        return {
            "pass_rate": 1.0,
            "matched_values": [],
            "missing_values": [],
            "is_100_percent_accurate": True
        }

    extracted_numbers = extract_numbers_from_text(generated_narrative)
    matched = []
    missing = []

    for exp in expected_values:
        if exp is None:
            continue
        found = False
        for ext in extracted_numbers:
            if exp == 0.0:
                if abs(ext) < 1e-4:
                    found = True
                    break
            else:
                rel_diff = abs(ext - exp) / abs(exp) * 100.0
                if rel_diff <= tolerance_pct:
                    found = True
                    break
        if found:
            matched.append(exp)
        else:
            missing.append(exp)

    total = len([v for v in expected_values if v is not None])
    pass_rate = (len(matched) / total) if total > 0 else 1.0
    return {
        "pass_rate": pass_rate,
        "matched_values": matched,
        "missing_values": missing,
        "is_100_percent_accurate": pass_rate == 1.0
    }


def compute_grounding_recall(
    generated_narrative: str,
    retrieved_chunks: List[str],
    expected_keywords: List[str]
) -> Dict[str, float]:
    """Computes Grounding Recall deterministically:
    Grounding Recall = 0.5 * Numeric_Recall + 0.5 * Keyword_Recall
    
    Numeric_Recall: % of numbers in narrative present in retrieved context.
    Keyword_Recall: % of required grounding keywords present in narrative and context.
    """
    if not generated_narrative:
        return {"numeric_recall": 0.0, "keyword_recall": 0.0, "grounding_recall": 0.0}

    # 1. Numeric Recall
    narrative_numbers = extract_numbers_from_text(generated_narrative)
    context_text = " ".join(retrieved_chunks if retrieved_chunks else [])
    context_numbers = set(extract_numbers_from_text(context_text))

    if not narrative_numbers:
        numeric_recall = 1.0
    else:
        grounded_count = 0
        for num in narrative_numbers:
            # Check if number appears in context
            is_present = False
            for c_num in context_numbers:
                if num == 0.0:
                    if abs(c_num) < 1e-4:
                        is_present = True
                        break
                elif abs(num - c_num) / abs(num) <= 0.01:
                    is_present = True
                    break
            if is_present:
                grounded_count += 1
        numeric_recall = grounded_count / len(narrative_numbers)

    # 2. Keyword Recall
    if not expected_keywords:
        keyword_recall = 1.0
    else:
        found_kw = 0
        narrative_lower = generated_narrative.lower()
        for kw in expected_keywords:
            if kw and kw.lower() in narrative_lower:
                found_kw += 1
        keyword_recall = found_kw / len(expected_keywords)

    combined_grounding_recall = 0.5 * numeric_recall + 0.5 * keyword_recall
    return {
        "numeric_recall": round(numeric_recall, 4),
        "keyword_recall": round(keyword_recall, 4),
        "grounding_recall": round(combined_grounding_recall, 4)
    }


def _tokenize(text: str) -> List[str]:
    """Basic lowercased word tokenization."""
    if not text:
        return []
    return re.findall(r'\b\w+\b', text.lower())


def compute_rouge_1(candidate_text: str, reference_text: str) -> Dict[str, float]:
    """Computes ROUGE-1 unigram overlap precision, recall, and F1 score."""
    cand_tokens = _tokenize(candidate_text)
    ref_tokens = _tokenize(reference_text)

    if not cand_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    ref_counts: Dict[str, int] = {}
    for tok in ref_tokens:
        ref_counts[tok] = ref_counts.get(tok, 0) + 1

    match_count = 0
    for tok in cand_tokens:
        if ref_counts.get(tok, 0) > 0:
            match_count += 1
            ref_counts[tok] -= 1

    precision = match_count / len(cand_tokens)
    recall = match_count / len(ref_tokens)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }


def compute_rouge_l(candidate_text: str, reference_text: str) -> Dict[str, float]:
    """Computes ROUGE-L Longest Common Subsequence (LCS) precision, recall, and F1 score."""
    cand_tokens = _tokenize(candidate_text)
    ref_tokens = _tokenize(reference_text)

    m = len(cand_tokens)
    n = len(ref_tokens)

    if m == 0 or n == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Dynamic programming grid for LCS length
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if cand_tokens[i - 1] == ref_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_len = dp[m][n]
    precision = lcs_len / m
    recall = lcs_len / n
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }
