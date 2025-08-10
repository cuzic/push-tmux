#!/usr/bin/env python3
"""
Logging utilities for push-tmux
"""
import logging
import logging.config
import sys
from pathlib import Path


def setup_logging(config, is_daemon=False):
    """ログ設定をセットアップ"""
    daemon_config = config.get('daemon', {})
    logging_config = daemon_config.get('logging', {})
    
    log_level = logging_config.get('log_level', 'INFO').upper()
    log_file = logging_config.get('log_file', '')
    enable_reload_logs = logging_config.get('enable_reload_logs', True)
    
    handlers = {}
    
    # コンソールハンドラー（デーモンモードでない場合、またはreload_logs有効時）
    if not is_daemon or enable_reload_logs:
        handlers['console'] = {
            'class': 'logging.StreamHandler',
            'level': log_level,
            'formatter': 'standard',
            'stream': sys.stdout
        }
    
    # ファイルハンドラー（log_fileが指定されている場合）
    if log_file and is_daemon:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers['file'] = {
            'class': 'logging.FileHandler',
            'level': log_level,
            'formatter': 'detailed',
            'filename': str(log_path),
            'encoding': 'utf-8'
        }
    
    logging_dict = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': handlers,
        'root': {
            'level': log_level,
            'handlers': list(handlers.keys())
        }
    }
    
    logging.config.dictConfig(logging_dict)
    return logging.getLogger('push_tmux')


def log_daemon_event(event_type, message, **kwargs):
    """デーモンイベントをログ出力"""
    import click
    logger = logging.getLogger('push_tmux.daemon')
    
    extra_info = _format_extra_info(kwargs)
    event_config = _get_event_config(event_type.lower(), message, extra_info)
    
    _log_and_echo(logger, click, event_config)


def _format_extra_info(kwargs):
    """追加情報をフォーマット"""
    return ' '.join([f'{k}={v}' for k, v in kwargs.items()]) if kwargs else ''


def _get_event_config(event_type, message, extra_info):
    """イベントタイプに基づいた設定を取得"""
    event_configs = {
        'start': {'prefix': 'プロセス開始', 'level': 'info', 'use_stderr': False},
        'error': {'prefix': 'エラー', 'level': 'error', 'use_stderr': True},
        'warning': {'prefix': '警告', 'level': 'warning', 'use_stderr': False},
        'info': {'prefix': '', 'level': 'info', 'use_stderr': False, 'include_extra': True},
        'file_change': {'prefix': 'ファイル変更検知', 'level': 'info', 'use_stderr': False}
    }
    
    config = event_configs.get(event_type, {'prefix': '', 'level': 'info', 'use_stderr': False, 'include_extra': True})
    config['message'] = _format_message(message, config, extra_info)
    
    return config


def _format_message(message, config, extra_info):
    """メッセージをフォーマット"""
    if config.get('prefix'):
        full_message = f"{config['prefix']}: {message}"
    else:
        full_message = message
    
    if config.get('include_extra') and extra_info:
        full_message += f' ({extra_info})'
    
    return full_message


def _log_and_echo(logger, click, event_config):
    """ログ出力とコンソール表示を実行"""
    message = event_config['message']
    level = event_config['level']
    use_stderr = event_config['use_stderr']
    
    # ログレベルに応じて出力
    getattr(logger, level)(message)
    
    # コンソール出力
    if use_stderr:
        click.echo(message, err=True)
    else:
        click.echo(message)