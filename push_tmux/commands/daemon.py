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
@click.option('--no-auto-route', is_flag=True, help='自動ルーティングを無効化（現在のデバイスのみ）')
@click.option('--debug', is_flag=True, help='デバッグ情報を表示')
@click.option('--reload-interval', type=float, default=1.0, help='ファイル変更監視間隔（秒）')
@click.option('--watch-files', multiple=True, help='監視するファイル（複数指定可能）')
def daemon(device, all_devices, auto_route, no_auto_route, debug, reload_interval, watch_files):
    """
    デーモンモードでPushbulletリスナーを起動します。
    ファイル変更の監視とホットリロード機能付き。
    
    デフォルトでは自動ルーティングモードで動作し、すべてのデバイスのメッセージを
    対応するtmuxセッションに送信します。
    """
    daemon_args = _process_daemon_args(device, all_devices, auto_route, no_auto_route)
    config = load_config()
    setup_logging(config, is_daemon=True)
    
    watch_config = _setup_watch_config(config, reload_interval, watch_files)
    
    mode_desc = "自動ルーティング" if daemon_args['auto_route'] else (daemon_args['device'] or 'default')
    log_daemon_event('info', 'デーモンモードを開始',
                    mode=mode_desc, auto_route=daemon_args['auto_route'], 
                    watch_files=watch_config['files'], reload_interval=watch_config['interval'])
    
    if not _check_watchdog_available():
        run_simple_daemon(daemon_args['device'], daemon_args['all_devices'], 
                         daemon_args['auto_route'], daemon_args['debug'])
        return
    
    _run_watchdog_daemon(daemon_args, watch_config)


def _process_daemon_args(device, all_devices, auto_route, no_auto_route):
    """デーモンの引数を処理して正規化する"""
    # 引数がない場合は自動ルーティングをデフォルトに
    if not device and not all_devices and not auto_route and not no_auto_route:
        auto_route = True
        
    # no_auto_route が指定された場合は auto_route を無効化
    if no_auto_route:
        auto_route = False
        
    return {
        'device': device,
        'all_devices': all_devices,
        'auto_route': auto_route,
        'debug': False  # daemon関数では使われていない
    }


def _setup_watch_config(config, reload_interval, watch_files):
    """ファイル監視の設定を準備する"""
    daemon_config = config.get('daemon', {})
    default_watch_files = daemon_config.get('watch_files', ['config.toml', '.env'])
    actual_watch_files = list(watch_files) if watch_files else default_watch_files
    actual_reload_interval = reload_interval if reload_interval != 1.0 else daemon_config.get('reload_interval', 1.0)
    
    return {
        'files': actual_watch_files,
        'interval': actual_reload_interval
    }


def _check_watchdog_available():
    """watchdogライブラリが利用可能かチェック"""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        return True
    except ImportError:
        log_daemon_event('warning', 'watchdogが利用できません。ファイル監視機能なしで実行します。')
        return False


def _run_watchdog_daemon(daemon_args, watch_config):
    """watchdogを使用したデーモンを実行"""
    from watchdog.observers import Observer
    
    handler = _create_reload_handler(daemon_args, watch_config)
    observer = Observer()
    
    _setup_file_monitoring(observer, handler, watch_config['files'])
    
    # 初回起動
    handler.start_worker()
    observer.start()
    
    _setup_signal_handlers(handler, observer)
    
    try:
        _run_daemon_loop(handler, watch_config['interval'])
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup_daemon(handler, observer)


def _create_reload_handler(daemon_args, watch_config):
    """リロードハンドラーを作成"""
    from watchdog.events import FileSystemEventHandler
    
    class ReloadHandler(FileSystemEventHandler):
        """ファイル変更を検知して再起動するハンドラー"""
        def __init__(self):
            self.process = None
            self.restart_needed = False
            
        def on_modified(self, event):
            if event.is_directory:
                return
            # 監視対象ファイルが変更された場合
            for watch_file in watch_config['files']:
                if event.src_path.endswith(watch_file):
                    log_daemon_event('info', f'ファイル変更を検出: {event.src_path}')
                    self.restart_needed = True
                    break
        
        def start_worker(self):
            """ワーカープロセスを開始"""
            if self.process:
                self.stop_worker()
            
            log_daemon_event('info', 'ワーカープロセスを開始')
            cmd = [sys.executable, '-m', 'push_tmux.commands.daemon_worker']
            env = _create_worker_env(daemon_args)
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
    
    return ReloadHandler()


def _create_worker_env(daemon_args):
    """ワーカープロセス用の環境変数を作成"""
    env = os.environ.copy()
    env['PUSH_TMUX_DEVICE'] = daemon_args['device'] or ''
    env['PUSH_TMUX_ALL_DEVICES'] = '1' if daemon_args['all_devices'] else '0'
    env['PUSH_TMUX_AUTO_ROUTE'] = '1' if daemon_args['auto_route'] else '0'
    env['PUSH_TMUX_DEBUG'] = '1' if daemon_args['debug'] else '0'
    return env


def _setup_file_monitoring(observer, handler, watch_files):
    """ファイル監視を設定"""
    watched_paths = set()
    for watch_file in watch_files:
        path = Path(watch_file)
        if path.exists():
            watched_paths.add(str(path.parent.absolute()))
    
    for path in watched_paths:
        observer.schedule(handler, path, recursive=False)
        log_daemon_event('info', f'監視開始: {path}')


def _setup_signal_handlers(handler, observer):
    """シグナルハンドラーを設定"""
    def signal_handler(signum, frame):
        log_daemon_event('info', 'シャットダウン要求を受信')
        handler.stop_worker()
        observer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def _run_daemon_loop(handler, reload_interval):
    """デーモンのメインループを実行"""
    while True:
        time.sleep(reload_interval)
        handler.check_restart()
        
        # プロセスが終了していないかチェック
        if handler.process and handler.process.poll() is not None:
            log_daemon_event('warning', 'ワーカープロセスが予期せず終了しました。再起動します。')
            handler.start_worker()


def _cleanup_daemon(handler, observer):
    """デーモン終了時のクリーンアップ"""
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