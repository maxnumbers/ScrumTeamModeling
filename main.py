import logging
from src.simulation import SprintSimulation
from src.visualization import visualize_results

def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('sprint_simulation')

def run_simulation(total_points: int = 50):
    """Run the scrum team simulation with visualization"""
    logger = setup_logging()
    logger.info(f"Starting simulation with {total_points} story points")
    
    try:
        # Initialize and run simulation
        sim = SprintSimulation(total_points=total_points)
        results = sim.run_simulation()
        
        # Generate visualizations and print summary
        visualize_results(results)
        
        logger.info("Simulation completed successfully")
        return results
        
    except Exception as e:
        logger.error(f"Error running simulation: {str(e)}")
        raise

if __name__ == "__main__":
    # Run simulation with 50 story points
    results = run_simulation(120)
