import os
import re
from pathlib import Path
from dotenv import load_dotenv


class Config:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        load_dotenv(self.base_dir / ".env")

        self.cache_dir = self.base_dir / "cache"
        self.output_dir = self.base_dir / "output"
        self.cache_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        self._load_user_info()

        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.headless = os.getenv("HEADLESS", "false").lower() == "true"
        self.news_count = int(os.getenv("NEWS_COUNT", "15"))
        self.analysis_days = int(os.getenv("ANALYSIS_DAYS", "120"))
        self.save_html_report = os.getenv("SAVE_HTML_REPORT", "true").lower() == "true"
        self.open_browser_dashboard = os.getenv("OPEN_BROWSER_DASHBOARD", "true").lower() == "true"

        self.use_ai = bool(self.openai_api_key)

    def _load_user_info(self):
        user_info_path = self.base_dir / "UserInfo.md"
        if not user_info_path.exists():
            raise FileNotFoundError(
                "UserInfo.md 파일이 없습니다.\n"
                "UserInfo.md 파일을 생성하고 이름/생년월일/전화번호를 입력해주세요."
            )

        content = user_info_path.read_text(encoding="utf-8")

        name_match = re.search(r"이름:\s*(.+)", content)
        birth_match = re.search(r"생년월일:\s*(.+)", content)
        phone_match = re.search(r"전화번호:\s*(.+)", content)

        self.user_name = name_match.group(1).strip() if name_match else ""
        self.user_birth = birth_match.group(1).strip() if birth_match else ""
        self.user_phone = phone_match.group(1).strip() if phone_match else ""

        if not self.user_phone:
            raise ValueError(
                "UserInfo.md에 전화번호가 없습니다.\n"
                "전화번호: 010-XXXX-XXXX 형식으로 입력해주세요."
            )
