from pathlib import Path
from config.settings import config
from utils.logging import setup_logging

def main():
    
    logger = setup_logging(config.paths.log_path)
    logger.info("Starting video processor")

    # Validate configuration
    if errors := config.validate():
        logger.error("Configuration errors found, exiting")
        return
    






    
    logger.info("Processing complete")

if __name__ == "__main__":
    main()
