#!/usr/bin/env python3
"""
Page Utilities - надёжная работа с элементами страницы.
Универсальные функции с retry, множественными селекторами и детальным логированием.
"""

import time
import random
from pathlib import Path
from typing import List, Optional, Callable, Any


class PageStep:
    """Контекст для выполнения шага с логированием и скриншотами."""
    
    def __init__(self, page, step_name: str, log_fn=None, screenshot_dir: Path = None):
        self.page = page
        self.step_name = step_name
        self.log = log_fn or print
        self.screenshot_dir = screenshot_dir
        self.start_time = time.time()
    
    def __enter__(self):
        self.log(f"  → [{self.step_name}] Starting...")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if exc_type:
            self.log(f"  ✗ [{self.step_name}] Failed: {exc_val} ({elapsed:.1f}s)")
            self._save_screenshot(f"error_{self.step_name}")
            return False  # propagate exception
        self.log(f"  ✓ [{self.step_name}] Done ({elapsed:.1f}s)")
        return True
    
    def _save_screenshot(self, name: str):
        if self.screenshot_dir:
            try:
                path = self.screenshot_dir / f"{name}_{int(time.time())}.png"
                self.page.screenshot(path=str(path))
                self.log(f"    📸 Screenshot: {path.name}")
            except:
                pass
    
    def screenshot(self, name: str = None):
        self._save_screenshot(name or self.step_name)


def find_element(page, selectors: List[str], timeout: int = 8000, log_fn=None):
    """Найти элемент по списку селекторов с retry.
    
    Args:
        page: Playwright page object
        selectors: Список CSS селекторов для поиска
        timeout: Таймаут в миллисекундах
        log_fn: Функция логирования
    
    Returns:
        Locator or None
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    
    deadline = time.time() + (timeout / 1000.0)
    
    while time.time() < deadline:
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=200):
                    return el
            except:
                pass
        time.sleep(0.2)
    
    if log_fn:
        log_fn(f"    Element not found: {selectors[0]} (tried {len(selectors)} selectors)")
    return None


def find_and_click(page, selectors: List[str], timeout: int = 8000, 
                   retry: int = 2, delay: float = 0.3, log_fn=None) -> bool:
    """Найти и кликнуть элемент с retry.
    
    Args:
        page: Playwright page
        selectors: Список селекторов
        timeout: Таймаут поиска
        retry: Количество попыток клика
        delay: Задержка между попытками
    
    Returns:
        True если успешно кликнули
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    
    el = find_element(page, selectors, timeout, log_fn)
    if not el:
        return False
    
    for attempt in range(retry):
        try:
            if el.is_enabled(timeout=1000):
                el.click(timeout=5000)
                time.sleep(delay)
                return True
        except Exception as e:
            if log_fn:
                log_fn(f"    Click attempt {attempt+1} failed: {str(e)[:50]}")
            time.sleep(0.5)
    
    # Fallback: JavaScript click
    try:
        page.evaluate(f'''() => {{
            for (const sel of {selectors}) {{
                const el = document.querySelector(sel);
                if (el) {{ el.click(); return true; }}
            }}
            // Try by text content
            for (const el of document.querySelectorAll('button, a, [role="button"]')) {{
                const txt = (el.textContent || el.innerText || '').toLowerCase();
                for (const sel of {selectors}) {{
                    if (txt.includes(sel.toLowerCase().replace('text=', '').replace(':', ''))) {{
                        el.click();
                        return true;
                    }}
                }}
            }}
            return false;
        }}''')
        time.sleep(delay)
        return True
    except:
        return False


