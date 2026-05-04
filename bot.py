from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / '.env')

import shared_data

shared_data.load_all_data()

from bot_core import run_bot


if __name__ == '__main__':
    run_bot()
