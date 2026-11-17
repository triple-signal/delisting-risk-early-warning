"""테스트 공통 설정. 테스트는 data/·.env·인터넷 없이 돈다 (CI에서도 같은 조건)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
