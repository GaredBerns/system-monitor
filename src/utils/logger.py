#!/usr/bin/env python3
"""
ENHANCED LOGGING SYSTEM
Улучшенная система логирования с цветами, уровнями и форматированием
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

# Цветовые коды ANSI
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Основные цвета
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Яркие цвета
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    
    # Фоны
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'

class ColoredFormatter(logging.Formatter):
    """Форматтер с цветами для разных уровней"""
    
    FORMATS = {
        logging.DEBUG: Colors.CYAN + '%(asctime)s | %(name)s | DEBUG | %(message)s' + Colors.RESET,
        logging.INFO: Colors.GREEN + '%(asctime)s | %(name)s | INFO | %(message)s' + Colors.RESET,
        logging.WARNING: Colors.YELLOW + '%(asctime)s | %(name)s | WARNING | %(message)s' + Colors.RESET,
        logging.ERROR: Colors.RED + '%(asctime)s | %(name)s | ERROR | %(message)s' + Colors.RESET,
        logging.CRITICAL: Colors.BG_RED + Colors.WHITE + '%(asctime)s | %(name)s | CRITICAL | %(message)s' + Colors.RESET,
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

class EnhancedLogger:
    """Улучшенный логгер с дополнительными функциями"""
    
    def __init__(self, name: str, log_dir: str = "logs", console_level=logging.INFO, file_level=logging.DEBUG):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Создаём логгер
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # Console handler с цветами
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(ColoredFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler без цветов (основной лог)
        log_file = self.log_dir / f"{name}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # JSON handler для структурированных логов
        json_log_file = self.log_dir / f"{name}_json.log"
        self.json_handler = logging.FileHandler(json_log_file, encoding='utf-8')
        self.json_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.json_handler)
        
        # Error handler (отдельный файл для ошибок)
        error_log_file = self.log_dir / f"{name}_errors.log"
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
        
        # Счётчики
        self.stats = {
            'debug': 0,
            'info': 0,
            'warning': 0,
            'error': 0,
            'critical': 0
        }
    
    def debug(self, msg, **kwargs):
        """Debug сообщение"""
        self.stats['debug'] += 1
        self.logger.debug(msg, **kwargs)
    
    def info(self, msg, **kwargs):
        """Info сообщение"""
        self.stats['info'] += 1
        self.logger.info(msg, **kwargs)
    
    def warning(self, msg, **kwargs):
        """Warning сообщение"""
        self.stats['warning'] += 1
        self.logger.warning(msg, **kwargs)
    
    def error(self, msg, **kwargs):
        """Error сообщение"""
        self.stats['error'] += 1
        self.logger.error(msg, **kwargs)
    
    def critical(self, msg, **kwargs):
        """Critical сообщение"""
        self.stats['critical'] += 1
        self.logger.critical(msg, **kwargs)
    
    def success(self, msg):
        """Success сообщение (зелёный)"""
        self.logger.info(f"{Colors.BRIGHT_GREEN}✓ {msg}{Colors.RESET}")
    
    def fail(self, msg):
        """Fail сообщение (красный)"""
        self.logger.error(f"{Colors.BRIGHT_RED}✗ {msg}{Colors.RESET}")
    
    def section(self, title):
        """Секция (заголовок)"""
        line = "=" * 79
        self.logger.info(f"\n{Colors.BOLD}{Colors.CYAN}{line}{Colors.RESET}")
        self.logger.info(f"{Colors.BOLD}{Colors.CYAN}{title.center(79)}{Colors.RESET}")
        self.logger.info(f"{Colors.BOLD}{Colors.CYAN}{line}{Colors.RESET}\n")
    
    def subsection(self, title):
        """Подсекция"""
        self.logger.info(f"\n{Colors.BOLD}{Colors.BLUE}>>> {title}{Colors.RESET}")
    
    def progress(self, current, total, msg=""):
        """Прогресс"""
        percent = int(current * 100 / total)
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        self.logger.info(
            f"{Colors.CYAN}[{bar}] {percent}% {msg}{Colors.RESET}"
        )
    
    def table(self, headers, rows):
        """Таблица"""
        # Вычисляем ширину колонок
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Заголовок
        header_line = " | ".join(
            h.ljust(w) for h, w in zip(headers, col_widths)
        )
        separator = "-+-".join("-" * w for w in col_widths)
        
        self.logger.info(f"\n{Colors.BOLD}{header_line}{Colors.RESET}")
        self.logger.info(separator)
        
        # Строки
        for row in rows:
            row_line = " | ".join(
                str(cell).ljust(w) for cell, w in zip(row, col_widths)
            )
            self.logger.info(row_line)
        
        self.logger.info("")
    
    def json_pretty(self, data, title=""):
        """JSON с форматированием"""
        import json
        if title:
            self.subsection(title)
        
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        for line in json_str.split('\n'):
            self.logger.info(f"{Colors.CYAN}{line}{Colors.RESET}")
    
    def exception(self, msg="Exception occurred"):
        """Exception с traceback"""
        self.stats['error'] += 1
        self.logger.exception(msg)
    
    def log_json(self, event_type: str, data: dict):
        """Структурированный JSON лог"""
        import json
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'logger': self.name,
            'event_type': event_type,
            'data': data
        }
        self.json_handler.stream.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        self.json_handler.stream.flush()
    
    def log_api_call(self, method: str, endpoint: str, status: int, duration: float, **kwargs):
        """Лог API вызова"""
        self.log_json('api_call', {
            'method': method,
            'endpoint': endpoint,
            'status': status,
            'duration_ms': round(duration * 1000, 2),
            **kwargs
        })
        
        status_color = Colors.GREEN if status < 400 else Colors.RED
        self.logger.info(
            f"{status_color}{method} {endpoint} [{status}] {duration*1000:.2f}ms{Colors.RESET}"
        )
    
    def log_task(self, task_id: str, task_type: str, status: str, **kwargs):
        """Лог задачи"""
        self.log_json('task', {
            'task_id': task_id,
            'task_type': task_type,
            'status': status,
            **kwargs
        })
        
        status_icon = "✓" if status == "completed" else "⏳" if status == "pending" else "✗"
        self.logger.info(f"{status_icon} Task {task_id[:8]} [{task_type}] -> {status}")
    
    def log_agent(self, agent_id: str, action: str, **kwargs):
        """Лог агента"""
        self.log_json('agent', {
            'agent_id': agent_id,
            'action': action,
            **kwargs
        })
        
        action_color = Colors.GREEN if action == "register" else Colors.YELLOW
        self.logger.info(f"{action_color}[Agent] {agent_id[:8]} -> {action}{Colors.RESET}")
    
    def log_security(self, event: str, severity: str, details: dict):
        """Лог безопасности"""
        self.log_json('security', {
            'event': event,
            'severity': severity,
            'details': details
        })
        
        if severity == 'critical':
            self.critical(f"🔒 SECURITY: {event}")
        elif severity == 'high':
            self.error(f"🔒 SECURITY: {event}")
        else:
            self.warning(f"🔒 SECURITY: {event}")
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Лог производительности"""
        self.log_json('performance', {
            'operation': operation,
            'duration_ms': round(duration * 1000, 2),
            **kwargs
        })
        
        if duration > 1.0:
            self.warning(f"⚠️  SLOW: {operation} took {duration:.2f}s")
        else:
            self.debug(f"⚡ {operation} took {duration*1000:.2f}ms")
    
    def get_stats(self) -> dict:
        """Получить статистику логов"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Сбросить статистику"""
        for key in self.stats:
            self.stats[key] = 0

