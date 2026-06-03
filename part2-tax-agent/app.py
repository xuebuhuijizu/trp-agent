from pathlib import Path

from dotenv import load_dotenv

from tax_agent.delivery.http_api import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8-sig")

app = create_app()
