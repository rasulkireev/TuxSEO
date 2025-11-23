import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


@dataclass
class ContentRequirements:
    """Structured representation of content guidelines"""

    paragraphs: Tuple[int, Optional[int]]  # (min, max) - max can be None for "Infinity"
    images: Tuple[int, int]
    headings: Tuple[int, int]
    characters: Tuple[int, int]
    words: Tuple[int, int]
    important_terms: Dict[str, Tuple[int, int]]  # {term: (min, max)}
    other_terms: List[str]
    questions: List[str]
    notes: str


class GuidelineParser:
    """
    Parses Surfer SEO guideline files and database content
    
    Usage Examples

    # From database text field
    guideline_text = Guideline.objects.get(id=1).content
    pipeline = ContentPipeline(guidelines_source=guideline_text)

    # From Django model
    guideline_model = Guideline.objects.get(id=1)
    pipeline = ContentPipeline(guidelines_source=guideline_model, source_type="model")

    # From JSON field
    guideline_data = Guideline.objects.get(id=1).data
    pipeline = ContentPipeline(guidelines_source=guideline_data)
    """

    def parse_file(self, filepath: str) -> ContentRequirements:
        """Parse the guidelines.txt file into structured requirements"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return self._parse_content(content)

    def parse_from_text(self, text: str) -> ContentRequirements:
        """
        Parse guidelines from raw text string (e.g., from database field).

        Args:
            text: Raw guideline text in the same format as .txt files

        Returns:
            ContentRequirements object
        """
        return self._parse_content(text)

    def parse_from_dict(self, data: Dict) -> ContentRequirements:
        """
        Parse guidelines from structured dictionary/JSON data.

        Args:
            data: Dictionary with keys matching ContentRequirements fields:
                - notes (str)
                - paragraphs (tuple[int, int|None])
                - images (tuple[int, int])
                - headings (tuple[int, int])
                - characters (tuple[int, int])
                - words (tuple[int, int])
                - important_terms (dict[str, tuple[int, int]])
                - other_terms (list[str])
                - questions (list[str])

        Returns:
            ContentRequirements object
        """
        return ContentRequirements(
            notes=data.get("notes", ""),
            paragraphs=tuple(data.get("paragraphs", (0, None))),
            images=tuple(data.get("images", (0, 0))),
            headings=tuple(data.get("headings", (0, 0))),
            characters=tuple(data.get("characters", (0, 0))),
            words=tuple(data.get("words", (0, 0))),
            important_terms=data.get("important_terms", {}),
            other_terms=data.get("other_terms", []),
            questions=data.get("questions", []),
        )

    def parse_from_model(self, model) -> ContentRequirements:
        """
        Parse guidelines from Django model or ORM object.

        Expects the model to have either:
        1. A 'content' or 'text' field with raw guideline text, OR
        2. Individual fields matching ContentRequirements attributes

        Args:
            model: Django model instance or similar ORM object

        Returns:
            ContentRequirements object
        """
        # Try to get raw text field first
        if hasattr(model, "content"):
            return self._parse_content(model.content)
        elif hasattr(model, "text"):
            return self._parse_content(model.text)
        elif hasattr(model, "guideline_text"):
            return self._parse_content(model.guideline_text)

        # Otherwise, try to build from individual fields
        return ContentRequirements(
            notes=getattr(model, "notes", ""),
            paragraphs=self._get_tuple_from_model(model, "paragraphs", (0, None)),
            images=self._get_tuple_from_model(model, "images", (0, 0)),
            headings=self._get_tuple_from_model(model, "headings", (0, 0)),
            characters=self._get_tuple_from_model(model, "characters", (0, 0)),
            words=self._get_tuple_from_model(model, "words", (0, 0)),
            important_terms=getattr(model, "important_terms", {}),
            other_terms=getattr(model, "other_terms", []),
            questions=getattr(model, "questions", []),
        )

    def _parse_content(self, content: str) -> ContentRequirements:
        """
        Internal method to parse raw text content.

        Args:
            content: Raw guideline text

        Returns:
            ContentRequirements object
        """
        return ContentRequirements(
            notes=self._parse_notes(content),
            paragraphs=self._parse_structure_item(content, "Paragraphs"),
            images=self._parse_structure_item(content, "Images"),
            headings=self._parse_structure_item(content, "Headings"),
            characters=self._parse_structure_item(content, "Characters"),
            words=self._parse_structure_item(content, "Words"),
            important_terms=self._parse_important_terms(content),
            other_terms=self._parse_other_terms(content),
            questions=self._parse_questions(content),
        )

    def _get_tuple_from_model(self, model, field_name: str, default: Tuple) -> Tuple:
        """
        Helper to extract tuple from model field.

        Handles cases where field might be:
        - A tuple
        - A string like "5-10"
        - Separate min/max fields like "paragraphs_min", "paragraphs_max"
        """
        # Try direct tuple field
        if hasattr(model, field_name):
            value = getattr(model, field_name)
            if isinstance(value, (tuple, list)) and len(value) >= 2:
                return tuple(value[:2])
            elif isinstance(value, str) and "-" in value:
                # Parse "5-10" format
                parts = value.split("-")
                min_val = int(parts[0].strip())
                max_val = (
                    None
                    if parts[1].strip().lower() == "infinity"
                    else int(parts[1].strip())
                )
                return (min_val, max_val)

        # Try separate min/max fields
        min_field = f"{field_name}_min"
        max_field = f"{field_name}_max"
        if hasattr(model, min_field) and hasattr(model, max_field):
            return (getattr(model, min_field), getattr(model, max_field))

        return default

    def _parse_notes(self, content: str) -> str:
        """Parse notes section"""
        match = re.search(r"## NOTES\n(.*?)(?=##|$)", content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _parse_structure_item(
        self, content: str, item_name: str
    ) -> Tuple[int, Optional[int]]:
        """Parse structure items like 'Paragraphs: 15 - Infinity'"""
        pattern = rf"\* {item_name}: (\d+) - (Infinity|\d+)"
        match = re.search(pattern, content)
        if match:
            min_val = int(match.group(1))
            max_val = None if match.group(2) == "Infinity" else int(match.group(2))
            return (min_val, max_val)
        return (0, None)

    def _parse_important_terms(self, content: str) -> Dict[str, Tuple[int, int]]:
        """Parse important terms with frequency ranges"""
        terms = {}
        section = re.search(
            r"## IMPORTANT TERMS TO USE(.*?)(?=##|$)", content, re.DOTALL
        )
        if section:
            # Match lines like "* hemp shoes: 17 - 53"
            pattern = r"\* (.+?): (\d+) - (\d+)"
            for match in re.finditer(pattern, section.group(1)):
                term = match.group(1).strip()
                min_count = int(match.group(2))
                max_count = int(match.group(3))
                terms[term] = (min_count, max_count)
        return terms

    def _parse_other_terms(self, content: str) -> List[str]:
        """Parse other relevant terms section"""
        section = re.search(r"## OTHER RELEVANT TERMS(.*?)(?=##|$)", content, re.DOTALL)
        if section:
            # Extract bullet points
            terms = re.findall(r"\* (.+)", section.group(1))
            return [t.strip() for t in terms]
        return []

    def _parse_questions(self, content: str) -> List[str]:
        """Parse questions to answer, removing duplicates while preserving order"""
        section = re.search(r"## QUESTIONS TO ANSWER(.*?)$", content, re.DOTALL)
        if section:
            questions = re.findall(r"\* (.+\?)", section.group(1))
            # Remove duplicates while preserving order
            seen = set()
            unique_questions = []
            for q in questions:
                q_clean = q.strip()
                if q_clean not in seen:
                    seen.add(q_clean)
                    unique_questions.append(q_clean)
            return unique_questions
        return []
