#!/usr/bin/env python3
"""
Fast Article Validator

Uses PRE-COMPUTED guideline data from database for FAST validation.
No re-parsing or quartile re-calculation - just validate current content.

Designed for real-time validation as LLM writes article content.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from guideline_storage import StoredGuideline


@dataclass
class ValidationFeedback:
    """Compact validation feedback for LLM"""
    keyword: str
    current: int
    target: int
    delta: int  # How many to add/remove
    status: str  # "below_min", "below_target", "at_target", "above_target", "above_max"
    priority: str  # "critical", "high", "medium", "low", "optimal"


@dataclass
class FastValidationResult:
    """Fast validation result using pre-computed data"""

    # Overall status
    total_keywords: int
    keywords_at_target: int
    keywords_within_range: int
    overall_score: float  # 0-100

    # Structure validation
    structure_valid: bool
    structure_feedback: List[str]

    # Keyword feedback (only issues)
    keyword_feedback: List[ValidationFeedback]

    # Quick summary for LLM
    summary: str

    def to_dict(self) -> Dict:
        return {
            'total_keywords': self.total_keywords,
            'keywords_at_target': self.keywords_at_target,
            'keywords_within_range': self.keywords_within_range,
            'overall_score': self.overall_score,
            'structure_valid': self.structure_valid,
            'structure_feedback': self.structure_feedback,
            'keyword_feedback': [
                {
                    'keyword': kf.keyword,
                    'current': kf.current,
                    'target': kf.target,
                    'delta': kf.delta,
                    'status': kf.status,
                    'priority': kf.priority
                }
                for kf in self.keyword_feedback
            ],
            'summary': self.summary
        }


class FastArticleValidator:
    """
    Fast validator using pre-computed guideline data.

    Usage:
        # Load pre-computed guideline from database
        stored_guideline = load_from_database()

        # Create validator (reuse for multiple validations)
        validator = FastArticleValidator(stored_guideline, target_quartile="Q3")

        # Validate article content (FAST - called repeatedly)
        result = validator.validate(article_text)
    """

    def __init__(self, stored_guideline: StoredGuideline, target_quartile: str = "Q3"):
        """
        Initialize validator with pre-computed guideline data.

        Args:
            stored_guideline: Pre-computed guideline from database
            target_quartile: "Q1", "Q2", "Q3", or "Q4"
        """
        self.guideline = stored_guideline
        self.target_quartile = target_quartile.upper()

        # Select appropriate quartile data
        if self.target_quartile == "Q1":
            self.keyword_targets = stored_guideline.keywords_q1
        elif self.target_quartile == "Q2":
            self.keyword_targets = stored_guideline.keywords_q2
        elif self.target_quartile == "Q3":
            self.keyword_targets = stored_guideline.keywords_q3
        elif self.target_quartile == "Q4":
            self.keyword_targets = stored_guideline.keywords_q4
        else:
            raise ValueError(f"Invalid quartile: {target_quartile}. Use Q1, Q2, Q3, or Q4")

    def validate(self, content: str) -> FastValidationResult:
        """
        Fast validation of article content.

        Args:
            content: Article text to validate

        Returns:
            FastValidationResult with feedback
        """
        # Count structure elements (fast)
        word_count = self._count_words(content)
        char_count = self._count_characters(content)
        heading_count = self._count_headings(content)
        paragraph_count = self._count_paragraphs(content)
        image_count = self._count_images(content)

        # Validate structure
        structure_valid, structure_feedback = self._validate_structure(
            word_count, char_count, heading_count, paragraph_count, image_count
        )

        # Count keywords (fast - simple regex)
        keyword_counts = self._count_keywords(content)

        # Validate keywords against targets
        keyword_feedback = self._validate_keywords(keyword_counts)

        # Calculate overall score
        keywords_at_target = sum(1 for kf in keyword_feedback if kf.status == "at_target")
        keywords_within_range = sum(1 for kf in keyword_feedback if kf.status in ["at_target", "below_target", "above_target"])

        total_keywords = len(self.keyword_targets)
        overall_score = self._calculate_score(
            keywords_at_target, keywords_within_range, total_keywords, structure_valid
        )

        # Generate summary
        summary = self._generate_summary(
            keyword_feedback, structure_feedback, overall_score
        )

        return FastValidationResult(
            total_keywords=total_keywords,
            keywords_at_target=keywords_at_target,
            keywords_within_range=keywords_within_range,
            overall_score=overall_score,
            structure_valid=structure_valid,
            structure_feedback=structure_feedback,
            keyword_feedback=keyword_feedback,
            summary=summary
        )

    def _count_words(self, content: str) -> int:
        """Fast word count"""
        clean = re.sub(r'<[^>]+>', '', content)
        clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)
        return len(re.findall(r'\b\w+\b', clean))

    def _count_characters(self, content: str) -> int:
        """Fast character count"""
        clean = re.sub(r'<[^>]+>', '', content)
        clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)
        return len(clean)

    def _count_headings(self, content: str) -> int:
        """Fast heading count"""
        md_headings = len(re.findall(r'^\s*#{1,6}\s+.+$', content, re.MULTILINE))
        html_headings = len(re.findall(r'<h[1-6][^>]*>.*?</h[1-6]>', content, re.IGNORECASE | re.DOTALL))
        return md_headings + html_headings

    def _count_paragraphs(self, content: str) -> int:
        """Fast paragraph count"""
        if '<p>' in content:
            return content.count('<p>')

        lines = content.split('\n')
        paragraphs = []
        current_para = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or re.match(r'^<h[1-6]', stripped):
                if current_para:
                    paragraphs.append(' '.join(current_para))
                    current_para = []
            else:
                current_para.append(stripped)

        if current_para:
            paragraphs.append(' '.join(current_para))

        return len(paragraphs)

    def _count_images(self, content: str) -> int:
        """Fast image count"""
        markdown_imgs = len(re.findall(r'!\[.*?\]\(.*?\)', content))
        html_imgs = len(re.findall(r'<img[^>]*>', content, re.IGNORECASE))
        placeholder_imgs = len(re.findall(r'\[IMAGE:.*?\]', content, re.IGNORECASE))
        return markdown_imgs + html_imgs + placeholder_imgs

    def _count_keywords(self, content: str) -> Dict[str, int]:
        """Fast keyword counting"""
        content_lower = content.lower()
        counts = {}

        for keyword in self.keyword_targets.keys():
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            count = len(re.findall(pattern, content_lower))
            counts[keyword] = count

        return counts

    def _validate_structure(
        self,
        word_count: int,
        char_count: int,
        heading_count: int,
        paragraph_count: int,
        image_count: int
    ) -> Tuple[bool, List[str]]:
        """Validate structure requirements"""
        feedback = []
        all_valid = True

        # Words
        if word_count < self.guideline.words_min:
            feedback.append(f"Add {self.guideline.words_min - word_count} more words")
            all_valid = False
        elif word_count > self.guideline.words_max:
            feedback.append(f"Remove {word_count - self.guideline.words_max} words")
            all_valid = False

        # Characters
        if char_count < self.guideline.characters_min:
            feedback.append(f"Add {self.guideline.characters_min - char_count} more characters")
            all_valid = False
        elif char_count > self.guideline.characters_max:
            feedback.append(f"Remove {char_count - self.guideline.characters_max} characters")
            all_valid = False

        # Headings
        if heading_count < self.guideline.headings_min:
            feedback.append(f"Add {self.guideline.headings_min - heading_count} more headings")
            all_valid = False
        elif heading_count > self.guideline.headings_max:
            feedback.append(f"Remove {heading_count - self.guideline.headings_max} headings")
            all_valid = False

        # Paragraphs
        if paragraph_count < self.guideline.paragraphs_min:
            feedback.append(f"Add {self.guideline.paragraphs_min - paragraph_count} more paragraphs")
            all_valid = False
        elif self.guideline.paragraphs_max and paragraph_count > self.guideline.paragraphs_max:
            feedback.append(f"Remove {paragraph_count - self.guideline.paragraphs_max} paragraphs")
            all_valid = False

        # Images
        if image_count < self.guideline.images_min:
            feedback.append(f"Add {self.guideline.images_min - image_count} more images")
            all_valid = False
        elif image_count > self.guideline.images_max:
            feedback.append(f"Remove {image_count - self.guideline.images_max} images")
            all_valid = False

        return all_valid, feedback

    def _validate_keywords(self, keyword_counts: Dict[str, int]) -> List[ValidationFeedback]:
        """Validate keywords against targets"""
        feedback = []

        for keyword, target_data in self.keyword_targets.items():
            current = keyword_counts.get(keyword, 0)
            target = target_data['target']
            min_val = target_data['min']
            max_val = target_data['max']

            delta = target - current

            # Determine status
            if current < min_val:
                status = "below_min"
                priority = "critical"
            elif current > max_val:
                status = "above_max"
                priority = "critical"
            elif current < target:
                status = "below_target"
                # Calculate how far from target
                distance_pct = abs(delta) / (max_val - min_val) if (max_val - min_val) > 0 else 0
                if distance_pct > 0.5:
                    priority = "high"
                elif distance_pct > 0.25:
                    priority = "medium"
                else:
                    priority = "low"
            elif current > target:
                status = "above_target"
                priority = "low"
            else:
                status = "at_target"
                priority = "optimal"

            # Only add feedback if not optimal
            if status != "at_target" and priority != "optimal":
                feedback.append(ValidationFeedback(
                    keyword=keyword,
                    current=current,
                    target=target,
                    delta=delta,
                    status=status,
                    priority=priority
                ))

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        feedback.sort(key=lambda f: (priority_order.get(f.priority, 99), -abs(f.delta)))

        return feedback

    def _calculate_score(
        self,
        keywords_at_target: int,
        keywords_within_range: int,
        total_keywords: int,
        structure_valid: bool
    ) -> float:
        """Calculate overall score 0-100"""
        if total_keywords == 0:
            keyword_score = 100
        else:
            # 60% weight for being at target, 40% for being in range
            at_target_pct = keywords_at_target / total_keywords
            in_range_pct = keywords_within_range / total_keywords
            keyword_score = (at_target_pct * 60) + (in_range_pct * 40)

        structure_score = 100 if structure_valid else 50

        # Overall: 70% keywords, 30% structure
        overall = (keyword_score * 0.7) + (structure_score * 0.3)

        return round(overall, 2)

    def _generate_summary(
        self,
        keyword_feedback: List[ValidationFeedback],
        structure_feedback: List[str],
        score: float
    ) -> str:
        """Generate concise summary for LLM"""
        critical = [kf for kf in keyword_feedback if kf.priority == "critical"]
        high = [kf for kf in keyword_feedback if kf.priority == "high"]

        parts = []

        if score >= 90:
            parts.append("✓ Excellent")
        elif score >= 75:
            parts.append("✓ Good")
        elif score >= 60:
            parts.append("⚠ Needs improvement")
        else:
            parts.append("✗ Poor")

        if critical:
            parts.append(f"{len(critical)} critical issues")
        if high:
            parts.append(f"{len(high)} high priority")
        if structure_feedback:
            parts.append(f"{len(structure_feedback)} structure issues")

        return " | ".join(parts) if len(parts) > 1 else parts[0]


# Helper function to load from database (example)
def load_guideline_from_database(guideline_id: str) -> StoredGuideline:
    """
    Example: Load pre-computed guideline from database

    In Django:
        guideline = Guideline.objects.get(id=guideline_id)
        return StoredGuideline.from_dict({
            'id': guideline.id,
            'name': guideline.name,
            'created_at': guideline.created_at.isoformat(),
            'paragraphs_min': guideline.paragraphs_min,
            ...
            'keywords_q1': guideline.keywords_q1,
            'keywords_q2': guideline.keywords_q2,
            ...
        })
    """
    # For now, load from JSON file
    from guideline_storage import load_guideline_from_json
    return load_guideline_from_json(f"{guideline_id}.json")
