import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from typing import Dict, Any
import os

# Create images directory if it doesn't exist
os.makedirs('images', exist_ok=True)

def plot_velocity_trend(sprint_metrics):
    """Plot velocity trend over sprints"""
    velocities = [sprint['velocity'] for sprint in sprint_metrics]
    plt.figure(figsize=(10, 6))
    plt.plot(range(1, len(velocities) + 1), velocities, marker='o')
    plt.title('Velocity Trend Over Sprints')
    plt.xlabel('Sprint Number')
    plt.ylabel('Story Points Completed')
    plt.grid(True)
    plt.savefig('images/sprint_velocity.png')
    plt.close()

def plot_bottlenecks(bottlenecks):
    """Plot detailed bottleneck analysis"""
    plt.figure(figsize=(15, 10))
    
    # Resource contention
    plt.subplot(2, 2, 1)
    contention = bottlenecks['resource_contention']
    roles = list(contention.keys())
    values = list(contention.values())
    colors = ['red' if v > 5 else 'orange' if v > 2 else 'green' for v in values]
    plt.bar(roles, values, color=colors)
    plt.title('Resource Contention by Role')
    plt.xlabel('Role')
    plt.ylabel('Failed Requests per Sprint')
    plt.xticks(rotation=45)
    
    # Phase durations
    plt.subplot(2, 2, 2)
    phase_stats = bottlenecks['phase_statistics']
    phases = list(phase_stats.keys())
    means = [stats['mean'] for stats in phase_stats.values()]
    stds = [stats['std'] for stats in phase_stats.values()]
    plt.bar(phases, means, yerr=stds)
    plt.title('Average Duration by Phase')
    plt.xlabel('Phase')
    plt.ylabel('Hours')
    plt.xticks(rotation=45)
    
    # Rework rates
    plt.subplot(2, 2, 3)
    rework = bottlenecks['rework_rates']
    plt.bar(rework.keys(), rework.values())
    plt.title('Rework Rates by Review Type')
    plt.xlabel('Review Type')
    plt.ylabel('Rework Rate')
    plt.xticks(rotation=45)
    
    # Wait times
    plt.subplot(2, 2, 4)
    phase_wait_times = {phase: stats['max'] - stats['mean'] 
                      for phase, stats in phase_stats.items()}
    plt.bar(phase_wait_times.keys(), phase_wait_times.values())
    plt.title('Maximum Wait Times by Phase')
    plt.xlabel('Phase')
    plt.ylabel('Hours')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('images/resource_util.png')
    plt.close()

def plot_team_utilization(team_utilization):
    """Plot team utilization patterns"""
    plt.figure(figsize=(15, 6))
    
    # Overall utilization
    utilization_rates = {name: data['utilization_rate'] 
                       for name, data in team_utilization.items()}
    
    plt.subplot(1, 2, 1)
    plt.bar(utilization_rates.keys(), utilization_rates.values())
    plt.title('Team Member Utilization')
    plt.xlabel('Team Member')
    plt.ylabel('Utilization Rate')
    plt.xticks(rotation=45)
    
    # Context switches
    context_switches = {name: data['context_switches_per_sprint']
                      for name, data in team_utilization.items()}
    
    plt.subplot(1, 2, 2)
    plt.bar(context_switches.keys(), context_switches.values())
    plt.title('Context Switches per Sprint')
    plt.xlabel('Team Member')
    plt.ylabel('Switches per Sprint')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('images/team_utilization.png')
    plt.close()

def plot_cycle_times(cycle_analysis):
    """Plot cycle time analysis"""
    plt.figure(figsize=(10, 6))
    
    # Plot cycle times by story size
    story_sizes = sorted(list(set(story.points for story in cycle_analysis['stories'])))
    cycle_times = [[] for _ in story_sizes]
    
    for story in cycle_analysis['stories']:
        idx = story_sizes.index(story.points)
        cycle_times[idx].append(story.completion_time - story.start_time)
    
    # Calculate statistics
    medians = [np.median(times) if times else 0 for times in cycle_times]
    p75 = [np.percentile(times, 75) if times else 0 for times in cycle_times]
    p25 = [np.percentile(times, 25) if times else 0 for times in cycle_times]
    
    # Create box plot
    plt.boxplot(cycle_times, labels=story_sizes)
    plt.xlabel('Story Points')
    plt.ylabel('Cycle Time (hours)')
    plt.title('Cycle Time Distribution by Story Size')
    
    plt.tight_layout()
    plt.savefig('images/cycle_time_dist.png')
    plt.close()

def plot_story_flow(sprint_metrics):
    """Plot cumulative flow diagram"""
    plt.figure(figsize=(12, 6))
    
    # Extract data for cumulative flow
    sprints = range(1, len(sprint_metrics) + 1)
    started = np.cumsum([sprint['stories_started'] for sprint in sprint_metrics])
    completed = np.cumsum([sprint['stories_completed'] for sprint in sprint_metrics])
    
    plt.fill_between(sprints, started, label='In Progress', alpha=0.3)
    plt.fill_between(sprints, completed, label='Completed', alpha=0.3)
    plt.plot(sprints, started, 'b-', label='Started')
    plt.plot(sprints, completed, 'g-', label='Completed')
    
    plt.title('Story Flow Over Time')
    plt.xlabel('Sprint Number')
    plt.ylabel('Cumulative Stories')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('images/story_flow.png')
    plt.close()

def print_summary(results: Dict[str, Any]):
    """Print summary statistics"""
    print("\nSIMULATION SUMMARY")
    print("=" * 50)
    print(f"Total Points Completed: {results['completed_points']}")
    print(f"Number of Sprints: {results['total_sprints']}")
    print(f"Average Velocity: {results['average_velocity']:.1f} points/sprint")
    
    print("\nBOTTLENECKS")
    print("-" * 50)
    for role, rate in results['bottlenecks']['resource_contention'].items():
        print(f"{role}: {rate:.1f} failed requests/sprint")
        
    print("\nREWORK RATES")
    print("-" * 50)
    rework = results['bottlenecks']['rework_rates']
    print(f"Peer Review: {rework['peer_review']:.1%}")
    print(f"PO Review: {rework['po_review']:.1%}")
    print(f"Validation: {rework['validation']:.1%}")
    
    print("\nCYCLE TIMES")
    print("-" * 50)
    cycle = results['cycle_time_analysis']['overall']
    print(f"Mean: {cycle['mean']:.1f} hours")
    print(f"Median: {cycle['median']:.1f} hours")
    print(f"Std Dev: {cycle['std']:.1f} hours")

def visualize_results(results: Dict[str, Any]):
    """Generate all visualizations and print summary"""
    plot_velocity_trend(results['sprint_metrics'])
    plot_bottlenecks(results['bottlenecks'])
    plot_team_utilization(results['team_utilization'])
    plot_cycle_times(results['cycle_time_analysis'])
    plot_story_flow(results['sprint_metrics'])
    print_summary(results)
