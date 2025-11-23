import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import math

class QuartileZone(Enum):
    """Quartile zones for keyword usage"""
    BELOW_RANGE = "Below Range"
    Q1 = "Q1 (0-25%)"      # Critical - needs immediate attention
    Q2 = "Q2 (25-50%)"     # Below target - needs improvement
    Q3 = "Q3 (50-75%)"     # Good - within acceptable range
    Q4 = "Q4 (75-100%)"    # Optimal - high but safe
    ABOVE_RANGE = "Above Range"


class OptimizationPriority(Enum):
    """Priority levels for keyword optimization"""
    CRITICAL = 1    # Below min or above max
    HIGH = 2        # Q1 range
    MEDIUM = 3      # Q2 range
    LOW = 4         # Q3 range
    MINIMAL = 5     # Q4 range


@dataclass
class QuartileMetrics:
    """Detailed quartile analysis for a keyword"""
    keyword: str
    current_count: int
    min_required: int
    max_allowed: int
    
    # Quartile boundaries
    q1_boundary: float
    q2_boundary: float  # Median
    q3_boundary: float
    q4_boundary: float  # Max
    
    # Current position
    current_zone: QuartileZone
    percentile: float  # 0-100, where current count falls
    
    # Distance metrics
    distance_to_min: int
    distance_to_median: float
    distance_to_max: int
    
    # Optimization metrics
    priority: OptimizationPriority
    health_score: float  # 0-100, higher is better
    
    # Recommendations
    target_count: int  # Recommended target (Q3 midpoint)
    adjustment_needed: int  # How many to add/remove
    
    # Status
    is_within_range: bool
    is_optimal: bool  # True if in Q3 or Q4
    
    def __str__(self) -> str:
        return (
            f"Keyword: '{self.keyword}'\n"
            f"  Current: {self.current_count} | Range: [{self.min_required}, {self.max_allowed}]\n"
            f"  Zone: {self.current_zone.value} | Percentile: {self.percentile:.1f}%\n"
            f"  Health Score: {self.health_score:.1f}/100\n"
            f"  Priority: {self.priority.name}\n"
            f"  Target: {self.target_count} (adjustment: {self.adjustment_needed:+d})"
        )


