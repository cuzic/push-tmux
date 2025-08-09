#!/usr/bin/env python3
"""
Daemon command for push-tmux
"""
import asyncio
import click
import os
import sys
from ..config import load_config
from ..logging import setup_logging, log_daemon_event
from .listen import listen_main


@click.command()
@click.option('--device', '-d', help='特定のデバイス名またはIDを指定')
@click.option('--all-devices', is_flag=True, help='全デバイスからのメッセージを受信')
@click.option('--auto-route', is_flag=True, help='tmuxセッション名に基づいてメッセージを自動ルーティング')
@click.option('--debug', is_flag=True, help='デバッグ情報を表示')
@click.option('--reload-interval', type=float, default=1.0, help='ファイル変更監視間隔（秒）')
@click.option('--watch-files', multiple=True, help='監視するファイル（複数指定可能）')
def daemon(device, all_devices, auto_route, debug, reload_interval, watch_files):
    """
    デーモンモードでPushbulletリスナーを起動します。
    ファイル変更の監視とホットリロード機能付き。
    """
    config = load_config()
    setup_logging(config, is_daemon=True)
    
    # デフォルトの監視ファイル設定
    daemon_config = config.get('daemon', {})
    default_watch_files = daemon_config.get('watch_files', ['config.toml', '.env'])
    actual_watch_files = list(watch_files) if watch_files else default_watch_files
    actual_reload_interval = reload_interval if reload_interval != 1.0 else daemon_config.get('reload_interval', 1.0)
    
    log_daemon_event('info', 'デーモンモードを開始',
                    device=device or 'default', auto_route=auto_route, 
                    watch_files=actual_watch_files, reload_interval=actual_reload_interval)
    
    if os.getenv('PUSH_TMUX_WORKER'):
        # ワーカープロセス
        asyncio.run(daemon_worker_main())
    else:
        # メインプロセス（hupper使用）
        try:
            import hupper
        except ImportError:
            click.echo("エラー: hupper がインストールされていません。", err=True)
            click.echo("pip install hupper でインストールしてください。", err=True)
            return
        
        # 環境変数を設定
        os.environ['PUSH_TMUX_WORKER'] = '1'
        os.environ['PUSH_TMUX_DEVICE'] = device or ''
        os.environ['PUSH_TMUX_ALL_DEVICES'] = '1' if all_devices else '0'
        os.environ['PUSH_TMUX_AUTO_ROUTE'] = '1' if auto_route else '0'
        os.environ['PUSH_TMUX_DEBUG'] = '1' if debug else '0'
        
        def worker_main():
            """ワーカーのメイン処理"""
            python_path = sys.executable
            module_name = __name__.split('.')[0]  # 'push_tmux'
            return [python_path, '-c', f'from {module_name}.commands.daemon import daemon_worker_main; import asyncio; asyncio.run(daemon_worker_main())']
        
        def on_reload():
            """リロード時の処理"""
            log_daemon_event('info', '設定ファイルの変更を検出しました。リロード中...')
        
        # hupperでファイル監視とプロセス管理
        reloader = hupper.start_reloader(
            worker_main,
            reload_interval=actual_reload_interval,
            ignore_files=['*.pyc', '__pycache__/*', '.git/*', '*.log'] + daemon_config.get('ignore_patterns', [])
        )
        
        # 監視ファイルを追加
        for watch_file in actual_watch_files:
            if os.path.exists(watch_file):
                reloader.watch_files([watch_file])
        
        # リロードコールバック設定
        reloader.on_reload = on_reload
        
        log_daemon_event('info', 'ファイル監視を開始', files=actual_watch_files)


def daemon_worker_main():
    """デーモンワーカーのメイン処理"""
    try:
        log_daemon_event('info', 'ワーカーを開始')
        
        # 環境変数から設定を復元
        device = os.getenv('PUSH_TMUX_DEVICE') or None
        if device == '':
            device = None
        all_devices = os.getenv('PUSH_TMUX_ALL_DEVICES') == '1'
        auto_route = os.getenv('PUSH_TMUX_AUTO_ROUTE') == '1'
        debug = os.getenv('PUSH_TMUX_DEBUG') == '1'
        
        # listen_mainを実行
        return listen_main(device, all_devices, auto_route, debug)
        
    except KeyboardInterrupt:
        log_daemon_event('info', 'ワーカーを停止')
    except Exception as e:
        log_daemon_event('error', f'ワーカーでエラー: {e}')
        raise