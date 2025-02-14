import sys
import logging
from pathlib import Path
from packaging.requirements import Requirement
import pkg_resources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_requirements(req_file: Path) -> bool:
    """Check if all requirements in a file are installed"""
    if not req_file.exists():
        logger.error(f"Requirements file not found: {req_file}")
        return False
        
    logger.info(f"Checking {req_file}...")
    missing = []

    try:
        with open(req_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-r'):
                    try:
                        pkg_resources.require(line)
                    except (pkg_resources.DistributionNotFound, 
                           pkg_resources.VersionConflict) as e:
                        missing.append(f"{line} ({str(e)})")
    except Exception as e:
        logger.error(f"Error reading {req_file}: {e}")
        return False
    
    if missing:
        logger.error(f"Missing/conflicting packages in {req_file.name}:")
        for pkg in missing:
            logger.error(f"  - {pkg}")
        return False
    
    logger.info(f"✓ All requirements satisfied in {req_file.name}")
    return True

def main():
    # Get the actual project root (where the script is located)
    root = Path(__file__).parent
    
    req_files = [
        root / "requirements-base.txt",
        root / "backend" / "requirements.txt",
        root / "frontend" / "requirements.txt",
        root / "requirements-dev.txt"
    ]

    logger.info(f"Project root: {root}")
    all_ok = True
    
    for req_file in req_files:
        if not check_requirements(req_file):
            all_ok = False
    
    if all_ok:
        logger.info("✅ All dependency checks passed!")
    else:
        logger.error("❌ Some dependencies are missing or have conflicts")
    
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()