# Глобальный логгер
_loggers = {}

def get_logger(name: str = "c2") -> EnhancedLogger:
    """Получить логгер"""
    if name not in _loggers:
        _loggers[name] = EnhancedLogger(name)
    return _loggers[name]

# Экспорт
__all__ = ['EnhancedLogger', 'get_logger', 'Colors']

if __name__ == "__main__":
    # Тест
    log = get_logger("test")
    
    log.section("TESTING ENHANCED LOGGER")
    
    log.debug("This is debug message")
    log.info("This is info message")
    log.warning("This is warning message")
    log.error("This is error message")
    log.critical("This is critical message")
    
    log.success("Operation completed successfully")
    log.fail("Operation failed")
    
    log.subsection("Progress Test")
    for i in range(1, 11):
        log.progress(i, 10, f"Processing item {i}/10")
    
    log.subsection("Table Test")
    log.table(
        ["Name", "Status", "Count"],
        [
            ["Server", "Running", "1"],
            ["Agents", "Active", "5"],
            ["Tasks", "Pending", "10"]
        ]
    )
    
    log.subsection("JSON Test")
    log.json_pretty({
        "server": "running",
        "agents": 5,
        "tasks": {"pending": 10, "completed": 50}
    }, "System Status")


# Декораторы для автоматического логирования
import functools
import time
import traceback

