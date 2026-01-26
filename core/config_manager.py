import json
import os
from PyQt6.QtCore import QSettings

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT_DIR, "api_config.json")

API_PRESETS = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-5.2",
        "description": "OpenAI 官方 API",
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-reasoner",
        "description": "DeepSeek API (R1 深度思考模型)",
    },
    "Kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model_name": "moonshot-v1-8k",
        "description": "月之暗面 Kimi API",
    },
    "Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_name": "gemini-3-pro-preview",
        "description": "Google Gemini API (OpenAI 兼容格式)",
    },
    "Custom": {
        "base_url": "",
        "model_name": "",
        "description": "自定义中转站 / 其他 API",
    },
}


def load_api_config():
    """从文件加载 API 配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_api_config(config):
    """保存 API 配置到文件"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_api_presets():
    return API_PRESETS


def get_selected_provider_config(raw_config: dict):
    """兼容旧格式与多提供商配置"""
    if raw_config.get("providers") and raw_config.get("provider"):
        provider = raw_config.get("provider")
        return raw_config.get("providers", {}).get(provider, {})
    return raw_config


def get_theme(default="light"):
    settings = QSettings("AutoFormatter", "AutoFormatter")
    theme = settings.value("theme", default) or default
    return str(theme).lower()


def set_theme(theme: str):
    settings = QSettings("AutoFormatter", "AutoFormatter")
    settings.setValue("theme", theme)
