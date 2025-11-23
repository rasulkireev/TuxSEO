#!/usr/bin/env python3
"""
Quartile Action Generator - Agent-Optimized

Generates actions ONLY for the selected quartile target.
Output: JSON format only (minimal, structured).
"""

from typing import Dict, List
from dataclasses import dataclass, asdict
from enum import Enum
import json

from quartile_analyzer import QuartileMetrics


class QuartileTarget(Enum):
    """Target quartile zones"""
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


@dataclass
class Action:
    """Single action specification"""
    type: str  # "add" | "remove" | "answer"
    target: str
    current: int
    required: int
    delta: int
    priority: str  # "critical" | "high" | "medium" | "low"
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class QuartileOutput:
    """Complete output for quartile target"""
    target: str
    total_actions: int
    actions: List[Dict]
    summary: Dict
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self, minified: bool = True) -> str:
        """Convert to JSON string"""
        if minified:
            return json.dumps(self.to_dict(), separators=(',', ':'))
        return json.dumps(self.to_dict(), indent=2)


class QuartileActionGenerator:
    """
    Generates token-efficient actions for a specific quartile target.
    
    Output: JSON only
    Focus: Selected quartile only (no comparisons)
    """
    
    def __init__(self, target: QuartileTarget):
        """
        Initialize generator.
        
        Args:
            target: Quartile target (Q1/Q2/Q3/Q4)
        """
        self.target = target
        self._zone_ranges = {
            QuartileTarget.Q1: (0.00, 0.25),
            QuartileTarget.Q2: (0.25, 0.50),
            QuartileTarget.Q3: (0.50, 0.75),
            QuartileTarget.Q4: (0.75, 1.00)
        }
    
    def _calculate_target_value(self, min_val: int, max_val: int) -> int:
        """Calculate target value for this quartile"""
        if min_val == max_val:
            return min_val
        
        zone_start, zone_end = self._zone_ranges[self.target]
        range_span = max_val - min_val
        
        # Target midpoint of zone
        target_pct = (zone_start + zone_end) / 2
        return int(round(min_val + (range_span * target_pct)))
    
    def _is_in_target_zone(self, current: int, min_val: int, max_val: int) -> bool:
        """Check if current is in target zone"""
        if current < min_val or current > max_val:
            return False
        
        zone_start, zone_end = self._zone_ranges[self.target]
        range_span = max_val - min_val
        
        if range_span == 0:
            return True
        
        zone_min = min_val + (range_span * zone_start)
        zone_max = min_val + (range_span * zone_end)
        
        return zone_min <= current <= zone_max
    
    def _calculate_priority(self, current: int, min_val: int, max_val: int, delta: int) -> str:
        """Calculate action priority"""
        # Out of range = critical
        if current < min_val or current > max_val:
            return "critical"
        
        # In range - calculate distance
        range_span = max_val - min_val
        if range_span == 0:
            return "low"
        
        distance_pct = abs(delta) / range_span
        
        if distance_pct > 0.5:
            return "high"
        elif distance_pct > 0.25:
            return "medium"
        else:
            return "low"
    
    def _process_keywords(self, metrics: List[QuartileMetrics]) -> List[Action]:
        """Process keyword metrics into actions"""
        actions = []
        
        for m in metrics:
            # Skip if already in target zone and within range
            if (m.min_required <= m.current_count <= m.max_allowed and 
                self._is_in_target_zone(m.current_count, m.min_required, m.max_allowed)):
                continue
            
            # Calculate target
            target_value = self._calculate_target_value(m.min_required, m.max_allowed)
            delta = target_value - m.current_count
            
            if delta == 0:
                continue
            
            # Determine type
            action_type = "add" if delta > 0 else "remove"
            
            # Calculate priority
            priority = self._calculate_priority(m.current_count, m.min_required, m.max_allowed, delta)
            
            actions.append(Action(
                type=action_type,
                target=m.keyword,
                current=m.current_count,
                required=target_value,
                delta=delta,
                priority=priority
            ))
        
        return actions
    
    def _process_structure(self, validation_results: List) -> List[Action]:
        """Process structure validation into actions"""
        actions = []
        
        for result in validation_results:
            if result.passed or result.category != "structure":
                continue
            
            # Calculate target and delta
            if result.current_value < result.expected_min:
                target_value = result.expected_min
                delta = target_value - result.current_value
                action_type = "add"
            else:
                target_value = result.expected_max
                delta = target_value - result.current_value
                action_type = "remove"
            
            # Map to target name
            metric_lower = result.metric_name.lower()
            if "heading" in metric_lower:
                target = "headings"
                priority = "high"
            elif "paragraph" in metric_lower:
                target = "paragraphs"
                priority = "medium"
            elif "image" in metric_lower:
                target = "images"
                priority = "medium"
            elif "word" in metric_lower:
                target = "words"
                priority = "high"
            elif "character" in metric_lower:
                target = "characters"
                priority = "medium"
            else:
                target = result.metric_name
                priority = "medium"
            
            actions.append(Action(
                type=action_type,
                target=target,
                current=result.current_value,
                required=target_value,
                delta=delta,
                priority=priority
            ))
        
        return actions
    
    def _process_questions(self, validation_results: List) -> List[Action]:
        """Process question validation into actions"""
        actions = []
        
        for result in validation_results:
            if result.passed or result.category != "question":
                continue
            
            question = result.metric_name.replace("Q: ", "")
            
            actions.append(Action(
                type="answer",
                target=question,
                current=0,
                required=1,
                delta=1,
                priority="critical"
            ))
        
        return actions
    
    def generate(
        self,
        keyword_metrics: List[QuartileMetrics],
        validation_results: List
    ) -> QuartileOutput:
        """
        Generate all actions for target quartile.
        
        Args:
            keyword_metrics: Keyword analysis results
            validation_results: Structure/question validation results
            
        Returns:
            QuartileOutput with JSON-serializable data
        """
        all_actions = []
        
        # Process all categories
        all_actions.extend(self._process_keywords(keyword_metrics))
        all_actions.extend(self._process_structure(validation_results))
        all_actions.extend(self._process_questions(validation_results))
        
        # Sort by priority and impact
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_actions.sort(key=lambda a: (priority_order.get(a.priority, 99), -abs(a.delta)))
        
        # Calculate summary
        summary = self._calculate_summary(all_actions)
        
        return QuartileOutput(
            target=self.target.value,
            total_actions=len(all_actions),
            actions=[a.to_dict() for a in all_actions],
            summary=summary
        )
    
    def _calculate_summary(self, actions: List[Action]) -> Dict:
        """Calculate summary statistics"""
        if not actions:
            return {
                "by_priority": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "by_type": {"add": 0, "remove": 0, "answer": 0},
                "total_additions": 0,
                "total_removals": 0
            }
        
        by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_type = {"add": 0, "remove": 0, "answer": 0}
        total_additions = 0
        total_removals = 0
        
        for action in actions:
            by_priority[action.priority] += 1
            by_type[action.type] += 1
            
            if action.type == "add":
                total_additions += abs(action.delta)
            elif action.type == "remove":
                total_removals += abs(action.delta)
        
        return {
            "by_priority": by_priority,
            "by_type": by_type,
            "total_additions": total_additions,
            "total_removals": total_removals
        }