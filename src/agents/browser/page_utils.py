"""
Compatibility alias for src.agents.browser.utils
Old import path was page_utils, now it's utils.
"""
from src.agents.browser.utils import *

__all__ = ['PageStep', 'find_element', 'find_and_fill', 'find_and_click', 
           'smart_click_button', 'safe_goto', 'check_url', 
           'check_all_checkboxes', 'extract_page_errors', 
           'scroll_to_find', 'wait_for_element_gone']

