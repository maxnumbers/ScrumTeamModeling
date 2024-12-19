import logging
import random
import simpy
import numpy as np
from collections import defaultdict
from typing import List, Dict, Optional
from src.enums import Role, Phase, Meeting
from src.models import Story, TeamMember

logger = logging.getLogger('sprint_simulation')

class SprintSimulation:
    def __init__(self, total_points: int = 50):
        self.env = simpy.Environment()
        self.team_members = self._initialize_team()
        self.total_points = total_points
        self.completed_points = 0
        self.stories = []
        self.sprint_number = 1
        self.sprint_days = 10
        self.daily_ceremonies = defaultdict(list)
        self.sprint_metrics = []
        self.failed_resource_requests = defaultdict(int)
        
        # Additional tracking
        self.current_sprint_start = 0
        self.work_started = False
        self.resource_pool = {}
        self._initialize_resource_pools()

    def _initialize_team(self) -> List[TeamMember]:
        team = []
        
        # PO roles with primary/secondary/tertiary
        team.extend([
            TeamMember("PO1", {Role.PO_PRIMARY, Role.REVIEWER}, Role.PO_PRIMARY, self.env),
            TeamMember("PO2", {Role.PO_SECONDARY, Role.DEVELOPER, Role.REVIEWER}, Role.DEVELOPER, self.env),
            TeamMember("PO3", {Role.PO_TERTIARY, Role.DEVELOPER, Role.REVIEWER}, Role.DEVELOPER, self.env),
        ])
        
        # Admin roles with primary/secondary/tertiary
        team.extend([
            TeamMember("ADMIN1", {Role.ADMIN_PRIMARY, Role.REVIEWER}, Role.ADMIN_PRIMARY, self.env),
            TeamMember("ADMIN2", {Role.ADMIN_SECONDARY, Role.DEVELOPER, Role.REVIEWER}, Role.DEVELOPER, self.env),
            TeamMember("ADMIN3", {Role.ADMIN_TERTIARY, Role.DEVELOPER, Role.REVIEWER}, Role.DEVELOPER, self.env),
        ])
        
        # Pure developers
        team.extend([
            TeamMember(f"DEV{i}", {Role.DEVELOPER, Role.REVIEWER}, Role.DEVELOPER, self.env)
            for i in range(4)
        ])
        
        return team

    def _initialize_resource_pools(self):
        """Initialize resource pools for each role"""
        for role in Role:
            capable_members = len([m for m in self.team_members if role in m.roles])
            
            if Role.is_po_role(role):
                if role == Role.PO_PRIMARY:
                    capacity = 1  # Only one primary PO
                elif role == Role.PO_SECONDARY:
                    capacity = 2  # Primary + Secondary
                else:  # PO_TERTIARY
                    capacity = 3  # All PO roles
            elif Role.is_admin_role(role):
                if role == Role.ADMIN_PRIMARY:
                    capacity = 1  # Only one primary Admin
                elif role == Role.ADMIN_SECONDARY:
                    capacity = 2  # Primary + Secondary
                else:  # ADMIN_TERTIARY
                    capacity = 3  # All Admin roles
            else:
                capacity = max(1, capable_members)
            
            self.resource_pool[role] = simpy.Resource(self.env, capacity=capacity)

    def _conduct_meeting(self, meeting: Meeting, duration: float):
        """Conduct a team meeting"""
        try:
            logger.info(f"Starting {meeting.name} meeting for {duration} hours")
            
            for member in self.team_members:
                member.attend_meeting(meeting, duration)
                member.non_dev_hours[meeting] += duration
                
            self.daily_ceremonies[meeting].append({
                'time': self.env.now,
                'duration': duration,
                'sprint': self.sprint_number
            })
            
        except Exception as e:
            logger.error(f"Error conducting {meeting.name} meeting: {str(e)}")

    def _get_available_member(self, role: Role, story_id: int, hours_needed: float, 
                            phase: str = None) -> Optional[TeamMember]:
        """Find available team member with resource pool management"""
        if not self.resource_pool[role].users and self.resource_pool[role].queue:
            self.failed_resource_requests[role] += 1
            logger.warning(f"Resource pool depleted for {role.name}, {len(self.resource_pool[role].queue)} waiting")
            return None

        # Handle PO role hierarchy
        if role == Role.PO_PRIMARY:
            for member in self.team_members:
                if Role.PO_PRIMARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
        elif role == Role.PO_SECONDARY:
            # Try secondary first, then tertiary
            for member in self.team_members:
                if Role.PO_SECONDARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
            for member in self.team_members:
                if Role.PO_TERTIARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
        elif role == Role.PO_TERTIARY:
            for member in self.team_members:
                if Role.PO_TERTIARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
                        
        # Handle Admin role hierarchy
        elif role == Role.ADMIN_PRIMARY:
            for member in self.team_members:
                if Role.ADMIN_PRIMARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
        elif role == Role.ADMIN_SECONDARY:
            # Try secondary first, then tertiary
            for member in self.team_members:
                if Role.ADMIN_SECONDARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
            for member in self.team_members:
                if Role.ADMIN_TERTIARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
        elif role == Role.ADMIN_TERTIARY:
            for member in self.team_members:
                if Role.ADMIN_TERTIARY in member.roles:
                    available, reason = member.is_available(role, story_id, hours_needed)
                    if available:
                        return member
        
        # Handle other roles (Developer, Reviewer)
        else:
            primary_candidates = []
            secondary_candidates = []
            
            for member in self.team_members:
                available, reason = member.is_available(role, story_id, hours_needed)
                if not available:
                    continue
                    
                if member.primary_role == role:
                    primary_candidates.append(member)
                elif role in member.roles:
                    secondary_candidates.append(member)
            
            if primary_candidates:
                return random.choice(primary_candidates)
                
            if secondary_candidates:
                return random.choice(secondary_candidates)
        
        self.failed_resource_requests[role] += 1
        if phase:
            logger.warning(f"Story {story_id} blocked in {phase} waiting for {role.name}")
        return None

    def story_development_process(self, story: Story):
        """Process for handling story development phase"""
        try:
            story.start_phase(Phase.IN_PROGRESS)
            story.start_time = self.env.now
            remaining_hours = story.get_phase_hours('dev')
            
            while remaining_hours > 0:
                with self.resource_pool[Role.DEVELOPER].request() as request:
                    yield request
                    
                    developer = self._get_available_member(Role.DEVELOPER, story.id, 
                                                        min(remaining_hours, 8.0), 'development')
                    if developer:
                        work_hours = min(remaining_hours, 8.0 - developer.daily_hours_worked)
                        developer.start_work(Role.DEVELOPER, story.id, work_hours, "Development")
                        story.assigned_members[Role.DEVELOPER] = developer.name
                        yield self.env.timeout(work_hours)
                        developer.end_work()
                        remaining_hours -= work_hours
                    else:
                        yield self.env.timeout(1)
            
            return True
        except Exception as e:
            logger.error(f"Error in development phase for story {story.id}: {str(e)}")
            return False

    def story_review_process(self, story: Story):
        """Process for handling story review phase"""
        try:
            story.start_phase(Phase.PEER_REVIEW)
            review_iterations = 0
            
            while review_iterations < story.max_attempts['review']:
                remaining_hours = story.get_phase_hours('review')
                
                while remaining_hours > 0:
                    with self.resource_pool[Role.REVIEWER].request() as request:
                        yield request
                        
                        reviewer = self._get_available_member(Role.REVIEWER, story.id, 
                                                           min(remaining_hours, 8.0), 'review')
                        if reviewer and reviewer.name != story.assigned_members.get(Role.DEVELOPER):
                            work_hours = min(remaining_hours, 8.0 - reviewer.daily_hours_worked)
                            reviewer.start_work(Role.REVIEWER, story.id, work_hours, "Peer Review")
                            story.assigned_members[Role.REVIEWER] = reviewer.name
                            yield self.env.timeout(work_hours)
                            reviewer.end_work()
                            remaining_hours -= work_hours
                        else:
                            yield self.env.timeout(1)

                if random.random() > 0.3 or review_iterations == story.max_attempts['review'] - 1:
                    break
                    
                review_iterations += 1
                story.review_iterations += 1
                yield from self.handle_rework(story, 'review', 0.2)
            
            story.end_phase(Phase.PEER_REVIEW)
            return True
            
        except Exception as e:
            logger.error(f"Error in review phase for story {story.id}: {str(e)}")
            return False

    def handle_rework(self, story: Story, phase: str, fraction: float):
        """Process for handling rework after review failures"""
        try:
            rework_hours = story.get_phase_hours('dev') * fraction
            
            while rework_hours > 0:
                with self.resource_pool[Role.DEVELOPER].request() as request:
                    yield request
                    
                    developer = self._get_available_member(Role.DEVELOPER, story.id, 
                                                       min(rework_hours, 8.0), f'{phase}_rework')
                    if developer and developer.name == story.assigned_members.get(Role.DEVELOPER):
                        work_hours = min(rework_hours, 8.0 - developer.daily_hours_worked)
                        developer.start_work(Role.DEVELOPER, story.id, work_hours, 
                                          f"{phase.capitalize()} Rework")
                        yield self.env.timeout(work_hours)
                        developer.end_work()
                        rework_hours -= work_hours
                    else:
                        yield self.env.timeout(1)
                        
        except Exception as e:
            logger.error(f"Error in rework for story {story.id} during {phase}: {str(e)}")

    def story_po_review_process(self, story: Story):
        """Process for handling PO review phase"""
        try:
            story.start_phase(Phase.PO_REVIEW)
            po_iterations = 0
            
            while po_iterations < story.max_attempts['po_review']:
                remaining_hours = story.get_phase_hours('po')
                
                while remaining_hours > 0:
                    with self.resource_pool[Role.PO_PRIMARY].request() as request:
                        yield request
                        
                        po = self._get_available_member(Role.PO_PRIMARY, story.id, 
                                                      min(remaining_hours, 8.0), 'po_review')
                        if po:
                            work_hours = min(remaining_hours, 8.0 - po.daily_hours_worked)
                            po.start_work(Role.PO_PRIMARY, story.id, work_hours, "PO Review")
                            story.assigned_members[Role.PO_PRIMARY] = po.name
                            yield self.env.timeout(work_hours)
                            po.end_work()
                            remaining_hours -= work_hours
                        else:
                            yield self.env.timeout(1)

                if random.random() > 0.2 or po_iterations == story.max_attempts['po_review'] - 1:
                    break
                    
                po_iterations += 1
                story.po_review_iterations += 1
                yield from self.handle_rework(story, 'po_review', 0.1)
            
            story.end_phase(Phase.PO_REVIEW)
            return True
            
        except Exception as e:
            logger.error(f"Error in PO review phase for story {story.id}: {str(e)}")
            return False

    def story_validation_process(self, story: Story):
        """Process for handling validation phase"""
        try:
            story.start_phase(Phase.VALIDATION)
            validation_iterations = 0
            
            while validation_iterations < story.max_attempts['validation']:
                remaining_hours = story.get_phase_hours('validation')
                
                while remaining_hours > 0:
                    with self.resource_pool[Role.ADMIN_PRIMARY].request() as request:
                        yield request
                        
                        admin = self._get_available_member(Role.ADMIN_PRIMARY, story.id, 
                                                         min(remaining_hours, 8.0), 'validation')
                        if admin:
                            work_hours = min(remaining_hours, 8.0 - admin.daily_hours_worked)
                            admin.start_work(Role.ADMIN_PRIMARY, story.id, work_hours, "Validation")
                            story.assigned_members[Role.ADMIN_PRIMARY] = admin.name
                            yield self.env.timeout(work_hours)
                            admin.end_work()
                            remaining_hours -= work_hours
                        else:
                            yield self.env.timeout(1)

                if random.random() > 0.15 or validation_iterations == story.max_attempts['validation'] - 1:
                    break
                    
                validation_iterations += 1
                story.validation_iterations += 1
                yield from self.handle_rework(story, 'validation', 0.15)
            
            story.end_phase(Phase.VALIDATION)
            return True
            
        except Exception as e:
            logger.error(f"Error in validation phase for story {story.id}: {str(e)}")
            return False

    def story_lifecycle_process(self, story: Story):
        """Main process for handling a story's complete lifecycle"""
        try:
            # Development Phase
            dev_result = yield from self.story_development_process(story)
            if not dev_result:
                return

            # Check for blocking
            if random.random() < 0.2:  # 20% chance of getting blocked
                story.start_phase(Phase.BLOCKED)
                block_duration = random.lognormvariate(np.log(4), 0.5)  # Reduced from 8 to 4
                yield self.env.timeout(block_duration)
                story.end_phase(Phase.BLOCKED)

            # Peer Review Phase
            review_result = yield from self.story_review_process(story)
            if not review_result:
                return

            # PO Review Phase
            po_result = yield from self.story_po_review_process(story)
            if not po_result:
                return

            # Validation Phase
            validation_result = yield from self.story_validation_process(story)
            if not validation_result:
                return

            story.phase = Phase.DONE
            story.completion_time = self.env.now
            self.completed_points += story.points
            logger.info(f"Story {story.id} ({story.points} pts) completed in {story.completion_time - story.start_time:.1f} hours")
            
        except Exception as e:
            logger.error(f"Error in story {story.id} lifecycle: {str(e)}")

    def ceremonies_process(self):
        """Process for handling sprint ceremonies"""
        while True:
            # Start of sprint
            self._conduct_meeting(Meeting.SPRINT_PLANNING, 2)  # Reduced from 4 to 2
            yield self.env.timeout(8)  # Wait a day after planning

            # Daily standups
            for day in range(self.sprint_days - 1):  # -1 to account for planning day
                self._conduct_meeting(Meeting.STANDUP, 0.5)
                yield self.env.timeout(8)  # Wait a day

            # End of sprint ceremonies
            self._conduct_meeting(Meeting.REVIEW, 1)
            self._conduct_meeting(Meeting.RETRO, 1)
            
            # Record sprint metrics and prepare for next sprint
            self._record_sprint_metrics()
            self.sprint_number += 1
            logger.info(f"\nStarting Sprint {self.sprint_number}")
            logger.info(f"Completed Points: {self.completed_points}/{self.total_points}")

    def workday_process(self):
        """Process for managing workday resets"""
        while True:
            # Reset daily hours
            for member in self.team_members:
                member.daily_hours_worked = 0.0
                
            # Reset weekly hours at start of week
            if self.env.now % 40 == 0:
                for member in self.team_members:
                    member.weekly_hours_worked = 0.0
                    
            yield self.env.timeout(8)  # Wait a workday

    def run_simulation(self):
        """Run the complete simulation"""
        def _run():
            try:
                # Generate stories
                story_id = 0
                points_remaining = self.total_points
                while points_remaining > 0:
                    possible_points = [p for p in [1, 2, 3, 5, 8] if p <= points_remaining]
                    if not possible_points:
                        break
                    points = random.choice(possible_points)
                    self.stories.append(Story(id=story_id, points=points, env=self.env))
                    points_remaining -= points
                    story_id += 1

                logger.info(f"Generated {len(self.stories)} stories totaling {self.total_points} points")

                # Start core processes
                self.env.process(self.ceremonies_process())
                self.env.process(self.workday_process())

                # Start story lifecycles with slight delays to prevent resource contention at start
                for i, story in enumerate(self.stories):
                    self.env.process(self.story_lifecycle_process(story))
                    yield self.env.timeout(random.uniform(0, 4))  # Stagger story starts

                # Run simulation
                yield self.env.timeout(self.sprint_days * 8 * 6)  # Run for 6 sprints max

            except Exception as e:
                logger.error(f"Error in simulation run: {str(e)}")
                raise
            
        # Create and start the simulation process
        sim_process = self.env.process(_run())
        
        # Run the simulation
        try:
            self.env.run(until=self.sprint_days * 8 * 6)  # Run for 6 sprints max
        except Exception as e:
            logger.error(f"Error running simulation environment: {str(e)}")
            raise
            
        return self.analyze_results()

    def _record_sprint_metrics(self):
        """Record metrics for the completed sprint"""
        try:
            sprint_metrics = {
                'sprint_number': self.sprint_number,
                'completed_points': self.completed_points,
                'velocity': len([s for s in self.stories if s.completion_time and 
                               s.completion_time <= self.env.now and 
                               s.completion_time > (self.sprint_number - 1) * self.sprint_days * 8]),
                'team_metrics': {
                    member.name: {
                        'hours_by_role': dict(member.total_hours_worked),
                        'context_switches': member.context_switches,
                        'failed_assignments': member.failed_assignments,
                        'utilization': sum(member.total_hours_worked.values()) / 
                                     (self.sprint_number * self.sprint_days * 8)
                    }
                    for member in self.team_members
                },
                'story_metrics': [
                    {
                        'id': story.id,
                        'points': story.points,
                        'cycle_time': story.completion_time - story.start_time if story.completion_time else None,
                        'time_in_phases': dict(story.time_in_phases),
                        'review_iterations': story.review_iterations,
                        'po_review_iterations': story.po_review_iterations,
                        'validation_iterations': story.validation_iterations
                    }
                    for story in self.stories if story.completion_time and 
                    story.completion_time <= self.env.now and 
                    story.completion_time > (self.sprint_number - 1) * self.sprint_days * 8
                ],
                'bottlenecks': {
                    role.name: count for role, count in self.failed_resource_requests.items()
                },
                'wip': len([s for s in self.stories if s.start_time and not s.completion_time])
            }
            
            self.sprint_metrics.append(sprint_metrics)
            
        except Exception as e:
            logger.error(f"Error recording sprint metrics: {str(e)}")

    def analyze_results(self):
        """Analyze simulation results and generate insights"""
        results = {
            'completed_points': self.completed_points,
            'total_sprints': self.sprint_number,
            'average_velocity': self.completed_points / max(1, self.sprint_number),
            'sprint_metrics': self.sprint_metrics,
            'bottlenecks': self._analyze_bottlenecks(),
            'team_utilization': self._analyze_team_utilization(),
            'cycle_time_analysis': self._analyze_cycle_times()
        }
        
        return results

    def _analyze_bottlenecks(self):
        """Analyze system bottlenecks"""
        bottlenecks = {
            'resource_contention': {
                role.name: count / max(1, self.sprint_number)
                for role, count in self.failed_resource_requests.items()
            },
            'phase_durations': defaultdict(list),
            'rework_rates': {
                'peer_review': sum(s.review_iterations for s in self.stories) / max(1, len(self.stories)),
                'po_review': sum(s.po_review_iterations for s in self.stories) / max(1, len(self.stories)),
                'validation': sum(s.validation_iterations for s in self.stories) / max(1, len(self.stories))
            }
        }
        
        # Analyze phase durations
        for story in self.stories:
            if story.completion_time:
                for phase, duration in story.time_in_phases.items():
                    bottlenecks['phase_durations'][phase.value].append(duration)
        
        # Calculate statistics for phase durations
        bottlenecks['phase_statistics'] = {
            phase: {
                'mean': np.mean(durations),
                'median': np.median(durations),
                'std': np.std(durations),
                'min': min(durations),
                'max': max(durations)
            }
            for phase, durations in bottlenecks['phase_durations'].items()
            if durations
        }
        
        return bottlenecks

    def _analyze_team_utilization(self):
        """Analyze team utilization patterns"""
        return {
            member.name: {
                'total_hours': dict(member.total_hours_worked),
                'utilization_rate': sum(member.total_hours_worked.values()) / 
                                  (self.sprint_number * self.sprint_days * 8),
                'context_switches_per_sprint': member.context_switches / max(1, self.sprint_number),
                'primary_role_focus': (member.total_hours_worked.get(member.primary_role, 0) /
                                     max(1, sum(member.total_hours_worked.values())))
            }
            for member in self.team_members
        }

    def _analyze_cycle_times(self):
        """Analyze story cycle times"""
        completed_stories = [s for s in self.stories if s.completion_time]
        if not completed_stories:
            return {}
            
        cycle_times = [s.completion_time - s.start_time for s in completed_stories]
        cycle_times_by_points = defaultdict(list)
        for story in completed_stories:
            cycle_times_by_points[story.points].append(
                story.completion_time - story.start_time)
            
        return {
            'overall': {
                'mean': np.mean(cycle_times),
                'median': np.median(cycle_times),
                'std': np.std(cycle_times),
                'min': min(cycle_times),
                'max': max(cycle_times)
            },
            'by_points': {
                points: {
                    'mean': np.mean(times),
                    'median': np.median(times),
                    'std': np.std(times)
                }
                for points, times in cycle_times_by_points.items()
            }
        }
