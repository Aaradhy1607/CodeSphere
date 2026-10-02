import re
import math
import hashlib
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from app.models.models import Question

class DuplicateDetector:
    """
    Multi-Tier Duplicate & Semantic Similarity Detection Engine for CodeSphere.
    
    Operates across 3 distinct analytical levels:
    - LEVEL 1: Exact Normalized Content Hash (SHA-256)
    - LEVEL 2: Lexical Similarity (Token N-gram Jaccard + Character Levenshtein Ratio)
    - LEVEL 3: Semantic Concept Overlap (Term-Frequency & Algorithmic Concept Cosine Similarity)
    
    Produces 4-Tier Categorization:
    - DUPLICATE (score >= 0.88 or exact match) -> Action: Reject or require explicit confirmation
    - SIMILAR   (0.70 <= score < 0.88)          -> Action: Flag for author review
    - RELATED   (0.45 <= score < 0.70)          -> Action: Thematically related, distinct problem
    - UNIQUE    (score < 0.45)                  -> Action: Novel question candidate
    """

    DUPLICATE_THRESHOLD = 0.88
    SIMILAR_THRESHOLD = 0.70
    RELATED_THRESHOLD = 0.45

    # Common English stopwords to prevent false-positive duplicate inflation
    STOPWORDS: Set[str] = {
        "a", "an", "the", "in", "on", "at", "to", "for", "with", "by", "about",
        "of", "and", "or", "but", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "you", "your", "given",
        "write", "program", "function", "code", "algorithm", "problem", "find",
        "return", "print", "input", "output", "test", "case", "example"
    }

    # Canonical semantic synonym / concept normalization map
    CONCEPT_SYNONYMS: Dict[str, str] = {
        "working principle of": "how works",
        "working principle": "how works",
        "working mechanism of": "how works",
        "working mechanism": "how works",
        "describe the": "explain",
        "describe how": "explain how",
        "illustrate how": "explain how",
        "clarify how": "explain how",
        "describe": "explain",
        "illustrate": "explain",
        "methodology": "approach",
        "computational complexity": "time complexity",
        "asymptotic complexity": "time complexity",
        "running time": "time complexity",
        "space usage": "space complexity",
        "memory consumption": "space complexity"
    }

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Strips punctuation, lowercases, canonicalizes synonyms, and normalizes whitespace."""
        if not text:
            return ""
        s = text.lower()
        s = re.sub(r'```[\s\S]*?```', '', s) # Strip code blocks for conceptual comparison
        for syn, canon in cls.CONCEPT_SYNONYMS.items():
            s = s.replace(syn, canon)
        s = re.sub(r'[^a-z0-9\s]', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    @classmethod
    def get_content_tokens(cls, text: str) -> List[str]:
        """Extracts informative content tokens, removing common boilerplate stopwords."""
        norm = cls.normalize_text(text)
        tokens = norm.split()
        return [t for t in tokens if t not in cls.STOPWORDS and len(t) > 1]

    @classmethod
    def compute_hash(cls, text: str) -> str:
        """Computes SHA-256 hash of normalized text for instant Level-1 exact lookups."""
        norm = cls.normalize_text(text)
        return hashlib.sha256(norm.encode('utf-8')).hexdigest()

    @classmethod
    def _jaccard_similarity(cls, tokens1: List[str], tokens2: List[str], n: int = 2) -> float:
        """Computes Jaccard similarity coefficient over token n-grams."""
        if not tokens1 or not tokens2:
            return 0.0

        if len(tokens1) < n or len(tokens2) < n:
            set1 = set(tokens1)
            set2 = set(tokens2)
        else:
            set1 = set(tuple(tokens1[i:i+n]) for i in range(len(tokens1) - n + 1))
            set2 = set(tuple(tokens2[i:i+n]) for i in range(len(tokens2) - n + 1))

        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def _semantic_concept_similarity(cls, tokens1: List[str], tokens2: List[str]) -> float:
        """
        Computes cosine similarity over term frequency vectors of key concepts,
        measuring semantic concept overlap while penalizing structural intent differences.
        """
        if not tokens1 or not tokens2:
            return 0.0

        freq1: Dict[str, int] = {}
        for t in tokens1:
            freq1[t] = freq1.get(t, 0) + 1

        freq2: Dict[str, int] = {}
        for t in tokens2:
            freq2[t] = freq2.get(t, 0) + 1

        all_terms = set(freq1.keys()).union(set(freq2.keys()))
        dot_product = sum(freq1.get(term, 0) * freq2.get(term, 0) for term in all_terms)
        norm1 = math.sqrt(sum(v ** 2 for v in freq1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in freq2.values()))

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot_product / (norm1 * norm2)

    @classmethod
    def compare_statements(cls, statement1: str, statement2: str) -> Dict[str, Any]:
        """
        Compares two question statements across Level 1, Level 2, and Level 3 tiers.
        """
        norm1 = cls.normalize_text(statement1)
        norm2 = cls.normalize_text(statement2)

        # Level 1: Exact check
        if norm1 and norm1 == norm2:
            return {
                "similarity_score": 1.0,
                "level_1_exact": True,
                "level_2_lexical": 1.0,
                "level_3_semantic": 1.0,
                "category": "DUPLICATE",
                "is_duplicate": True
            }

        tokens1 = cls.get_content_tokens(statement1)
        tokens2 = cls.get_content_tokens(statement2)

        # Level 2: Lexical similarity
        seq_ratio = SequenceMatcher(None, norm1[:1200], norm2[:1200]).ratio()
        ngram_jaccard = cls._jaccard_similarity(tokens1, tokens2, n=2)
        unigram_jaccard = cls._jaccard_similarity(tokens1, tokens2, n=1)
        lexical_score = (seq_ratio * 0.4) + (ngram_jaccard * 0.3) + (unigram_jaccard * 0.3)

        # Level 3: Semantic concept similarity
        semantic_score = cls._semantic_concept_similarity(tokens1, tokens2)

        # Weighted composite score
        composite_score = (lexical_score * 0.50) + (semantic_score * 0.50)
        composite_score = round(min(1.0, max(0.0, composite_score)), 3)

        # Intent modifier: If one is "compare X and Y" and other is just "explain X",
        # the presence of unique distinguishing keywords like 'compare', 'difference', 'versus'
        # decreases duplicate probability.
        intent_contrast_words = {"compare", "contrast", "difference", "versus", "vs", "benchmark"}
        has_contrast_1 = bool(set(tokens1).intersection(intent_contrast_words))
        has_contrast_2 = bool(set(tokens2).intersection(intent_contrast_words))
        if has_contrast_1 != has_contrast_2:
            composite_score = round(max(0.0, composite_score * 0.70), 3)

        if composite_score >= cls.DUPLICATE_THRESHOLD:
            category = "DUPLICATE"
            is_dup = True
        elif composite_score >= cls.SIMILAR_THRESHOLD:
            category = "SIMILAR"
            is_dup = False
        elif composite_score >= cls.RELATED_THRESHOLD:
            category = "RELATED"
            is_dup = False
        else:
            category = "UNIQUE"
            is_dup = False

        return {
            "similarity_score": composite_score,
            "level_1_exact": False,
            "level_2_lexical": round(lexical_score, 3),
            "level_3_semantic": round(semantic_score, 3),
            "category": category,
            "is_duplicate": is_dup
        }

    @classmethod
    def check_duplicate(
        cls,
        title: str,
        problem_statement: str,
        db: Session,
        exclude_question_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scans existing Question bank to detect exact, lexical, or semantic duplicates.
        """
        norm_title = cls.normalize_text(title)
        norm_statement = cls.normalize_text(problem_statement)
        full_norm = f"{norm_title} {norm_statement}"
        content_hash = cls.compute_hash(full_norm)

        # 1. Level 1: Exact Hash Check
        query = db.query(Question).filter(Question.similarity_hash == content_hash)
        if exclude_question_id:
            query = query.filter(Question.id != exclude_question_id)
        exact_match = query.first()

        if exact_match:
            return {
                "is_duplicate": True,
                "similarity_score": 1.0,
                "normalized_similarity_percent": 100.0,
                "matched_question_id": exact_match.id,
                "matched_title": exact_match.title,
                "category": "DUPLICATE",
                "match_reason": f"Exact duplicate of Question #{exact_match.id} ('{exact_match.title}').",
                "similarity_hash": content_hash,
                "level_1_exact": True,
                "level_2_lexical": 1.0,
                "level_3_semantic": 1.0
            }

        # 2. Multi-Level Scan over existing questions
        scan_query = db.query(Question.id, Question.title, Question.problem_statement, Question.similarity_hash)
        if exclude_question_id:
            scan_query = scan_query.filter(Question.id != exclude_question_id)
        existing_questions = scan_query.all()

        max_sim = 0.0
        best_match_id = None
        best_match_title = None
        best_match_category = "UNIQUE"
        best_comparison = None

        target_full = f"{title} {problem_statement}"

        for q_id, q_title, q_statement, q_hash in existing_questions:
            cand_full = f"{q_title} {q_statement}"
            cmp_res = cls.compare_statements(target_full, cand_full)

            # Fast title exact override
            q_norm_title = cls.normalize_text(q_title)
            if norm_title and norm_title == q_norm_title and len(norm_title.split()) >= 3:
                cmp_res["similarity_score"] = max(cmp_res["similarity_score"], 0.95)
                cmp_res["category"] = "DUPLICATE"
                cmp_res["is_duplicate"] = True

            if cmp_res["similarity_score"] > max_sim:
                max_sim = cmp_res["similarity_score"]
                best_match_id = q_id
                best_match_title = q_title
                best_match_category = cmp_res["category"]
                best_comparison = cmp_res

        if best_match_category == "DUPLICATE":
            match_reason = f"Duplicate question ({round(max_sim * 100, 1)}% similarity) of Question #{best_match_id} ('{best_match_title}')."
        elif best_match_category == "SIMILAR":
            match_reason = f"Highly similar problem statement ({round(max_sim * 100, 1)}% match) to Question #{best_match_id} ('{best_match_title}')."
        elif best_match_category == "RELATED":
            match_reason = f"Thematically related question ({round(max_sim * 100, 1)}% match) with Question #{best_match_id} ('{best_match_title}')."
        else:
            match_reason = "No similar question detected."

        return {
            "is_duplicate": best_match_category == "DUPLICATE",
            "similarity_score": round(max_sim, 3),
            "normalized_similarity_percent": round(max_sim * 100, 1),
            "matched_question_id": best_match_id if max_sim >= cls.RELATED_THRESHOLD else None,
            "matched_title": best_match_title if max_sim >= cls.RELATED_THRESHOLD else None,
            "category": best_match_category,
            "match_reason": match_reason,
            "similarity_hash": content_hash,
            "level_1_exact": bool(best_comparison and best_comparison.get("level_1_exact")),
            "level_2_lexical": best_comparison.get("level_2_lexical", 0.0) if best_comparison else 0.0,
            "level_3_semantic": best_comparison.get("level_3_semantic", 0.0) if best_comparison else 0.0
        }

duplicate_detector = DuplicateDetector()
