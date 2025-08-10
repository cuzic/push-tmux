#!/usr/bin/env python3
"""
Daemon command for push-tmux
"""
import asyncio
import click
import os
import sys
import signal
import time
import subprocess
from pathlib import Path
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
    
    # watchdogを使ったファイル監視と再起動
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        # watchdogが利用できない場合は、シンプルなループで実行
        log_daemon_event('warning', 'watchdogが利用できません。ファイル監視機能なしで実行します。')
        run_simple_daemon(device, all_devices, auto_route, debug)
        return
    
    class ReloadHandler(FileSystemEventHandler):
        """ファイル変更を検知して再起動するハンドラー"""
        def __init__(self):
            self.process = None
            self.restart_needed = False
            
        def on_modified(self, event):
            if event.is_directory:
                return
            # 監視対象ファイルが変更された場合
            for watch_file in actual_watch_files:
                if event.src_path.endswith(watch_file):
                    log_daemon_event('info', f'ファイル変更を検出: {event.src_path}')
                    self.restart_needed = True
                    break
        
        def start_worker(self):
            """ワーカープロセスを開始"""
            if self.process:
                self.stop_worker()
            
            log_daemon_event('info', 'ワーカープロセスを開始')
            # 子プロセスで listen を実行
            cmd = [sys.executable, '-m', 'push_tmux.commands.daemon_worker']
            env = os.environ.copy()
            env['PUSH_TMUX_DEVICE'] = device or ''
            env['PUSH_TMUX_ALL_DEVICES'] = '1' if all_devices else '0'
            env['PUSH_TMUX_AUTO_ROUTE'] = '1' if auto_route else '0'
            env['PUSH_TMUX_DEBUG'] = '1' if debug else '0'
            
            self.process = subprocess.Popen(cmd, env=env)
            
        def stop_worker(self):
            """ワーカープロセスを停止"""
            if self.process:
                log_daemon_event('info', 'ワーカープロセスを停止')
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                self.process = None
        
        def check_restart(self):
            """再起動が必要な場合は実行"""
            if self.restart_needed:
                self.restart_needed = False
                log_daemon_event('info', '設定変更により再起動します')
                self.start_worker()
    
    # ファイル監視を設定
    handler = ReloadHandler()
    observer = Observer()
    
    # 監視するパスを設定
    watched_paths = set()
    for watch_file in actual_watch_files:
        path = Path(watch_file)
        if path.exists():
            # ファイルの親ディレクトリを監視
            watched_paths.add(str(path.parent.absolute()))
    
    for path in watched_paths:
        observer.schedule(handler, path, recursive=False)
        log_daemon_event('info', f'監視開始: {path}')
    
    # 初回起動
    handler.start_worker()
    
    # 監視開始
    observer.start()
    
    # Ctrl+C でのシャットダウン処理
    def signal_handler(signum, frame):
        log_daemon_event('info', 'シャットダウン要求を受信')
        handler.stop_worker()
        observer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while True:
            time.sleep(actual_reload_interval)
            handler.check_restart()
            
            # プロセスが終了していないかチェック
            if handler.process and handler.process.poll() is not None:
                log_daemon_event('warning', 'ワーカープロセスが予期せず終了しました。再起動します。')
                handler.start_worker()
                
    except KeyboardInterrupt:
        pass
    finally:
        handler.stop_worker()
        observer.stop()
        observer.join()
        log_daemon_event('info', 'デーモンを終了')


def run_simple_daemon(device, all_devices, auto_route, debug):
    """watchdogなしでシンプルなデーモンを実行"""
    while True:
        try:
            log_daemon_event('info', 'リスナーを開始')
            asyncio.run(listen_main(device, all_devices, auto_route, debug))
        except KeyboardInterrupt:
            log_daemon_event('info', 'デーモンを停止')
            break
        except Exception as e:
            log_daemon_event('error', f'エラーが発生しました: {e}')
            log_daemon_event('info', '5秒後に再起動します...')
            time.sleep(5)