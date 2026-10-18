"""Compatibility entry for the correlated live comparison driver."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_compare import main
if __name__=='__main__':main()
