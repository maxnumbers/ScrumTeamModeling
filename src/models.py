from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
import random
import logging
from datetime import datetime
from src.enums import Role, Phase, Meeting

logger = logging.getLogger('sprint_simulation')

@dataclass
class TimeBlock:
    start: float
    duration: float
    activity: str
    story_id: Optional[int] = None
    meeting: Optional[Meeting] = None

@dataclass
class TeamMember:
    name: str
    roles: Set[Role]
    primary_role: Role
    env: 'simpy.Environment'
    current_role: Optional[Role] = None
    current_story: Optional[int] = None
    daily_hours_worked: float = 0.0
    weekly_hours_worked: float = 0.0
    total_hours_worked: Dict[Role, float] = field(default_factory=lambda: defaultdict(float))
    non_dev_hours: Dict[Meeting, float] = field(default_factory=lambda: defaultdict(float))
    story_points_contributed: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    schedule: List[TimeBlock] = field(default_factory=list)
    context_switches: int = 0
    last_task: Optional[Tuple[str, int]] = None
    failed_assignments: int = 0
    max_weekly_hours: float = 40.0
    max_daily_hours: float = 8.0

    def get_effective_availability(self, hours_needed: float) -> float:
        """Calculate effective availability considering non-dev tasks"""
        non_dev_time = sum(self.non_dev_hours.values())
        available_hours = min(
            self.max_daily_hours - self.daily_hours_worked,
            self.max_weekly_hours - self.weekly_hours_worked
        )
        return max(0, available_hours - (non_dev_time * 0.2))  # 20% buffer for context switching

    def is_available(self, role: Role, story_id: int, hours_needed: float) -> Tuple[bool, str]:
        if self.current_role is not None:
            return False, f"Already working as {self.current_role}"
        if role not in self.roles:
            return False, f"Does not have {role} capability"
        if self.current_story == story_id:
            return False, "Already working on this story"
            
        effective_hours = self.get_effective_availability(hours_needed)
        if effective_hours < hours_needed:
            return False, f"Insufficient availability ({effective_hours:.1f}h < {hours_needed:.1f}h needed)"
            
        # Check role-specific constraints
        if Role.is_po_role(role) and any(Role.is_po_role(r) for r in self.roles):
            for assigned_role in self.total_hours_worked.keys():
                if Role.is_po_role(assigned_role) and story_id in self.story_points_contributed:
                    return False, "Cannot perform multiple PO roles on same story"
                    
        if Role.is_admin_role(role) and any(Role.is_admin_role(r) for r in self.roles):
            for assigned_role in self.total_hours_worked.keys():
                if Role.is_admin_role(assigned_role) and story_id in self.story_points_contributed:
                    return False, "Cannot perform multiple Admin roles on same story"
                    
        return True, "Available"

    def start_work(self, role: Role, story_id: int, hours: float, activity: str):
        if hours <= 0:
            raise ValueError(f"Invalid work duration: {hours} hours")
        
        available, reason = self.is_available(role, story_id, hours)
        if not available:
            raise RuntimeError(f"Cannot start work: {reason}")

        self.current_role = role
        self.current_story = story_id
        self.daily_hours_worked += hours
        self.weekly_hours_worked += hours
        self.total_hours_worked[role] += hours

        current_task = (activity, story_id)
        if self.last_task and self.last_task != current_task:
            self.context_switches += 1
        self.last_task = current_task

        self.schedule.append(TimeBlock(
            start=self.env.now,
            duration=hours,
            activity=activity,
            story_id=story_id
        ))
        
        logger.debug(f"{self.name} started {activity} on story {story_id} for {hours} hours")

    def end_work(self):
        self.current_role = None
        self.current_story = None

    def attend_meeting(self, meeting: Meeting, duration: float):
        if duration <= 0:
            raise ValueError(f"Invalid meeting duration: {duration} hours")
        
        if self.daily_hours_worked + duration > 8.0:
            logger.warning(f"{self.name} exceeded daily hours due to {meeting} meeting")
        
        self.daily_hours_worked += duration
        self.weekly_hours_worked += duration
        
        self.schedule.append(TimeBlock(
            start=self.env.now,
            duration=duration,
            activity="Meeting",
            meeting=meeting
        ))
        logger.debug(f"{self.name} attended {meeting} for {duration} hours")

@dataclass
class Story:
    id: int
    points: int
    env: 'simpy.Environment'
    phase: Phase = Phase.TODO
    assigned_members: Dict[Role, str] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    review_iterations: int = 0
    po_review_iterations: int = 0
    validation_iterations: int = 0
    time_in_phases: Dict[Phase, float] = field(default_factory=lambda: defaultdict(float))
    phase_start_times: Dict[Phase, float] = field(default_factory=dict)
    max_attempts: Dict[str, int] = field(default_factory=lambda: {
        'review': 3,
        'po_review': 2,
        'validation': 2
    })

    def get_phase_hours(self, phase: str) -> float:
        base_hours = {
            1: {'dev': 4, 'review': 1, 'po': 0.5, 'validation': 1, 'documentation': 0.5},
            2: {'dev': 8, 'review': 2, 'po': 1, 'validation': 2, 'documentation': 1},
            3: {'dev': 16, 'review': 3, 'po': 1.5, 'validation': 3, 'documentation': 1.5},
            5: {'dev': 24, 'review': 5, 'po': 2, 'validation': 5, 'documentation': 2},
            8: {'dev': 40, 'review': 8, 'po': 3, 'validation': 8, 'documentation': 3}
        }

        if self.points not in base_hours:
            raise ValueError(f"Invalid story points: {self.points}")
        if phase not in base_hours[self.points]:
            raise ValueError(f"Invalid phase: {phase}")

        variation = random.uniform(0.8, 1.2)
        return base_hours[self.points][phase] * variation

    def start_phase(self, phase: Phase):
        self.phase = phase
        self.phase_start_times[phase] = self.env.now
        logger.info(f"Story {self.id} ({self.points} pts) entered {phase.value}")

    def end_phase(self, phase: Phase):
        if phase in self.phase_start_times:
            duration = self.env.now - self.phase_start_times[phase]
            self.time_in_phases[phase] += duration
            logger.info(f"Story {self.id} completed {phase.value} in {duration:.1f} hours")