def find_and_fill(page, selectors: List[str], value: str, timeout: int = 8000,
                  clear_first: bool = True, human_typing: bool = False,
                  log_fn=None) -> bool:
    """Найти поле и заполнить его.
    
    Args:
        page: Playwright page
        selectors: Список селекторов
        value: Значение для ввода
        clear_first: Очистить поле перед вводом
        human_typing: Имитировать человеческий ввод с задержками
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    
    el = find_element(page, selectors, timeout, log_fn)
    if not el:
        return False
    
    try:
        el.click(timeout=2000)
        time.sleep(0.2)
        
        if clear_first:
            el.fill("", timeout=2000)
            time.sleep(0.1)
        
        if human_typing:
            for char in value:
                el.type(char, delay=random.randint(30, 100))
        else:
            el.fill(value, timeout=5000)
        
        return True
    except Exception as e:
        if log_fn:
            log_fn(f"    Fill failed: {str(e)[:50]}")
        return False


def wait_for_navigation(page, url_pattern: str = None, timeout: int = 30000) -> bool:
    """Ждать навигации на страницу с определённым URL паттерном."""
    deadline = time.time() + (timeout / 1000.0)
    
    while time.time() < deadline:
        try:
            current = page.url
            if url_pattern and url_pattern in current:
                return True
            if not url_pattern:
                return True
        except:
            pass
        time.sleep(0.3)
    
    return False


def wait_for_download(download_dir: str, pattern: str = "kaggle*.json", 
                      timeout: int = 30, log_fn=None) -> Optional[str]:
    """Ждать появления файла в директории загрузок."""
    import glob
    import os
    
    deadline = time.time() + timeout
    seen = set(glob.glob(os.path.join(download_dir, pattern)))
    
    while time.time() < deadline:
        files = glob.glob(os.path.join(download_dir, pattern))
        for f in files:
            if f not in seen:
                if log_fn:
                    log_fn(f"    Download detected: {os.path.basename(f)}")
                return f
        time.sleep(0.5)
    
    return None


def scroll_to_find(page, selectors: List[str], direction: str = "down",
                   max_scrolls: int = 5, log_fn=None):
    """Скроллить страницу в поисках элемента."""
    if isinstance(selectors, str):
        selectors = [selectors]
    
    for _ in range(max_scrolls):
        el = find_element(page, selectors, timeout=1000)
        if el:
            return el
        
        if direction == "down":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        else:
            page.evaluate("window.scrollTo(0, 0)")
        
        time.sleep(0.5)
    
    if log_fn:
        log_fn(f"    Element not found after {max_scrolls} scrolls")
    return None


def check_url(page, expected: str, log_fn=None) -> bool:
    """Проверить текущий URL."""
    try:
        current = page.url
        if expected in current:
            return True
        if log_fn:
            log_fn(f"    URL mismatch: expected '{expected}' in '{current}'")
        return False
    except Exception as e:
        if log_fn:
            log_fn(f"    URL check error: {e}")
        return False


def get_element_text(page, selectors: List[str], timeout: int = 3000) -> Optional[str]:
    """Получить текст элемента."""
    el = find_element(page, selectors, timeout)
    if el:
        try:
            return el.text_content(timeout=2000)
        except:
            pass
    return None


def is_checkbox_checked(page, selectors: List[str]) -> bool:
    """Проверить, отмечен ли чекбокс."""
    el = find_element(page, selectors, timeout=1000)
    if el:
        try:
            return el.is_checked()
        except:
            pass
    return False


def check_all_checkboxes(page, selectors: List[str], log_fn=None) -> int:
    """Отметить все найденные чекбоксы."""
    if isinstance(selectors, str):
        selectors = [selectors]
    
    checked = 0
    for sel in selectors:
        try:
            for el in page.locator(sel).all():
                if el.is_visible(timeout=500) and not el.is_checked():
                    el.click()
                    checked += 1
                    time.sleep(0.1)
        except:
            pass
    
    if log_fn and checked:
        log_fn(f"    Checked {checked} boxes")
    return checked


def dismiss_modals(page, log_fn=None):
    """Закрыть все модальные окна (Escape, клик вне модала)."""
    try:
        # Try Escape
        page.keyboard.press("Escape")
        time.sleep(0.3)
        
        # Try clicking outside
        page.mouse.click(10, 10)
        time.sleep(0.2)
        
        if log_fn:
            log_fn("    Dismissed modals")
    except:
        pass


def extract_page_errors(page) -> List[str]:
    """Извлечь текст ошибок со страницы."""
    errors = []
    error_selectors = [
        '[class*="error"]',
        '[class*="alert"]',
        '[role="alert"]',
        '.form-error',
        '.error-message',
        '[data-error]',
    ]
    
    for sel in error_selectors:
        try:
            for el in page.locator(sel).all():
                if el.is_visible(timeout=200):
                    text = el.text_content()
                    if text and text.strip():
                        errors.append(text.strip())
        except:
            pass
    
    return errors


def smart_click_button(page, texts: List[str], timeout: int = 10000, log_fn=None) -> bool:
    """Умный поиск кнопки по тексту с множественными стратегиями."""
    if isinstance(texts, str):
        texts = [texts]
    
    # Strategy 1: Playwright text locator
    for text in texts:
        try:
            btn = page.locator(f"text={text}").first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=5000)
                if log_fn:
                    log_fn(f"    Clicked button: {text}")
                return True
        except:
            pass
    
    # Strategy 2: Button with has-text
    for text in texts:
        try:
            btn = page.locator(f"button:has-text('{text}')").first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=5000)
                return True
        except:
            pass
    
    # Strategy 3: JavaScript search
    js_array = ', '.join(f"'{t}'" for t in texts)
    try:
        result = page.evaluate(f'''() => {{
            const texts = [{js_array}];
            // Check buttons
            for (const btn of document.querySelectorAll('button, [role="button"], a.btn, input[type="submit"]')) {{
                const txt = (btn.textContent || btn.innerText || btn.value || '').toLowerCase();
                for (const t of texts) {{
                    if (txt.includes(t.toLowerCase())) {{
                        btn.click();
                        return t;
                    }}
                }}
            }}
            // Check divs/spans with click handlers
            for (const el of document.querySelectorAll('[onclick], [data-action]')) {{
                const txt = (el.textContent || el.innerText || '').toLowerCase();
                for (const t of texts) {{
                    if (txt.includes(t.toLowerCase())) {{
                        el.click();
                        return t;
                    }}
                }}
            }}
            return null;
        }}''')
        if result:
            if log_fn:
                log_fn(f"    JS clicked: {result}")
            return True
    except:
        pass
    
    if log_fn:
        log_fn(f"    Button not found: {texts}")
    return False


def wait_for_element_gone(page, selectors: List[str], timeout: int = 5000) -> bool:
    """Ждать исчезновения элемента."""
    if isinstance(selectors, str):
        selectors = [selectors]
    
    deadline = time.time() + (timeout / 1000.0)
    
    while time.time() < deadline:
        visible = False
        for sel in selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=200):
                    visible = True
                    break
            except:
                pass
        
        if not visible:
            return True
        time.sleep(0.2)
    
    return False


def safe_goto(page, url: str, timeout: int = 30000, wait_until: str = "networkidle",
              retry: int = 2, log_fn=None) -> bool:
    """Безопасная навигация с retry."""
    for attempt in range(retry):
        try:
            page.goto(url, timeout=timeout, wait_until=wait_until)
            return True
        except Exception as e:
            if log_fn:
                log_fn(f"    Navigation attempt {attempt+1} failed: {str(e)[:50]}")
            time.sleep(1)
    
    # Last attempt with domcontentloaded
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        return True
    except Exception as e:
        if log_fn:
            log_fn(f"    Navigation failed: {e}")
        return False
