#!/usr/bin/env python3
"""
Configuration management utilities for push-tmux
"""
import os
import toml
from pathlib import Path
from collections import ChainMap
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# 設定ファイルのパスを定義
CONFIG_FILE = Path("config.toml")


def _get_default_config():
    """デフォルト設定を返す"""
    return {
        'tmux': {
            'target_session': 'current',
            'target_window': 'first',  
            'target_pane': 'first'
        },
        'daemon': {
            'reload_interval': 1.0,
            'watch_files': ['config.toml', '.env'],
            'ignore_patterns': ['*.pyc', '__pycache__/*', '.git/*', '*.log'],
            'logging': {
                'enable_reload_logs': True,
                'log_file': '',
                'log_level': 'INFO'
            },
            'monitoring': {
                'cpu_threshold': 80.0,
                'memory_threshold': 500,
                'websocket_check': True,
                'heartbeat_interval': 30
            }
        }
    }


def _load_user_config(config_path):
    """ユーザー設定ファイルを読み込む"""
    try:
        return toml.load(config_path)
    except (FileNotFoundError, toml.TomlDecodeError):
        return {}


def _merge_configs(default_config, user_config):
    """デフォルト設定とユーザー設定をマージ"""
    merged = {}
    for key in default_config:
        if key in user_config:
            if isinstance(default_config[key], dict) and isinstance(user_config[key], dict):
                merged[key] = dict(ChainMap(user_config[key], default_config[key]))
            else:
                merged[key] = user_config[key]
        else:
            merged[key] = default_config[key]
    
    # ユーザー設定にのみ存在するキーも追加
    for key in user_config:
        if key not in merged:
            merged[key] = user_config[key]
    
    return merged


def load_config():
    """設定ファイル (config.toml) を読み込む"""
    default_config = _get_default_config()
    user_config = _load_user_config(CONFIG_FILE)
    return _merge_configs(default_config, user_config)


def save_config(config):
    """設定をconfig.tomlに保存"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        toml.dump(config, f)


def get_device_name():
    """デバイス名を取得（環境変数またはディレクトリ名）"""
    return os.getenv('DEVICE_NAME') or os.path.basename(os.getcwd())