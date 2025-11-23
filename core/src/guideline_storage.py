#!/usr/bin/env python3
"""
Guideline Storage Module

Pre-computes guideline data and quartile boundaries ONCE and stores in database.
This data is then reused for fast article validation without re-parsing.

Workflow:
1. Parse guideline file/text ONCE
2. Calculate Q1, Q2, Q3, Q4 boundaries for all keywords ONCE
3. Store in database with Q1, Q2, Q3, Q4 as columns/keys
4. Use cached data for fast validation during LLM article writing
"""

import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from guideline_parser import GuidelineParser, ContentRequirements


@dataclass
class QuartileBoundaries:
    """Pre-computed quartile boundaries for a keyword"""
    keyword: str
    min_required: int
    max_allowed: int

    # Quartile boundaries
    q1: float  # 25th percentile
    q2: float  # 50th percentile (median)
    q3: float  # 75th percentile
    q4: float  # 100th percentile (max)

    # Target counts for each quartile
    q1_target: int
    q2_target: int
    q3_target: int
    q4_target: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'QuartileBoundaries':
        """Create from database dictionary"""
        return cls(**data)


@dataclass
class StoredGuideline:
    """Complete guideline data ready for database storage"""

    # Metadata
    id: Optional[str] = None
    name: str = ""
    created_at: str = ""

    # Content requirements
    paragraphs_min: int = 0
    paragraphs_max: Optional[int] = None
    images_min: int = 0
    images_max: int = 0
    headings_min: int = 0
    headings_max: int = 0
    characters_min: int = 0
    characters_max: int = 0
    words_min: int = 0
    words_max: int = 0

    # Keywords with quartile data
    # Each keyword has: {keyword: {min, max, q1, q2, q3, q4, q1_target, q2_target, q3_target, q4_target}}
    keywords_q1: Dict[str, Dict] = None
    keywords_q2: Dict[str, Dict] = None
    keywords_q3: Dict[str, Dict] = None
    keywords_q4: Dict[str, Dict] = None

    # Other data
    other_terms: List[str] = None
    questions: List[str] = None
    notes: str = ""

    def __post_init__(self):
        if self.keywords_q1 is None:
            self.keywords_q1 = {}
        if self.keywords_q2 is None:
            self.keywords_q2 = {}
        if self.keywords_q3 is None:
            self.keywords_q3 = {}
        if self.keywords_q4 is None:
            self.keywords_q4 = {}
        if self.other_terms is None:
            self.other_terms = []
        if self.questions is None:
            self.questions = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/database storage"""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict) -> 'StoredGuideline':
        """Create from database dictionary"""
        return cls(**data)


class GuidelinePreprocessor:
    """
    Pre-processes guidelines ONCE for storage in database.
    Calculates all quartile boundaries and targets upfront.
    """

    def process_guideline(
        self,
        guideline_source,
        guideline_name: str = "default",
        guideline_id: Optional[str] = None
    ) -> StoredGuideline:
        """
        Process guideline file/text/model and prepare for database storage.

        Args:
            guideline_source: File path, text, dict, or model
            guideline_name: Name for this guideline
            guideline_id: Optional ID for database

        Returns:
            StoredGuideline object ready for database storage
        """
        # Parse guideline
        parser = GuidelineParser()

        if isinstance(guideline_source, str):
            # Check if file or text
            if '\n' not in guideline_source and guideline_source.endswith('.txt'):
                requirements = parser.parse_file(guideline_source)
            else:
                requirements = parser.parse_from_text(guideline_source)
        elif isinstance(guideline_source, dict):
            requirements = parser.parse_from_dict(guideline_source)
        elif isinstance(guideline_source, ContentRequirements):
            requirements = guideline_source
        else:
            requirements = parser.parse_from_model(guideline_source)

        # Calculate quartile boundaries for all keywords
        keywords_q1, keywords_q2, keywords_q3, keywords_q4 = self._calculate_all_quartiles(
            requirements.important_terms
        )

        # Create stored guideline
        stored = StoredGuideline(
            id=guideline_id or f"guideline_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=guideline_name,
            created_at=datetime.now().isoformat(),
            paragraphs_min=requirements.paragraphs[0],
            paragraphs_max=requirements.paragraphs[1],
            images_min=requirements.images[0],
            images_max=requirements.images[1],
            headings_min=requirements.headings[0],
            headings_max=requirements.headings[1],
            characters_min=requirements.characters[0],
            characters_max=requirements.characters[1],
            words_min=requirements.words[0],
            words_max=requirements.words[1],
            keywords_q1=keywords_q1,
            keywords_q2=keywords_q2,
            keywords_q3=keywords_q3,
            keywords_q4=keywords_q4,
            other_terms=requirements.other_terms,
            questions=requirements.questions,
            notes=requirements.notes
        )

        return stored

    def _calculate_all_quartiles(
        self,
        important_terms: Dict[str, Tuple[int, int]]
    ) -> Tuple[Dict, Dict, Dict, Dict]:
        """
        Calculate quartile boundaries and targets for all keywords.

        Returns:
            Tuple of (keywords_q1, keywords_q2, keywords_q3, keywords_q4)
            Each is a dict: {keyword: {min, max, boundary, target}}
        """
        keywords_q1 = {}
        keywords_q2 = {}
        keywords_q3 = {}
        keywords_q4 = {}

        for keyword, (min_req, max_req) in important_terms.items():
            range_span = max_req - min_req

            if range_span == 0:
                # Edge case: min == max
                q1 = q2 = q3 = q4 = min_req
                q1_target = q2_target = q3_target = q4_target = min_req
            else:
                # Calculate quartile boundaries
                q1 = min_req + (range_span * 0.25)
                q2 = min_req + (range_span * 0.50)  # Median
                q3 = min_req + (range_span * 0.75)
                q4 = max_req

                # Calculate target values for each quartile
                # Q1: Target midpoint of Q1 zone (12.5th percentile)
                q1_target = int(round(min_req + (range_span * 0.125)))

                # Q2: Target midpoint between Q1 and Q2 (37.5th percentile)
                q2_target = int(round(min_req + (range_span * 0.375)))

                # Q3: Target midpoint between Q2 and Q3 (62.5th percentile)
                q3_target = int(round(min_req + (range_span * 0.625)))

                # Q4: Target midpoint between Q3 and Q4 (87.5th percentile)
                q4_target = int(round(min_req + (range_span * 0.875)))

            # Store Q1 data
            keywords_q1[keyword] = {
                'min': min_req,
                'max': max_req,
                'boundary': q1,
                'target': q1_target
            }

            # Store Q2 data
            keywords_q2[keyword] = {
                'min': min_req,
                'max': max_req,
                'boundary': q2,
                'target': q2_target
            }

            # Store Q3 data
            keywords_q3[keyword] = {
                'min': min_req,
                'max': max_req,
                'boundary': q3,
                'target': q3_target
            }

            # Store Q4 data
            keywords_q4[keyword] = {
                'min': min_req,
                'max': max_req,
                'boundary': q4,
                'target': q4_target
            }

        return keywords_q1, keywords_q2, keywords_q3, keywords_q4


# Database helper functions (work with any database)

def save_guideline_to_json(stored_guideline: StoredGuideline, filepath: str):
    """
    Save pre-computed guideline to JSON file.
    Can also be stored in database JSON field.

    Args:
        stored_guideline: Processed guideline data
        filepath: Path to save JSON
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(stored_guideline.to_json())

    print(f"✓ Saved guideline to: {filepath}")