def log_function(logger_name: str = "c2"):
    """Декоратор для логирования вызовов функций"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            func_name = func.__name__
            
            # Логируем вызов
            logger.debug(f"→ Calling {func_name}(args={args[:2] if len(args) > 2 else args}, kwargs={list(kwargs.keys())})")
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Логируем успех
                logger.debug(f"← {func_name} completed in {duration:.3f}s")
                logger.log_performance(func_name, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Логируем ошибку
                logger.error(f"✗ {func_name} failed after {duration:.3f}s: {e}")
                logger.exception(f"Exception in {func_name}")
                raise
        
        return wrapper
    return decorator

def log_api_endpoint(logger_name: str = "c2"):
    """Декоратор для логирования API endpoints"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            logger = get_logger(logger_name)
            
            start_time = time.time()
            method = request.method
            endpoint = request.path
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Определяем статус
                if hasattr(result, 'status_code'):
                    status = result.status_code
                elif isinstance(result, tuple) and len(result) > 1:
                    status = result[1]
                else:
                    status = 200
                
                # Логируем API вызов
                logger.log_api_call(
                    method=method,
                    endpoint=endpoint,
                    status=status,
                    duration=duration,
                    ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')[:50]
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.log_api_call(
                    method=method,
                    endpoint=endpoint,
                    status=500,
                    duration=duration,
                    error=str(e)
                )
                raise
        
        return wrapper
    return decorator

def log_task_execution(logger_name: str = "c2"):
    """Декоратор для логирования выполнения задач"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(task_id, task_type, *args, **kwargs):
            logger = get_logger(logger_name)
            
            logger.log_task(task_id, task_type, "started")
            
            start_time = time.time()
            try:
                result = func(task_id, task_type, *args, **kwargs)
                duration = time.time() - start_time
                
                logger.log_task(
                    task_id, 
                    task_type, 
                    "completed",
                    duration=duration
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.log_task(
                    task_id,
                    task_type,
                    "failed",
                    duration=duration,
                    error=str(e)
                )
                raise
        
        return wrapper
    return decorator

# Context manager для логирования блоков кода
class LogContext:
    """Context manager для логирования блоков кода"""
    
    def __init__(self, logger_name: str, operation: str, **kwargs):
        self.logger = get_logger(logger_name)
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"▶ Starting: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            self.logger.debug(f"✓ Completed: {self.operation} in {duration:.3f}s")
            self.logger.log_performance(self.operation, duration, **self.kwargs)
        else:
            self.logger.error(f"✗ Failed: {self.operation} after {duration:.3f}s")
            self.logger.exception(f"Exception in {self.operation}")
        
        return False  # Don't suppress exceptions

# Экспорт декораторов
__all__.extend(['log_function', 'log_api_endpoint', 'log_task_execution', 'LogContext'])
