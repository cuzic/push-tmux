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
    
    # 追加情報があれば含める
    extra_info = ' '.join([f'{k}={v}' for k, v in kwargs.items()]) if kwargs else ''
    
    # イベントタイプに基づいたメッセージの作成
    if event_type.lower() == 'start':
        full_message = f'プロセス開始: {message}'
        logger.info(full_message)
        click.echo(full_message)
    elif event_type.lower() == 'error':
        full_message = f'エラー: {message}'
        logger.error(full_message)
        click.echo(full_message, err=True)
    elif event_type.lower() == 'warning':
        full_message = f'警告: {message}'
        logger.warning(full_message)
        click.echo(full_message)
    elif event_type.lower() == 'info':
        full_message = f'{message}' + (f' ({extra_info})' if extra_info else '')
        logger.info(full_message)
        click.echo(full_message)
    elif event_type.lower() == 'file_change':
        full_message = f'ファイル変更検知: {message}'
        logger.info(full_message)
        click.echo(full_message)
    else:
        full_message = f'{message}' + (f' ({extra_info})' if extra_info else '')
        logger.info(full_message)
        click.echo(full_message)