class KeywordQuartileAnalyzer:
    """
    Analyzes keyword usage distribution using quartile analysis.
    
    Features:
    - Calculate quartile boundaries for keyword ranges
    - Determine which quartile current usage falls into
    - Generate health scores and optimization priorities
    - Provide strategic recommendations based on distribution
    - Handle edge cases (zero ranges, out-of-bounds values)
    - Aggregate analysis across all keywords
    """
    
    def __init__(self, keyword_requirements: Dict[str, Tuple[int, int]]):
        """
        Initialize analyzer with keyword requirements.
        
        Args:
            keyword_requirements: {keyword: (min_count, max_count)}
        """
        self.keyword_requirements = keyword_requirements
        self.metrics_cache: Dict[str, QuartileMetrics] = {}
    
    def analyze_keyword(
        self, 
        keyword: str, 
        current_count: int,
        use_cache: bool = True
    ) -> QuartileMetrics:
        """
        Perform comprehensive quartile analysis for a single keyword.
        
        Args:
            keyword: The keyword to analyze
            current_count: Current occurrence count in content
            use_cache: Whether to use cached results
            
        Returns:
            QuartileMetrics object with complete analysis
        """
        cache_key = f"{keyword}:{current_count}"
        
        if use_cache and cache_key in self.metrics_cache:
            return self.metrics_cache[cache_key]
        
        if keyword not in self.keyword_requirements:
            raise ValueError(f"Keyword '{keyword}' not found in requirements")
        
        min_req, max_req = self.keyword_requirements[keyword]
        
        # Calculate quartile boundaries
        range_span = max_req - min_req
        
        if range_span == 0:
            # Edge case: min == max (single target value)
            q1 = q2 = q3 = q4 = min_req
        else:
            q1 = min_req + (range_span * 0.25)
            q2 = min_req + (range_span * 0.50)  # Median
            q3 = min_req + (range_span * 0.75)
            q4 = max_req
        
        # Determine current zone
        current_zone = self._determine_zone(current_count, min_req, max_req, q1, q2, q3)
        
        # Calculate percentile (where in range 0-100%)
        percentile = self._calculate_percentile(current_count, min_req, max_req)
        
        # Distance metrics
        distance_to_min = current_count - min_req
        distance_to_median = current_count - q2
        distance_to_max = current_count - max_req
        
        # Optimization priority
        priority = self._calculate_priority(current_zone, percentile)
        
        # Health score (0-100)
        health_score = self._calculate_health_score(
            current_count, min_req, max_req, q2, q3, current_zone
        )
        
        # Target recommendation (aim for Q3 midpoint for optimal balance)
        target_count = self._calculate_target(q3, q4, current_zone, current_count, min_req, max_req)
        adjustment_needed = target_count - current_count
        
        # Status flags
        is_within_range = min_req <= current_count <= max_req
        is_optimal = current_zone in [QuartileZone.Q3, QuartileZone.Q4]
        
        metrics = QuartileMetrics(
            keyword=keyword,
            current_count=current_count,
            min_required=min_req,
            max_allowed=max_req,
            q1_boundary=q1,
            q2_boundary=q2,
            q3_boundary=q3,
            q4_boundary=q4,
            current_zone=current_zone,
            percentile=percentile,
            distance_to_min=distance_to_min,
            distance_to_median=distance_to_median,
            distance_to_max=distance_to_max,
            priority=priority,
            health_score=health_score,
            target_count=target_count,
            adjustment_needed=adjustment_needed,
            is_within_range=is_within_range,
            is_optimal=is_optimal
        )
        
        # Cache result
        self.metrics_cache[cache_key] = metrics
        
        return metrics
    
    def _determine_zone(
        self, 
        count: int, 
        min_val: int, 
        max_val: int,
        q1: float,
        q2: float,
        q3: float
    ) -> QuartileZone:
        """Determine which quartile zone the count falls into"""
        if count < min_val:
            return QuartileZone.BELOW_RANGE
        elif count > max_val:
            return QuartileZone.ABOVE_RANGE
        elif count <= q1:
            return QuartileZone.Q1
        elif count <= q2:
            return QuartileZone.Q2
        elif count <= q3:
            return QuartileZone.Q3
        else:
            return QuartileZone.Q4
    
    def _calculate_percentile(self, count: int, min_val: int, max_val: int) -> float:
        """
        Calculate percentile position (0-100) within the allowed range.
        Values below min return negative percentiles, above max return >100.
        """
        range_span = max_val - min_val
        
        if range_span == 0:
            # Single value range
            if count == min_val:
                return 50.0
            elif count < min_val:
                return 0.0
            else:
                return 100.0
        
        percentile = ((count - min_val) / range_span) * 100
        return percentile
    
    def _calculate_priority(self, zone: QuartileZone, percentile: float) -> OptimizationPriority:
        """Determine optimization priority based on zone and percentile"""
        if zone in [QuartileZone.BELOW_RANGE, QuartileZone.ABOVE_RANGE]:
            return OptimizationPriority.CRITICAL
        elif zone == QuartileZone.Q1:
            return OptimizationPriority.HIGH
        elif zone == QuartileZone.Q2:
            return OptimizationPriority.MEDIUM
        elif zone == QuartileZone.Q3:
            return OptimizationPriority.LOW
        else:  # Q4
            return OptimizationPriority.MINIMAL
    
    def _calculate_health_score(
        self,
        count: int,
        min_val: int,
        max_val: int,
        q2: float,
        q3: float,
        zone: QuartileZone
    ) -> float:
        """
        Calculate health score (0-100) where higher is better.
        
        Scoring:
        - Below range: 0
        - Q1: 25-40 (proportional)
        - Q2: 40-60 (proportional)
        - Q3: 60-90 (proportional) - optimal zone
        - Q4: 90-100 (proportional) - peak zone
        - Above range: 0
        """
        if zone == QuartileZone.BELOW_RANGE:
            # Penalty based on how far below
            deficit_ratio = count / min_val if min_val > 0 else 0
            return max(0, deficit_ratio * 25)
        
        elif zone == QuartileZone.ABOVE_RANGE:
            # Penalty based on how far above
            excess_ratio = max_val / count if count > 0 else 0
            return max(0, excess_ratio * 25)
        
        elif zone == QuartileZone.Q1:
            # 25-40 range
            q1_start = min_val
            q1_end = min_val + (max_val - min_val) * 0.25
            position = (count - q1_start) / (q1_end - q1_start) if q1_end != q1_start else 1
            return 25 + (position * 15)
        
        elif zone == QuartileZone.Q2:
            # 40-60 range
            q2_start = min_val + (max_val - min_val) * 0.25
            q2_end = q2
            position = (count - q2_start) / (q2_end - q2_start) if q2_end != q2_start else 1
            return 40 + (position * 20)
        
        elif zone == QuartileZone.Q3:
            # 60-90 range (optimal)
            q3_start = q2
            q3_end = q3
            position = (count - q3_start) / (q3_end - q3_start) if q3_end != q3_start else 1
            return 60 + (position * 30)
        
        else:  # Q4
            # 90-100 range (peak)
            q4_start = q3
            q4_end = max_val
            position = (count - q4_start) / (q4_end - q4_start) if q4_end != q4_start else 1
            return 90 + (position * 10)
    
    def _calculate_target(
        self,
        q3: float,
        q4: float,
        zone: QuartileZone,
        current: int,
        min_val: int,
        max_val: int
    ) -> int:
        """
        Calculate recommended target count.
        
        Strategy:
        - Below range: Target minimum
        - Q1/Q2: Target Q3 midpoint (62.5th percentile)
        - Q3: Keep current (already optimal)
        - Q4: Keep current (already excellent)
        - Above range: Target maximum
        """
        if zone == QuartileZone.BELOW_RANGE:
            return min_val
        elif zone == QuartileZone.ABOVE_RANGE:
            return max_val
        elif zone in [QuartileZone.Q1, QuartileZone.Q2]:
            # Target Q3 midpoint for optimal balance
            return math.ceil((q3 + q4) / 2)
        else:  # Q3 or Q4
            # Already in good zone, keep current
            return current
    
    def analyze_all_keywords(self, content: str) -> List[QuartileMetrics]:
        """
        Analyze all keywords in the content.
        
        Args:
            content: The article content to analyze
            
        Returns:
            List of QuartileMetrics for all keywords
        """
        content_lower = content.lower()
        all_metrics = []
        
        for keyword, (min_req, max_req) in self.keyword_requirements.items():
            # Count keyword occurrences (word boundary aware)
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            count = len(re.findall(pattern, content_lower))
            
            metrics = self.analyze_keyword(keyword, count)
            all_metrics.append(metrics)
        
        return all_metrics
    
    def get_aggregate_stats(self, metrics_list: List[QuartileMetrics]) -> Dict:
        """
        Calculate aggregate statistics across all keywords.
        
        Returns dictionary with:
        - Zone distribution
        - Priority distribution
        - Average health score
        - Overall optimization status
        """
        if not metrics_list:
            return {}
        
        # Zone distribution
        zone_counts = {}
        for zone in QuartileZone:
            zone_counts[zone.value] = sum(1 for m in metrics_list if m.current_zone == zone)
        
        # Priority distribution
        priority_counts = {}
        for priority in OptimizationPriority:
            priority_counts[priority.name] = sum(1 for m in metrics_list if m.priority == priority)
        
        # Health metrics
        avg_health = sum(m.health_score for m in metrics_list) / len(metrics_list)
        min_health = min(m.health_score for m in metrics_list)
        max_health = max(m.health_score for m in metrics_list)
        
        # Status counts
        within_range = sum(1 for m in metrics_list if m.is_within_range)
        optimal = sum(1 for m in metrics_list if m.is_optimal)
        
        # Critical issues
        critical_keywords = [m for m in metrics_list if m.priority == OptimizationPriority.CRITICAL]
        
        return {
            "total_keywords": len(metrics_list),
            "zone_distribution": zone_counts,
            "priority_distribution": priority_counts,
            "health_metrics": {
                "average": avg_health,
                "minimum": min_health,
                "maximum": max_health
            },
            "within_range_count": within_range,
            "within_range_percentage": (within_range / len(metrics_list)) * 100,
            "optimal_count": optimal,
            "optimal_percentage": (optimal / len(metrics_list)) * 100,
            "critical_keywords": [m.keyword for m in critical_keywords],
            "overall_status": self._determine_overall_status(avg_health, optimal, len(metrics_list))
        }
    
    def _determine_overall_status(self, avg_health: float, optimal_count: int, total: int) -> str:
        """Determine overall content optimization status"""
        optimal_ratio = optimal_count / total if total > 0 else 0
        
        if avg_health >= 80 and optimal_ratio >= 0.8:
            return "EXCELLENT"
        elif avg_health >= 60 and optimal_ratio >= 0.6:
            return "GOOD"
        elif avg_health >= 40 and optimal_ratio >= 0.4:
            return "NEEDS IMPROVEMENT"
        else:
            return "POOR"
    
    def get_priority_sorted_keywords(self, metrics_list: List[QuartileMetrics]) -> List[QuartileMetrics]:
        """
        Sort keywords by optimization priority (critical first).
        
        Within same priority, sort by health score (lowest first).
        """
        return sorted(
            metrics_list,
            key=lambda m: (m.priority.value, m.health_score)
        )
    
    def generate_optimization_plan(self, metrics_list: List[QuartileMetrics]) -> str:
        """
        Generate a strategic optimization plan based on quartile analysis.
        """
        sorted_metrics = self.get_priority_sorted_keywords(metrics_list)
        
        lines = ["🎯 QUARTILE-BASED OPTIMIZATION PLAN", "=" * 60, ""]
        
        # Group by priority
        by_priority = {}
        for priority in OptimizationPriority:
            by_priority[priority] = [m for m in sorted_metrics if m.priority == priority]
        
        # Critical priority
        if by_priority[OptimizationPriority.CRITICAL]:
            lines.append("🔴 CRITICAL PRIORITY (Fix Immediately)")
            lines.append("-" * 60)
            for m in by_priority[OptimizationPriority.CRITICAL]:
                lines.append(f"\n'{m.keyword}':")
                lines.append(f"  Current: {m.current_count} | Range: [{m.min_required}, {m.max_allowed}]")
                lines.append(f"  Status: {m.current_zone.value}")
                lines.append(f"  Action: Adjust by {m.adjustment_needed:+d} to reach {m.target_count}")
                lines.append(f"  Health: {m.health_score:.1f}/100")
            lines.append("")
        
        # High priority
        if by_priority[OptimizationPriority.HIGH]:
            lines.append("🟠 HIGH PRIORITY (Address Soon)")
            lines.append("-" * 60)
            for m in by_priority[OptimizationPriority.HIGH]:
                lines.append(f"\n'{m.keyword}':")
                lines.append(f"  Current: {m.current_count} ({m.percentile:.1f}% of range)")
                lines.append(f"  Target: {m.target_count} (Q3 zone) - adjust by {m.adjustment_needed:+d}")
                lines.append(f"  Health: {m.health_score:.1f}/100")
            lines.append("")
        
        # Medium priority
        if by_priority[OptimizationPriority.MEDIUM]:
            lines.append("🟡 MEDIUM PRIORITY (Improve When Possible)")
            lines.append("-" * 60)
            for m in by_priority[OptimizationPriority.MEDIUM]:
                lines.append(f"  • '{m.keyword}': {m.current_count} → {m.target_count} ({m.adjustment_needed:+d})")
            lines.append("")
        
        # Low/Minimal priority
        low_and_minimal = by_priority[OptimizationPriority.LOW] + by_priority[OptimizationPriority.MINIMAL]
        if low_and_minimal:
            lines.append("🟢 LOW PRIORITY (Already Optimal)")
            lines.append("-" * 60)
            for m in low_and_minimal:
                lines.append(f"  ✓ '{m.keyword}': {m.current_count} ({m.current_zone.value})")
            lines.append("")
        
        # Summary
        stats = self.get_aggregate_stats(metrics_list)
        lines.append("📊 OVERALL ASSESSMENT")
        lines.append("-" * 60)
        lines.append(f"Status: {stats['overall_status']}")
        lines.append(f"Average Health: {stats['health_metrics']['average']:.1f}/100")
        lines.append(f"Keywords in Optimal Range: {stats['optimal_count']}/{stats['total_keywords']} ({stats['optimal_percentage']:.1f}%)")
        
        return "\n".join(lines)
    
    def visualize_keyword_distribution(self, metrics: QuartileMetrics, width: int = 50) -> str:
        """
        Create ASCII visualization of keyword position in range.
        
        Example output:
        hemp shoes [17-53]:
        ├─────Q1─────┼─────Q2─────┼─────Q3─────┼─────Q4─────┤
        17          24.5         32         39.5          53
                              ▲ (32 - Q2/Q3 border)
        """
        lines = []
        lines.append(f"\n{metrics.keyword} [{metrics.min_required}-{metrics.max_allowed}]:")
        
        # Create scale line
        q1_pos = int((metrics.q1_boundary - metrics.min_required) / (metrics.max_allowed - metrics.min_required) * width)
        q2_pos = int((metrics.q2_boundary - metrics.min_required) / (metrics.max_allowed - metrics.min_required) * width)
        q3_pos = int((metrics.q3_boundary - metrics.min_required) / (metrics.max_allowed - metrics.min_required) * width)
        
        scale = ['─'] * width
        scale[0] = '├'
        scale[-1] = '┤'
        if 0 < q1_pos < width:
            scale[q1_pos] = '┼'
        if 0 < q2_pos < width:
            scale[q2_pos] = '┼'
        if 0 < q3_pos < width:
            scale[q3_pos] = '┼'
        
        lines.append(''.join(scale))
        
        # Add labels
        label_line = f"{metrics.min_required:<10}"
        label_line += f"{metrics.q1_boundary:>8.1f}"
        label_line += f"{metrics.q2_boundary:>10.1f}"
        label_line += f"{metrics.q3_boundary:>10.1f}"
        label_line += f"{metrics.max_allowed:>12}"
        lines.append(label_line)
        
        # Add current position indicator
        if metrics.min_required <= metrics.current_count <= metrics.max_allowed:
            current_pos = int((metrics.current_count - metrics.min_required) / (metrics.max_allowed - metrics.min_required) * width)
            indicator = ' ' * current_pos + f"▲ ({metrics.current_count} - {metrics.current_zone.value})"
            lines.append(indicator)
        else:
            if metrics.current_count < metrics.min_required:
                lines.append(f"▼ ({metrics.current_count} - BELOW RANGE)")
            else:
                lines.append(f"{' ' * (width - 10)}▲ ({metrics.current_count} - ABOVE RANGE)")
        
        return '\n'.join(lines)
    
    def export_to_dict(self, metrics: QuartileMetrics) -> Dict:
        """Export metrics to dictionary for JSON serialization"""
        return {
            "keyword": metrics.keyword,
            "current_count": metrics.current_count,
            "range": {
                "min": metrics.min_required,
                "max": metrics.max_allowed
            },
            "quartiles": {
                "q1": metrics.q1_boundary,
                "q2": metrics.q2_boundary,
                "q3": metrics.q3_boundary,
                "q4": metrics.q4_boundary
            },
            "analysis": {
                "zone": metrics.current_zone.value,
                "percentile": metrics.percentile,
                "priority": metrics.priority.name,
                "health_score": metrics.health_score
            },
            "recommendation": {
                "target_count": metrics.target_count,
                "adjustment_needed": metrics.adjustment_needed
            },
            "status": {
                "within_range": metrics.is_within_range,
                "is_optimal": metrics.is_optimal
            }
        }