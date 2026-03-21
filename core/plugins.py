"""Plugin system for C2 Server"""
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Callable, Any
import json

class Plugin:
    """Base plugin class"""
    name = "base"
    version = "1.0.0"
    description = ""
    
    def __init__(self, server_app):
        self.app = server_app
        self.config = {}
    
    def on_load(self):
        """Called when plugin is loaded"""
        pass
    
    def on_unload(self):
        """Called when plugin is unloaded"""
        pass
    
    def on_agent_register(self, agent_data: dict):
        """Called when agent registers"""
        pass
    
    def on_task_create(self, task_data: dict):
        """Called when task is created"""
        pass
    
    def on_task_complete(self, task_id: str, result: str):
        """Called when task completes"""
        pass

class PluginManager:
    def __init__(self, plugins_dir: Path, server_app):
        self.plugins_dir = plugins_dir
        self.app = server_app
        self.plugins: Dict[str, Plugin] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        
    def discover(self) -> List[str]:
        """Discover available plugins"""
        if not self.plugins_dir.exists():
            return []
        
        plugins = []
        for f in self.plugins_dir.glob("*.py"):
            if f.stem != "__init__":
                plugins.append(f.stem)
        return plugins
    
    def load(self, plugin_name: str) -> bool:
        """Load a plugin"""
        try:
            module = importlib.import_module(f"plugins.{plugin_name}")
            
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                    plugin = obj(self.app)
                    plugin.on_load()
                    self.plugins[plugin_name] = plugin
                    self._register_hooks(plugin)
                    return True
            return False
        except Exception as e:
            print(f"Failed to load plugin {plugin_name}: {e}")
            return False
    
    def unload(self, plugin_name: str):
        """Unload a plugin"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].on_unload()
            self._unregister_hooks(plugin_name)
            del self.plugins[plugin_name]
    
    def _register_hooks(self, plugin: Plugin):
        """Register plugin hooks"""
        for method_name in dir(plugin):
            if method_name.startswith("on_"):
                hook_name = method_name
                if hook_name not in self.hooks:
                    self.hooks[hook_name] = []
                self.hooks[hook_name].append(getattr(plugin, method_name))
    
    def _unregister_hooks(self, plugin_name: str):
        """Unregister plugin hooks"""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return
        
        for hook_name, callbacks in self.hooks.items():
            self.hooks[hook_name] = [cb for cb in callbacks if cb.__self__ != plugin]
    
    def trigger(self, hook_name: str, *args, **kwargs):
        """Trigger a hook"""
        for callback in self.hooks.get(hook_name, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"Hook {hook_name} error: {e}")
    
    def get_info(self) -> List[dict]:
        """Get info about loaded plugins"""
        return [{
            "name": p.name,
            "version": p.version,
            "description": p.description
        } for p in self.plugins.values()]
