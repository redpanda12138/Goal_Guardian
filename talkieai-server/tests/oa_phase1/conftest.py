import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER / "mas" / "OA"))
sys.path.insert(0, str(SERVER / "mas" / "common"))
