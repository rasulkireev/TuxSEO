#!/usr/bin/env python3
"""
Complete Content Creation and Validation Pipeline - LLM-Optimized Version

Features:
- Configurable quartile targets
- Structured JSON output for LLM consumption
- Agent-friendly feedback format
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
import json
from quartile_action_generator import QuartileActionGenerator, QuartileTarget as QTarget



from guideline_parser import GuidelineParser, ContentRequirements
from keyword_analysis import ImprovedArticleValidator, ValidationResult
from quartile_analyzer import (
    KeywordQuartileAnalyzer, 
    QuartileMetrics, 
)


class QuartileTarget(Enum):
    """Target quartile zones for optimization"""
    Q1_MINIMUM = "Q1" 
    Q2_MEDIAN = "Q2"  # Target median (50th percentile)
    Q3_UPPER = "Q3"   # Target 75th percentile (recommended)
    Q4_MAX = "Q4"     # Target 90th percentile (aggressive)


@dataclass
class StructuredFeedback:
    """Single structured feedback item for LLM"""
    priority: str  # "critical", "high", "medium", "low"
    category: str  # "keyword", "structure", "question"
    action: str    # "add", "remove", "modify", "answer"
    target: str    # What to act on (e.g., "hemp shoes")
    current_value: Any
    target_value: Any
    adjustment: int  # Numeric adjustment needed
    instruction: str  # Natural language instruction
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class StructuredValidationResult:
    """Structured validation result for LLM consumption"""
    metric_name: str
    category: str  # "structure", "keyword", "question"
    passed: bool
    current_value: Any
    expected_min: Any
    expected_max: Any
    details: str
    feedback: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class StructuredQuartileMetrics:
    """Structured quartile metrics for LLM consumption"""
    keyword: str
    current_count: int
    min_required: int
    max_allowed: int
    target_count: int
    adjustment_needed: int
    
    # Quartile info
    current_zone: str  # "Q1", "Q2", "Q3", "Q4", "BELOW", "ABOVE"
    percentile: float
    health_score: float
    priority: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"
    
    # Status
    is_within_range: bool
    is_optimal: bool
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class PipelineOutput:
    """Complete pipeline output - structured for LLM"""
    
    # Metadata
    timestamp: str
    guideline_file: str
    article_file: str
    content_length: int
    
    # Overall status
    all_passed: bool
    overall_quality_score: float  # 0-100
    overall_status: str  # "EXCELLENT", "GOOD", "NEEDS_IMPROVEMENT", "POOR"
    
    # Summary statistics
    validation_summary: Dict[str, Any]
    quartile_summary: Dict[str, Any]
    
    # Detailed results (for LLM to parse)
    validation_results: List[StructuredValidationResult]
    quartile_metrics: List[StructuredQuartileMetrics]
    
    # Actionable feedback (prioritized)
    feedback: List[StructuredFeedback]
    
    # Estimated revision time
    estimated_revision_minutes: int
    
    def to_dict(self) -> Dict:
        """Convert entire output to dictionary for JSON serialization"""
        return {
            "metadata": {
                "timestamp": self.timestamp,
                "guideline_file": self.guideline_file,
                "article_file": self.article_file,
                "content_length": self.content_length
            },
            "status": {
                "all_passed": self.all_passed,
                "overall_quality_score": self.overall_quality_score,
                "overall_status": self.overall_status,
                "estimated_revision_minutes": self.estimated_revision_minutes
            },
            "summary": {
                "validation": self.validation_summary,
                "quartile": self.quartile_summary
            },
            "results": {
                "validation": [r.to_dict() for r in self.validation_results],
                "quartile_metrics": [m.to_dict() for m in self.quartile_metrics]
            },
            "feedback": [f.to_dict() for f in self.feedback]
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)


class ContentPipeline:
    """
    End-to-end content creation and validation pipeline.
    Optimized for LLM agent consumption with structured outputs.
    Supports multiple input sources: file, database text, Django model, or ContentRequirements object.
    """

    def __init__(
        self,
        guidelines_source,
        quartile_target: QuartileTarget = QuartileTarget.Q3_UPPER,
        verbose: bool = True,
        source_type: str = "auto"
    ):
        """
        Initialize pipeline with guidelines from various sources.

        Args:
            guidelines_source: Can be:
                - str: File path OR raw guideline text (detected automatically)
                - dict: Structured guideline data
                - Django model: ORM object with guideline fields
                - ContentRequirements: Pre-parsed requirements object
            quartile_target: Target quartile zone for optimization (Q2/Q3/Q4)
            verbose: Whether to print progress messages
            source_type: Type of source - "auto" (detect), "file", "text", "dict", "model", "requirements"
        """
        self.quartile_target = quartile_target
        self.verbose = verbose
        self.guidelines_file = None  # Will be set if source is a file

        # Parse guidelines based on source type
        self._log("📄 Parsing guidelines...")
        self.parser = GuidelineParser()
        self.requirements = self._parse_guidelines(guidelines_source, source_type)

        self._log(f"✓ Parsed {len(self.requirements.important_terms)} keywords, "
                 f"{len(self.requirements.questions)} questions")

        # Initialize components
        self.validator = ImprovedArticleValidator(self.requirements)
        self.quartile_analyzer = KeywordQuartileAnalyzer(self.requirements.important_terms)

        self._log(f"✓ Quartile target set to: {quartile_target.value}")
        self._log("✓ Pipeline initialized\n")

    def _parse_guidelines(self, source, source_type: str) -> ContentRequirements:
        """
        Parse guidelines from various source types.

        Args:
            source: The guideline source (file path, text, dict, model, or ContentRequirements)
            source_type: Type of source ("auto", "file", "text", "dict", "model", "requirements")

        Returns:
            ContentRequirements object
        """
        # If already a ContentRequirements object, return it
        if isinstance(source, ContentRequirements):
            return source

        # Auto-detect source type if requested
        if source_type == "auto":
            source_type = self._detect_source_type(source)

        # Parse based on type
        if source_type == "file":
            self.guidelines_file = str(source)
            return self.parser.parse_file(str(source))

        elif source_type == "text":
            return self.parser.parse_from_text(source)

        elif source_type == "dict":
            return self.parser.parse_from_dict(source)

        elif source_type == "model":
            return self.parser.parse_from_model(source)

        elif source_type == "requirements":
            return source

        else:
            raise ValueError(
                f"Unknown source_type: {source_type}. "
                f"Use 'auto', 'file', 'text', 'dict', 'model', or 'requirements'"
            )

    def _detect_source_type(self, source) -> str:
        """
        Auto-detect the type of guideline source.

        Args:
            source: The guideline source

        Returns:
            Detected source type string
        """
        # Check if ContentRequirements object
        if isinstance(source, ContentRequirements):
            return "requirements"

        # Check if dictionary
        if isinstance(source, dict):
            return "dict"

        # Check if string
        if isinstance(source, str):
            # Check if it looks like a file path
            if '\n' not in source and (
                source.endswith('.txt') or
                source.endswith('.md') or
                '/' in source or
                '\\' in source
            ):
                # Verify file exists
                from pathlib import Path
                if Path(source).is_file():
                    return "file"

            # If contains newlines or doesn't look like a path, treat as raw text
            # Also check for guideline markers
            if '\n' in source or '##' in source:
                return "text"

            # Last resort: try as file path
            from pathlib import Path
            if Path(source).is_file():
                return "file"
            else:
                # Assume raw text
                return "text"

        # If has attributes (model object)
        if hasattr(source, '__dict__') or hasattr(source, 'content') or hasattr(source, 'text'):
            return "model"

        raise ValueError(
            f"Cannot auto-detect source type for: {type(source)}. "
            f"Please specify source_type explicitly."
        )
    
    def _log(self, message: str):
        """Print log message if verbose mode enabled"""
        if self.verbose:
            print(message)
    
    def analyze_article(self, article_file: str) -> PipelineOutput:
        """
        Run complete analysis on an article.
        
        Args:
            article_file: Path to article file (markdown or text)
            
        Returns:
            PipelineOutput with structured data for LLM
        """
        article_file = str(article_file)  # Convert Path to string

        self._log(f"🚀 Starting pipeline analysis")
        self._log(f"   Guidelines: {self.guidelines_file if self.guidelines_file else 'database/text source'}")
        self._log(f"   Article: {article_file}")
        self._log(f"   Target: {self.quartile_target.value} quartile\n")
        
        # Load article
        self._log("📖 Loading article...")
        with open(article_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self._log(f"✓ Loaded {len(content)} characters\n")
        
        # Step 1: Validate structure and content
        self._log("🔍 Step 1: Validating article structure...")
        validation_results = self.validator.validate_all(content)
        validation_summary = self.validator.get_summary(validation_results)
        self._log(f"✓ Validation complete: {validation_summary['passed']}/{validation_summary['total_checks']} checks passed\n")
        
        # Step 2: Quartile analysis
        self._log("📊 Step 2: Performing quartile analysis...")
        quartile_metrics_raw = self.quartile_analyzer.analyze_all_keywords(content)
        quartile_stats = self.quartile_analyzer.get_aggregate_stats(quartile_metrics_raw)
        self._log(f"✓ Analyzed {len(quartile_metrics_raw)} keywords\n")
        
        # Step 3: Convert to structured format
        self._log("🔄 Step 3: Structuring data for LLM...")
        
        structured_validation = self._structure_validation_results(validation_results)
        structured_quartile = self._structure_quartile_metrics(quartile_metrics_raw)
        
        # Step 4: Generate prioritized feedback
        feedback = self._generate_structured_feedback(
            structured_validation, 
            structured_quartile,
            validation_results,
            quartile_metrics_raw
        )
        
        # Step 5: Calculate overall metrics
        overall_quality = self._calculate_overall_quality(validation_summary, quartile_stats)
        estimated_time = self._estimate_revision_time_minutes(feedback)
        
        self._log("✓ Data structured\n")
        
        # Create output
        output = PipelineOutput(
            timestamp=datetime.now().isoformat(),
            guideline_file=self.guidelines_file if self.guidelines_file else "database",
            article_file=article_file,
            content_length=len(content),
            all_passed=validation_summary['all_passed'],
            overall_quality_score=overall_quality,
            overall_status=self._get_status_label(overall_quality),
            validation_summary=validation_summary,
            quartile_summary=quartile_stats,
            validation_results=structured_validation,
            quartile_metrics=structured_quartile,
            feedback=feedback,
            estimated_revision_minutes=estimated_time
        )
        
        self._log("✅ Pipeline analysis complete!\n")
        
        return output
    
    def _structure_validation_results(
        self, 
        validation_results: Dict
    ) -> List[StructuredValidationResult]:
        """Convert validation results to structured format"""
        structured = []
        
        # Structure validation
        if "structure" in validation_results:
            for metric_name, result in validation_results["structure"].items():
                structured.append(StructuredValidationResult(
                    metric_name=result.metric_name,
                    category="structure",
                    passed=result.passed,
                    current_value=result.current_value,
                    expected_min=result.expected_range[0],
                    expected_max=result.expected_range[1],
                    details=result.details,
                    feedback=result.feedback if result.feedback else None
                ))
        
        # Keyword validation
        if "important_terms" in validation_results:
            for result in validation_results["important_terms"]:
                structured.append(StructuredValidationResult(
                    metric_name=result.metric_name,
                    category="keyword",
                    passed=result.passed,
                    current_value=result.current_value,
                    expected_min=result.expected_range[0],
                    expected_max=result.expected_range[1],
                    details=result.details,
                    feedback=result.feedback if result.feedback else None
                ))
        
        # Questions
        if "questions" in validation_results:
            for result in validation_results["questions"]:
                structured.append(StructuredValidationResult(
                    metric_name=result.metric_name,
                    category="question",
                    passed=result.passed,
                    current_value=result.current_value,
                    expected_min=result.expected_range[0],
                    expected_max=result.expected_range[1],
                    details=result.details,
                    feedback=result.feedback if result.feedback else None
                ))
        
        return structured
    
    def _structure_quartile_metrics(
        self, 
        quartile_metrics: List[QuartileMetrics]
    ) -> List[StructuredQuartileMetrics]:
        """Convert quartile metrics to structured format"""
        structured = []
        
        for m in quartile_metrics:
            # Adjust target based on configured quartile
            target = self._calculate_target_for_quartile(m)
            adjustment = target - m.current_count
            
            structured.append(StructuredQuartileMetrics(
                keyword=m.keyword,
                current_count=m.current_count,
                min_required=m.min_required,
                max_allowed=m.max_allowed,
                target_count=target,
                adjustment_needed=adjustment,
                current_zone=m.current_zone.value,
                percentile=m.percentile,
                health_score=m.health_score,
                priority=m.priority.name,
                is_within_range=m.is_within_range,
                is_optimal=m.is_optimal
            ))
        
        return structured
    
    def _calculate_target_for_quartile(self, metrics: QuartileMetrics) -> int:
        """Calculate target count based on configured quartile target"""
        if metrics.current_count < metrics.min_required:
            return metrics.min_required
        elif metrics.current_count > metrics.max_allowed:
            return metrics.max_allowed
        elif self.quartile_target == QuartileTarget.Q1_MINIMUM:
            # Target Q1 (25th percentile) - conservative approach
            return int(metrics.q1_boundary)
        elif self.quartile_target == QuartileTarget.Q2_MEDIAN:
            return int(metrics.q2_boundary)
        elif self.quartile_target == QuartileTarget.Q3_UPPER:
            return int((metrics.q3_boundary + metrics.q2_boundary) / 2)
        else:  # Q4_MAX
            return int((metrics.q4_boundary + metrics.q3_boundary) / 2)
    
    def _generate_structured_feedback(
        self,
        validation_results: List[StructuredValidationResult],
        quartile_metrics: List[StructuredQuartileMetrics],
        raw_validation: Dict,
        raw_quartile: List[QuartileMetrics]
    ) -> List[StructuredFeedback]:
        """Generate prioritized, structured feedback for LLM"""
        feedback_items = []
        
        # 1. Critical keyword issues
        critical_keywords = [m for m in quartile_metrics if m.priority == "CRITICAL"]
        for m in critical_keywords:
            action = "add" if m.adjustment_needed > 0 else "remove"
            priority = "critical"
            
            if m.adjustment_needed > 0:
                instruction = f"Add {abs(m.adjustment_needed)} more instances of '{m.keyword}' to reach minimum requirement of {m.min_required}"
            else:
                instruction = f"Remove {abs(m.adjustment_needed)} instances of '{m.keyword}' to stay within maximum of {m.max_allowed}"
            
            feedback_items.append(StructuredFeedback(
                priority=priority,
                category="keyword",
                action=action,
                target=m.keyword,
                current_value=m.current_count,
                target_value=m.target_count,
                adjustment=m.adjustment_needed,
                instruction=instruction
            ))
        
        # 2. Failed structure validations
        failed_structure = [v for v in validation_results if v.category == "structure" and not v.passed]
        for v in failed_structure:
            # Determine action
            if "add" in v.feedback.lower() if v.feedback else False:
                action = "add"
                adjustment = v.expected_min - v.current_value if isinstance(v.current_value, int) else 0
            elif "remove" in v.feedback.lower() if v.feedback else False:
                action = "remove"
                adjustment = -(v.current_value - v.expected_max) if isinstance(v.current_value, int) else 0
            else:
                action = "modify"
                adjustment = 0
            
            feedback_items.append(StructuredFeedback(
                priority="high",
                category="structure",
                action=action,
                target=v.metric_name,
                current_value=v.current_value,
                target_value=f"{v.expected_min}-{v.expected_max}",
                adjustment=adjustment,
                instruction=v.feedback or f"Adjust {v.metric_name} to meet requirements"
            ))
        
        # 3. Unanswered questions
        unanswered = [v for v in validation_results if v.category == "question" and not v.passed]
        for v in unanswered:
            question = v.metric_name.replace("Q: ", "")
            feedback_items.append(StructuredFeedback(
                priority="critical",
                category="question",
                action="answer",
                target=question,
                current_value="not answered",
                target_value="answered",
                adjustment=0,
                instruction=f"Add content that addresses the question: '{question}'"
            ))
        
        # 4. High priority keywords
        high_priority = [m for m in quartile_metrics 
                        if m.priority == "HIGH" and m.adjustment_needed != 0]
        for m in high_priority[:5]:  # Limit to top 5
            action = "add" if m.adjustment_needed > 0 else "reduce"
            instruction = f"{'Increase' if m.adjustment_needed > 0 else 'Decrease'} usage of '{m.keyword}' by {abs(m.adjustment_needed)} to reach {self.quartile_target.value} quartile target ({m.target_count} occurrences)"
            
            feedback_items.append(StructuredFeedback(
                priority="high",
                category="keyword",
                action=action,
                target=m.keyword,
                current_value=m.current_count,
                target_value=m.target_count,
                adjustment=m.adjustment_needed,
                instruction=instruction
            ))
        
        # 5. Medium priority keywords
        medium_priority = [m for m in quartile_metrics 
                          if m.priority == "MEDIUM" and m.adjustment_needed != 0]
        for m in medium_priority[:3]:  # Limit to top 3
            action = "add" if m.adjustment_needed > 0 else "reduce"
            instruction = f"Consider {'increasing' if m.adjustment_needed > 0 else 'decreasing'} '{m.keyword}' by {abs(m.adjustment_needed)} for optimal distribution"
            
            feedback_items.append(StructuredFeedback(
                priority="medium",
                category="keyword",
                action=action,
                target=m.keyword,
                current_value=m.current_count,
                target_value=m.target_count,
                adjustment=m.adjustment_needed,
                instruction=instruction
            ))
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        feedback_items.sort(key=lambda f: (priority_order.get(f.priority, 99), -abs(f.adjustment)))
        
        return feedback_items
    
    def _calculate_overall_quality(self, validation_summary: Dict, quartile_stats: Dict) -> float:
        """Calculate overall quality score (0-100)"""
        pass_rate = validation_summary['pass_rate']
        health_avg = quartile_stats['health_metrics']['average']
        optimal_pct = quartile_stats['optimal_percentage']
        
        # Weighted score
        score = (pass_rate * 0.4) + (health_avg * 0.4) + (optimal_pct * 0.2)
        return round(score, 2)
    
    def _get_status_label(self, score: float) -> str:
        """Get status label from score"""
        if score >= 90:
            return "EXCELLENT"
        elif score >= 75:
            return "GOOD"
        elif score >= 60:
            return "NEEDS_IMPROVEMENT"
        else:
            return "POOR"
    
    def _estimate_revision_time_minutes(self, feedback: List[StructuredFeedback]) -> int:
        """Estimate revision time in minutes"""
        minutes = 0
        
        for item in feedback:
            if item.priority == "critical":
                if item.category == "question":
                    minutes += 10  # Questions take longer
                else:
                    minutes += 5
            elif item.priority == "high":
                minutes += 3
            elif item.priority == "medium":
                minutes += 2
            else:
                minutes += 1
        
        return max(minutes, 5)  # Minimum 5 minutes
    
    def save_json(self, output: PipelineOutput, filepath: str):
        """
        Save structured output as JSON.
        
        Args:
            output: PipelineOutput object
            filepath: Path to save JSON file
        """
        # Ensure directory exists
        from pathlib import Path
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output.to_json())
        
        self._log(f"✓ Saved JSON: {filepath}")

    def save_human_readable_report(self, output: PipelineOutput, filepath: str):
        """
        Save human-readable report.
        
        Args:
            output: PipelineOutput object
            filepath: Path to save report
        """
        # Ensure directory exists
        from pathlib import Path
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        lines = [
            "=" * 70,
            "CONTENT VALIDATION REPORT",
            "=" * 70,
            "",
            f"Generated: {output.timestamp}",
            f"Article: {output.article_file}",
            f"Guidelines: {output.guideline_file}",
            "",
            "=" * 70,
            "OVERALL STATUS",
            "=" * 70,
            "",
            f"Quality Score: {output.overall_quality_score}/100",
            f"Status: {output.overall_status}",
            f"All Checks Passed: {'✅ Yes' if output.all_passed else '❌ No'}",
            f"Estimated Revision Time: {output.estimated_revision_minutes} minutes",
            "",
            "=" * 70,
            "SUMMARY",
            "=" * 70,
            "",
            "Validation:",
            f"  • Pass Rate: {output.validation_summary['pass_rate']:.1f}%",
            f"  • Passed: {output.validation_summary['passed']}/{output.validation_summary['total_checks']}",
            "",
            "Keywords:",
            f"  • Average Health: {output.quartile_summary['health_metrics']['average']:.1f}/100",
            f"  • Optimal Range: {output.quartile_summary['optimal_percentage']:.1f}%",
            f"  • Within Range: {output.quartile_summary['within_range_percentage']:.1f}%",
            "",
            "=" * 70,
            f"ACTIONABLE FEEDBACK ({len(output.feedback)} items)",
            "=" * 70,
            ""
        ]
        
        # Group feedback by priority
        for priority in ["critical", "high", "medium", "low"]:
            items = [f for f in output.feedback if f.priority == priority]
            if items:
                lines.append(f"\n{priority.upper()} PRIORITY:")
                lines.append("-" * 70)
                for i, item in enumerate(items, 1):
                    lines.append(f"\n{i}. {item.instruction}")
                    lines.append(f"   Category: {item.category} | Action: {item.action}")
                    lines.append(f"   Target: {item.target}")
                    lines.append(f"   Current: {item.current_value} → Target: {item.target_value}")
                    if item.adjustment != 0:
                        lines.append(f"   Adjustment: {item.adjustment:+d}")
                lines.append("")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        self._log(f"✓ Saved report: {filepath}")
    
    def generate_action_reports(self, output: PipelineOutput, output_dir: str = "./reports"):
        """
        Generate action-only reports using QuartileFeedbackGenerator.
        
        Args:
            output: PipelineOutput from analyze_article()
            output_dir: Directory to save reports
        """
        from pathlib import Path
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create feedback generator
        generator = QuartileFeedbackGenerator(self.quartile_target)
        
        # Re-analyze to get raw metrics
        with open(output.article_file, 'r') as f:
            content = f.read()
        
        raw_metrics = self.quartile_analyzer.analyze_all_keywords(content)
        
        # Calculate quartile-specific targets
        target_metrics = generator.calculate_quartile_targets(raw_metrics)
        
        # Generate actions
        actions = generator.generate_all_actions(target_metrics, output.validation_results)
        
        # Generate reports
        action_only = generator.generate_action_only_report(actions)
        detailed = generator.generate_detailed_action_report(actions)
        
        # Save files
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        action_file = output_dir / f"actions_{self.quartile_target.value}_{timestamp}.txt"
        detailed_file = output_dir / f"detailed_{self.quartile_target.value}_{timestamp}.txt"
        json_file = output_dir / f"actions_{self.quartile_target.value}_{timestamp}.json"
        
        with open(action_file, 'w') as f:
            f.write(action_only)
        
        with open(detailed_file, 'w') as f:
            f.write(detailed)
        
        with open(json_file, 'w') as f:
            json.dump(generator.export_actions_to_json(actions), f, indent=2)
        
        self._log(f"✓ Saved action reports:")
        self._log(f"   • {action_file}")
        self._log(f"   • {detailed_file}")
        self._log(f"   • {json_file}")
        
        return action_file, detailed_file, json_file