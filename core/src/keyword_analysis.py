import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from guideline_parser import ContentRequirements


@dataclass
class ValidationResult:
    """Result of a validation check"""

    passed: bool
    metric_name: str
    current_value: any
    expected_range: Tuple[any, any]
    feedback: str
    details: str = ""  # Additional context


@dataclass
class KeywordAnalysis:
    """Detailed analysis of keyword usage"""

    keyword: str
    total_count: int
    standalone_count: int
    compound_count: int
    compound_sources: Dict[str, int]
    min_required: int
    max_allowed: int
    is_compound: bool
    passes: bool
    feedback: str


class SmartKeywordCounter:
    """
    Handles overlapping keywords intelligently using hierarchical matching.
    """

    def __init__(self, keyword_requirements: Dict[str, Tuple[int, int]]):
        self.requirements = keyword_requirements
        # Sort by word count (descending), then by length
        self.sorted_keywords = sorted(
            keyword_requirements.keys(),
            key=lambda k: (len(k.split()), len(k)),
            reverse=True,
        )

    def analyze_keywords(self, content: str) -> List[KeywordAnalysis]:
        """Analyze all keywords with overlap awareness."""
        content_lower = content.lower()

        # Step 1: Mark all matched positions for each keyword
        keyword_positions = {}
        for keyword in self.sorted_keywords:
            positions = self._find_all_positions(content_lower, keyword.lower())
            keyword_positions[keyword] = positions

        # Step 2: Build hierarchy
        hierarchy = self._build_hierarchy()

        # Step 3: Calculate standalone vs compound counts
        analyses = []
        for keyword in self.sorted_keywords:
            analysis = self._analyze_single_keyword(
                keyword, keyword_positions, hierarchy, content_lower
            )
            analyses.append(analysis)

        return analyses

    def _find_all_positions(self, content: str, keyword: str) -> List[Tuple[int, int]]:
        """Find all (start, end) positions of keyword in content"""
        positions = []
        pattern = r"\b" + re.escape(keyword) + r"\b"
        for match in re.finditer(pattern, content):
            positions.append((match.start(), match.end()))
        return positions

    def _build_hierarchy(self) -> Dict[str, List[str]]:
        """Build parent-child relationships."""
        hierarchy = {kw: [] for kw in self.sorted_keywords}

        for i, keyword in enumerate(self.sorted_keywords):
            for parent in self.sorted_keywords[:i]:
                if keyword.lower() in parent.lower():
                    hierarchy[keyword].append(parent)

        return hierarchy

    def _positions_overlap(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> bool:
        """Check if two position ranges overlap"""
        return not (pos1[1] <= pos2[0] or pos2[1] <= pos1[0])

    def _analyze_single_keyword(
        self,
        keyword: str,
        all_positions: Dict[str, List[Tuple[int, int]]],
        hierarchy: Dict[str, List[str]],
        content: str,
    ) -> KeywordAnalysis:
        """Analyze a single keyword considering its context"""

        my_positions = all_positions[keyword]
        total_count = len(my_positions)

        compound_sources = {}
        compound_positions = set()

        parent_keywords = hierarchy[keyword]
        for parent in parent_keywords:
            parent_positions = all_positions[parent]
            overlap_count = 0

            for my_pos in my_positions:
                for parent_pos in parent_positions:
                    if self._positions_overlap(my_pos, parent_pos):
                        overlap_count += 1
                        compound_positions.add(my_pos)
                        break

            if overlap_count > 0:
                compound_sources[parent] = overlap_count

        compound_count = len(compound_positions)
        standalone_count = total_count - compound_count

        min_req, max_req = self.requirements[keyword]
        is_compound = len(keyword.split()) > 1

        passes, feedback = self._generate_smart_feedback(
            keyword=keyword,
            total_count=total_count,
            standalone_count=standalone_count,
            compound_count=compound_count,
            compound_sources=compound_sources,
            min_required=min_req,
            max_allowed=max_req,
            is_compound=is_compound,
            parent_keywords=parent_keywords,
        )

        return KeywordAnalysis(
            keyword=keyword,
            total_count=total_count,
            standalone_count=standalone_count,
            compound_count=compound_count,
            compound_sources=compound_sources,
            min_required=min_req,
            max_allowed=max_req,
            is_compound=is_compound,
            passes=passes,
            feedback=feedback,
        )

    def _generate_smart_feedback(
        self,
        keyword: str,
        total_count: int,
        standalone_count: int,
        compound_count: int,
        compound_sources: Dict[str, int],
        min_required: int,
        max_allowed: int,
        is_compound: bool,
        parent_keywords: List[str],
    ) -> Tuple[bool, str]:
        """Generate intelligent feedback considering keyword relationships."""

        # For compound phrases (multi-word), count total occurrences
        if is_compound:
            passes = min_required <= total_count <= max_allowed

            if not passes:
                if total_count < min_required:
                    deficit = min_required - total_count
                    feedback = f"Use '{keyword}' {deficit} more times (current: {total_count}, required: {min_required}-{max_allowed})"
                else:
                    excess = total_count - max_allowed
                    feedback = f"Reduce '{keyword}' by {excess} occurrences (current: {total_count}, max: {max_allowed})"
            else:
                feedback = ""

            return passes, feedback

        # For single words that are part of compound phrases
        if parent_keywords:
            passes = min_required <= total_count <= max_allowed

            if not passes:
                if total_count < min_required:
                    deficit = min_required - total_count

                    compound_info = ", ".join(
                        [
                            f"'{p}' ({compound_sources.get(p, 0)}x)"
                            for p in parent_keywords
                        ]
                    )

                    feedback = (
                        f"Use '{keyword}' {deficit} more times. "
                        f"Currently: {total_count} total ({standalone_count} standalone + "
                        f"{compound_count} in phrases like {compound_info}). "
                        f"Required: {min_required}-{max_allowed}. "
                        f"💡 Tip: Using parent phrases like '{parent_keywords[0]}' will also count towards '{keyword}'."
                    )
                else:
                    excess = total_count - max_allowed
                    feedback = (
                        f"Reduce '{keyword}' by {excess} occurrences. "
                        f"Currently: {total_count} total (max: {max_allowed})"
                    )
            else:
                feedback = ""

            return passes, feedback

        # For standalone single words (no parent phrases)
        passes = min_required <= total_count <= max_allowed

        if not passes:
            if total_count < min_required:
                deficit = min_required - total_count
                feedback = f"Use '{keyword}' {deficit} more times (current: {total_count}, required: {min_required}-{max_allowed})"
            else:
                excess = total_count - max_allowed
                feedback = f"Reduce '{keyword}' by {excess} occurrences (current: {total_count}, max: {max_allowed})"
        else:
            feedback = ""

        return passes, feedback

    def get_optimization_strategy(self, analyses: List[KeywordAnalysis]) -> str:
        """Generate strategic guidance for meeting all requirements."""
        failed = [a for a in analyses if not a.passes]

        if not failed:
            return "✅ All keyword requirements met!"

        strategy_lines = ["📊 KEYWORD OPTIMIZATION STRATEGY:", ""]

        compound_phrases = [a for a in failed if a.is_compound]
        single_words_with_parents = [
            a for a in failed if not a.is_compound and a.compound_sources
        ]
        standalone_words = [
            a for a in failed if not a.is_compound and not a.compound_sources
        ]

        if compound_phrases:
            strategy_lines.append("🎯 Priority 1: Compound Phrases")
            strategy_lines.append(
                "   (These will also help with single-word requirements)"
            )
            for a in compound_phrases:
                if a.total_count < a.min_required:
                    strategy_lines.append(f"   • {a.feedback}")
            strategy_lines.append("")

        words_needing_more = [
            a for a in single_words_with_parents if a.total_count < a.min_required
        ]
        if words_needing_more:
            strategy_lines.append("🎯 Priority 2: Single Words Needing More Usage")
            for a in words_needing_more:
                parents = list(a.compound_sources.keys())
                strategy_lines.append(
                    f"   • '{a.keyword}': needs {a.min_required - a.total_count} more "
                    f"(consider using '{parents[0]}' to boost this count)"
                )
            strategy_lines.append("")

        if standalone_words:
            strategy_lines.append("🎯 Priority 3: Standalone Words")
            for a in standalone_words:
                strategy_lines.append(f"   • {a.feedback}")
            strategy_lines.append("")

        words_exceeding = [a for a in failed if a.total_count > a.max_allowed]
        if words_exceeding:
            strategy_lines.append("⚠️  Reduce Usage:")
            for a in words_exceeding:
                strategy_lines.append(f"   • {a.feedback}")

        return "\n".join(strategy_lines)


class ImprovedArticleValidator:
    """
    Enhanced validator with smart keyword counting and comprehensive validations.
    Features:
    - Smart keyword counting (handles overlapping keywords)
    - Accumulated heading counts (H1-H6 all count equally)
    - Paragraph, image, character, word count validation
    - Question answering validation
    """

    def __init__(self, requirements: ContentRequirements):
        self.requirements = requirements
        self.keyword_counter = SmartKeywordCounter(requirements.important_terms)

    def validate_all(self, content: str) -> Dict[str, any]:
        """Run all validation checks"""
        return {
            "structure": self.validate_structure(content),
            "important_terms": self.validate_important_terms(content),
            "questions": self.validate_questions_answered(content),
        }

    def validate_structure(self, content: str) -> Dict[str, ValidationResult]:
        """Validate all structural elements"""
        return {
            "paragraphs": self.validate_paragraphs(content),
            "images": self.validate_images(content),
            "headings": self.validate_headings(content),
            "characters": self.validate_characters(content),
            "words": self.validate_words(content),
        }

    def validate_paragraphs(self, content: str) -> ValidationResult:
        """Count paragraphs (separated by double newlines or <p> tags)"""
        if "<p>" in content:
            count = content.count("<p>")
        else:
            # Split by double newlines, filter out headings and empty lines
            lines = content.split("\n")
            paragraphs = []
            current_para = []

            for line in lines:
                stripped = line.strip()
                # Skip empty lines and headings
                if (
                    not stripped
                    or stripped.startswith("#")
                    or re.match(r"^<h[1-6]", stripped)
                ):
                    if current_para:
                        paragraphs.append(" ".join(current_para))
                        current_para = []
                else:
                    current_para.append(stripped)

            if current_para:
                paragraphs.append(" ".join(current_para))

            count = len(paragraphs)

        min_val, max_val = self.requirements.paragraphs
        passed = count >= min_val and (max_val is None or count <= max_val)

        feedback = ""
        details = f"Counted {count} paragraphs"

        if not passed:
            if count < min_val:
                feedback = f"Add {min_val - count} more paragraphs (current: {count}, required: {min_val}+)"
            elif max_val and count > max_val:
                feedback = f"Remove {count - max_val} paragraphs (current: {count}, max: {max_val})"

        return ValidationResult(
            passed=passed,
            metric_name="Paragraphs",
            current_value=count,
            expected_range=(min_val, max_val),
            feedback=feedback,
            details=details,
        )

    def validate_images(self, content: str) -> ValidationResult:
        """Count image placeholders"""
        # Count various image formats
        markdown_imgs = len(re.findall(r"!\[.*?\]\(.*?\)", content))
        html_imgs = len(re.findall(r"<img[^>]*>", content, re.IGNORECASE))
        placeholder_imgs = len(re.findall(r"\[IMAGE:.*?\]", content, re.IGNORECASE))

        img_count = markdown_imgs + html_imgs + placeholder_imgs

        min_val, max_val = self.requirements.images
        passed = min_val <= img_count <= max_val

        feedback = ""
        details = f"Found {markdown_imgs} markdown, {html_imgs} HTML, {placeholder_imgs} placeholder images"

        if not passed:
            if img_count < min_val:
                feedback = f"Add {min_val - img_count} more image placeholders (current: {img_count}, required: {min_val}-{max_val})"
            else:
                feedback = f"Remove {img_count - max_val} image placeholders (current: {img_count}, max: {max_val})"

        return ValidationResult(
            passed=passed,
            metric_name="Images",
            current_value=img_count,
            expected_range=(min_val, max_val),
            feedback=feedback,
            details=details,
        )

    def validate_headings(self, content: str) -> ValidationResult:
        """
        Count ALL heading levels (H1-H6) accumulated.
        Each heading increases the count by 1, regardless of level.
        """
        # Count markdown headings (# ## ### #### ##### ######)
        md_headings = re.findall(r"^\s*#{1,6}\s+.+$", content, re.MULTILINE)

        # Count HTML headings (<h1> through <h6>)
        html_headings = re.findall(
            r"<h[1-6][^>]*>.*?</h[1-6]>", content, re.IGNORECASE | re.DOTALL
        )

        total_count = len(md_headings) + len(html_headings)

        # Break down by level for details
        heading_breakdown = {}

        # Markdown headings breakdown
        for heading in md_headings:
            level = len(heading.split()[0])  # Count # symbols
            heading_breakdown[f"H{level}"] = heading_breakdown.get(f"H{level}", 0) + 1

        # HTML headings breakdown
        for heading in html_headings:
            match = re.match(r"<h([1-6])", heading, re.IGNORECASE)
            if match:
                level = match.group(1)
                heading_breakdown[f"H{level}"] = (
                    heading_breakdown.get(f"H{level}", 0) + 1
                )

        min_val, max_val = self.requirements.headings
        passed = min_val <= total_count <= max_val

        feedback = ""
        breakdown_str = ", ".join(
            [f"{k}:{v}" for k, v in sorted(heading_breakdown.items())]
        )
        details = f"Total headings: {total_count} ({breakdown_str})"

        if not passed:
            if total_count < min_val:
                deficit = min_val - total_count
                feedback = f"Add {deficit} more headings of any level (H2, H3, etc.) (current: {total_count}, required: {min_val}-{max_val})"
            else:
                excess = total_count - max_val
                feedback = (
                    f"Remove {excess} headings (current: {total_count}, max: {max_val})"
                )

        return ValidationResult(
            passed=passed,
            metric_name="Headings (All Levels)",
            current_value=total_count,
            expected_range=(min_val, max_val),
            feedback=feedback,
            details=details,
        )

    def validate_characters(self, content: str) -> ValidationResult:
        """Count total characters (excluding HTML tags)"""
        # Remove HTML tags
        clean_content = re.sub(r"<[^>]+>", "", content)
        # Remove markdown image syntax
        clean_content = re.sub(r"!\[.*?\]\(.*?\)", "", clean_content)
        # Remove image placeholders
        clean_content = re.sub(r"\[IMAGE:.*?\]", "", clean_content, flags=re.IGNORECASE)

        char_count = len(clean_content)

        min_val, max_val = self.requirements.characters
        passed = min_val <= char_count <= max_val

        feedback = ""
        details = f"Character count (excluding markup): {char_count}"

        if not passed:
            if char_count < min_val:
                deficit = min_val - char_count
                feedback = f"Add approximately {deficit} more characters (current: {char_count}, required: {min_val}-{max_val})"
            else:
                excess = char_count - max_val
                feedback = f"Remove approximately {excess} characters (current: {char_count}, max: {max_val})"

        return ValidationResult(
            passed=passed,
            metric_name="Characters",
            current_value=char_count,
            expected_range=(min_val, max_val),
            feedback=feedback,
            details=details,
        )

    def validate_words(self, content: str) -> ValidationResult:
        """Count total words"""
        # Remove HTML tags
        clean_content = re.sub(r"<[^>]+>", "", content)
        # Remove markdown and placeholder images
        clean_content = re.sub(r"!\[.*?\]\(.*?\)", "", clean_content)
        clean_content = re.sub(r"\[IMAGE:.*?\]", "", clean_content, flags=re.IGNORECASE)

        # Count words
        words = re.findall(r"\b\w+\b", clean_content)
        word_count = len(words)

        min_val, max_val = self.requirements.words
        passed = min_val <= word_count <= max_val

        feedback = ""
        details = f"Word count: {word_count}"

        if not passed:
            if word_count < min_val:
                deficit = min_val - word_count
                feedback = f"Add {deficit} more words (current: {word_count}, required: {min_val}-{max_val})"
            else:
                excess = word_count - max_val
                feedback = (
                    f"Remove {excess} words (current: {word_count}, max: {max_val})"
                )

        return ValidationResult(
            passed=passed,
            metric_name="Words",
            current_value=word_count,
            expected_range=(min_val, max_val),
            feedback=feedback,
            details=details,
        )

    def validate_important_terms(self, content: str) -> List[ValidationResult]:
        """Validate keywords with overlap awareness"""
        analyses = self.keyword_counter.analyze_keywords(content)

        results = []
        for analysis in analyses:
            detail_parts = [f"Total: {analysis.total_count}"]
            if analysis.compound_count > 0:
                detail_parts.append(f"Standalone: {analysis.standalone_count}")
                detail_parts.append(f"In compounds: {analysis.compound_count}")
                if analysis.compound_sources:
                    sources = ", ".join(
                        [f"{k}({v})" for k, v in analysis.compound_sources.items()]
                    )
                    detail_parts.append(f"Sources: {sources}")

            results.append(
                ValidationResult(
                    passed=analysis.passes,
                    metric_name=f"Term: '{analysis.keyword}'",
                    current_value=analysis.total_count,
                    expected_range=(analysis.min_required, analysis.max_allowed),
                    feedback=analysis.feedback,
                    details=" | ".join(detail_parts),
                )
            )

        return results

    def validate_questions_answered(self, content: str) -> List[ValidationResult]:
        """Check if questions are answered in content"""
        content_lower = content.lower()
        results = []

        for question in self.requirements.questions:
            # Extract key terms from question
            question_lower = question.lower()
            # Remove common question words
            for qword in [
                "is",
                "are",
                "can",
                "does",
                "do",
                "what",
                "how",
                "why",
                "where",
                "when",
                "a",
                "the",
                "?",
            ]:
                question_lower = question_lower.replace(qword, " ")

            key_terms = [w for w in question_lower.split() if len(w) > 3]

            # Check if key terms appear in content
            matches = sum(1 for term in key_terms if term in content_lower)
            match_percentage = (matches / len(key_terms) * 100) if key_terms else 0
            passed = matches >= len(key_terms) * 0.6  # At least 60% of key terms

            feedback = "" if passed else f"Address question: '{question}'"
            details = (
                f"Key terms found: {matches}/{len(key_terms)} ({match_percentage:.0f}%)"
            )

            results.append(
                ValidationResult(
                    passed=passed,
                    metric_name=f"Q: {question[:50]}{'...' if len(question) > 50 else ''}",
                    current_value=f"{matches}/{len(key_terms)} terms",
                    expected_range=("60%+", "100%"),
                    feedback=feedback,
                    details=details,
                )
            )

        return results

    def get_keyword_optimization_strategy(self, content: str) -> str:
        """Get strategic guidance for keyword optimization"""
        analyses = self.keyword_counter.analyze_keywords(content)
        return self.keyword_counter.get_optimization_strategy(analyses)

    def get_summary(self, validation_results: Dict) -> Dict[str, any]:
        """Generate validation summary statistics"""
        all_results = []

        # Flatten structure results
        if "structure" in validation_results:
            all_results.extend(validation_results["structure"].values())

        # Add keyword results
        if "important_terms" in validation_results:
            all_results.extend(validation_results["important_terms"])

        # Add question results
        if "questions" in validation_results:
            all_results.extend(validation_results["questions"])

        total = len(all_results)
        passed = sum(1 for r in all_results if r.passed)
        failed = total - passed

        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "all_passed": failed == 0,
        }

    def get_failed_checks(self, validation_results: Dict) -> List[ValidationResult]:
        """Get list of all failed validation checks"""
        all_results = []

        if "structure" in validation_results:
            all_results.extend(validation_results["structure"].values())

        if "important_terms" in validation_results:
            all_results.extend(validation_results["important_terms"])

        if "questions" in validation_results:
            all_results.extend(validation_results["questions"])

        return [r for r in all_results if not r.passed]