def load_guideline_from_json(filepath: str) -> StoredGuideline:
    """
    Load pre-computed guideline from JSON file.

    Args:
        filepath: Path to JSON file

    Returns:
        StoredGuideline object
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return StoredGuideline.from_dict(data)


def save_guideline_to_database_dict(stored_guideline: StoredGuideline) -> Dict:
    """
    Convert StoredGuideline to dictionary format suitable for database.

    For Django, you can use this with JSONField:
        Guideline.objects.create(
            name=data['name'],
            data=data,  # JSONField
            keywords_q1=data['keywords_q1'],  # JSONField
            keywords_q2=data['keywords_q2'],  # JSONField
            ...
        )

    Args:
        stored_guideline: Processed guideline data

    Returns:
        Dictionary ready for database storage
    """
    return stored_guideline.to_dict()


# Example Django model structure (for reference)
"""
# models.py

from django.db import models

class Guideline(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    # Structure requirements
    paragraphs_min = models.IntegerField()
    paragraphs_max = models.IntegerField(null=True, blank=True)
    images_min = models.IntegerField()
    images_max = models.IntegerField()
    headings_min = models.IntegerField()
    headings_max = models.IntegerField()
    characters_min = models.IntegerField()
    characters_max = models.IntegerField()
    words_min = models.IntegerField()
    words_max = models.IntegerField()

    # Pre-computed quartile data (JSON fields)
    keywords_q1 = models.JSONField()  # {keyword: {min, max, boundary, target}}
    keywords_q2 = models.JSONField()
    keywords_q3 = models.JSONField()
    keywords_q4 = models.JSONField()

    # Other data
    other_terms = models.JSONField(default=list)
    questions = models.JSONField(default=list)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name
"""


# Usage examples

def example_preprocess_and_save():
    """
    Example: Preprocess guideline ONCE and save to database
    """
    print("=" * 70)
    print("EXAMPLE: PREPROCESS GUIDELINE FOR DATABASE STORAGE")
    print("=" * 70)

    # Sample guideline text
    guideline_text = """## CONTENT STRUCTURE
* Paragraphs: 5 - 15
* Images: 2 - 5
* Headings: 3 - 10
* Characters: 1000 - 3000
* Words: 200 - 600

## IMPORTANT TERMS TO USE
* hemp shoes: 5 - 15
* sustainable footwear: 3 - 10
* eco-friendly: 2 - 8

## QUESTIONS TO ANSWER
* Are hemp shoes durable?
* How to clean hemp shoes?
"""

    # Step 1: Preprocess guideline
    print("\n📝 Step 1: Preprocessing guideline...")
    preprocessor = GuidelinePreprocessor()
    stored = preprocessor.process_guideline(
        guideline_source=guideline_text,
        guideline_name="Hemp Shoes SEO Guide",
        guideline_id="hemp_shoes_001"
    )

    print(f"✓ Processed guideline: {stored.name}")
    print(f"✓ Keywords with Q1 data: {len(stored.keywords_q1)}")
    print(f"✓ Keywords with Q2 data: {len(stored.keywords_q2)}")
    print(f"✓ Keywords with Q3 data: {len(stored.keywords_q3)}")
    print(f"✓ Keywords with Q4 data: {len(stored.keywords_q4)}")

    # Step 2: Show quartile data for one keyword
    print("\n📊 Step 2: Sample quartile data for 'hemp shoes':")
    print(f"   Q1 (Conservative): {stored.keywords_q1['hemp shoes']}")
    print(f"   Q2 (Median):       {stored.keywords_q2['hemp shoes']}")
    print(f"   Q3 (Recommended):  {stored.keywords_q3['hemp shoes']}")
    print(f"   Q4 (Aggressive):   {stored.keywords_q4['hemp shoes']}")

    # Step 3: Save to JSON (simulates database storage)
    print("\n💾 Step 3: Saving to JSON (simulates database)...")
    save_guideline_to_json(stored, "guideline_preprocessed.json")

    # Step 4: Show database format
    print("\n📦 Step 4: Database-ready format:")
    db_dict = save_guideline_to_database_dict(stored)
    print(f"   Fields ready for database: {list(db_dict.keys())}")

    return stored


if __name__ == "__main__":
    example_preprocess_and_save()
