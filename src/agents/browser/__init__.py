"""Browser automation - Captcha solving, Firefox control, utilities.

Components:
- captcha: Captcha solving and bypass
- firefox: Firefox browser automation
- utils: Page utilities (PageStep, find_element)
- page_utils: Page manipulation helpers
"""

from .captcha import setup_stealth_only, solve_captcha_on_page
from .firefox import run_registration_firefox
from .utils import PageStep, find_element

__all__ = [
    "setup_stealth_only",
    "solve_captcha_on_page",
    "run_registration_firefox",
    "PageStep",
    "find_element",
]