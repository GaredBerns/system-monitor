"""Async operations for C2 Server"""
import asyncio
from typing import List, Callable, Any
from concurrent.futures import ThreadPoolExecutor
import aiohttp

executor = ThreadPoolExecutor(max_workers=10)

async def run_in_executor(func: Callable, *args) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, func, *args)

async def gather_with_limit(tasks: List, limit: int = 10):
    semaphore = asyncio.Semaphore(limit)
    
    async def bounded_task(task):
        async with semaphore:
            return await task
    
    return await asyncio.gather(*[bounded_task(t) for t in tasks])

async def fetch_url(session: aiohttp.ClientSession, url: str, **kwargs) -> dict:
    async with session.get(url, **kwargs) as response:
        return {'url': url, 'status': response.status, 'data': await response.text()}

async def post_url(session: aiohttp.ClientSession, url: str, data: dict, **kwargs) -> dict:
    async with session.post(url, json=data, **kwargs) as response:
        return {'url': url, 'status': response.status, 'data': await response.text()}

async def batch_http_requests(urls: List[str], method='GET', **kwargs) -> List[dict]:
    async with aiohttp.ClientSession() as session:
        if method == 'GET':
            tasks = [fetch_url(session, url, **kwargs) for url in urls]
        else:
            tasks = [post_url(session, url, kwargs.get('data', {}), **kwargs) for url in urls]
        return await gather_with_limit(tasks)

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
