#!/usr/bin/env python3
"""
Pushbulletのメッセージをtmuxに送信するCLIツール（非同期版）
"""
import asyncio
import click
import os
import time
import toml
import logging
import sys
from datetime import datetime
from dotenv import load_dotenv
from async_pushbullet import AsyncPushbullet, AsyncPushbulletListener
import questionary
import aiohttp

# .envファイルから環境変数を読み込む
load_dotenv()

# 設定ファイルのパスを定義
CONFIG_FILE = "config.toml"

def load_config():
    """
    設定ファイル (config.toml) を読み込む
    ファイルが存在しない場合はデフォルト設定を返す
    """
    # デフォルト設定
    default_config = {
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
    
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            user_config = toml.load(f)
        
        # デフォルト設定とユーザー設定をマージ
        def merge_dict(default, user):
            result = default.copy()
            for key, value in user.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result
        
        return merge_dict(default_config, user_config)
    
    return default_config

def save_config(config):
    """
    設定をTOML形式で設定ファイルに書き込む
    """
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        toml.dump(config, f)

def setup_logging(config, is_daemon=False):
    """
    ログ設定のセットアップ
    """
    daemon_config = config.get('daemon', {})
    logging_config = daemon_config.get('logging', {})
    
    # ログレベル設定
    log_level = logging_config.get('log_level', 'INFO').upper()
    level = getattr(logging, log_level, logging.INFO)
    
    # ログフォーマット
    if is_daemon:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [Daemon] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # ハンドラー設定
    handlers = []
    
    # ファイルログ
    log_file = logging_config.get('log_file', '')
    if log_file and log_file.strip():
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception as e:
            click.echo(f"警告: ログファイル '{log_file}' を開けません: {e}", err=True)
    
    # コンソールログ（ファイルログがない場合、またはdaemonモード）
    if not handlers or is_daemon:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 既存のハンドラーをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 新しいハンドラーを追加
    for handler in handlers:
        root_logger.addHandler(handler)
    
    return root_logger


def log_daemon_event(event_type, message, **kwargs):
    """
    デーモンイベントのログ記録
    """
    logger = logging.getLogger()
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    if event_type == 'start':
        logger.info(f"プロセス開始: {message}")
        click.echo(f"[{timestamp}] [START] {message}")
    elif event_type == 'restart':
        logger.warning(f"プロセス再起動: {message}")
        click.echo(f"[{timestamp}] [RESTART] {message}")
    elif event_type == 'error':
        logger.error(f"エラー: {message}")
        click.echo(f"[{timestamp}] [ERROR] {message}", err=True)
    elif event_type == 'file_change':
        logger.info(f"ファイル変更検知: {message}")
        click.echo(f"[{timestamp}] [FILE] {message}")
    else:
        logger.info(f"{event_type}: {message}")
        click.echo(f"[{timestamp}] [{event_type.upper()}] {message}")


def get_device_name():
    """
    環境変数またはディレクトリ名からデバイス名を取得する
    """
    return os.getenv('DEVICE_NAME', os.path.basename(os.getcwd()))

async def send_to_tmux(config, message, device_name=None):
    """
    tmuxにメッセージとEnterキーを送信する
    
    Args:
        config: 設定辞書
        message: 送信するメッセージ
        device_name: デバイス名（tmuxセッション名として使用）
    """
    tmux_config = config.get('tmux', {})
    session_setting = tmux_config.get('target_session')
    window_setting = tmux_config.get('target_window')
    pane_setting = tmux_config.get('target_pane')
    
    # ターゲットセッションを決定
    target_session = None
    
    # 優先順位: 1. config設定 2. device_name 3. 現在のセッション
    # configに明示的な設定がある場合はそれを優先
    if session_setting and session_setting != 'current':
        target_session = session_setting
    
    # config設定がない場合、device_nameを使用
    elif device_name:
        # デバイス名と同じ名前のtmuxセッションが存在するか確認
        try:
            result = await asyncio.create_subprocess_exec(
                'tmux', 'has-session', '-t', device_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            if result.returncode == 0:
                target_session = device_name
                click.echo(f"デバイス名に対応するtmuxセッション '{device_name}' を使用します。")
            else:
                click.echo(f"警告: tmuxセッション '{device_name}' が存在しません。フォールバックします。")
        except:
            pass
    
    # configもdevice_nameもない、またはdevice_nameでセッションが見つからなかった場合
    if target_session is None:
        # TMUX環境変数から現在のセッション情報を取得
        tmux_env = os.environ.get('TMUX')
        if tmux_env:
            # tmux display-messageで現在のセッション名を取得
            try:
                result = await asyncio.create_subprocess_exec(
                    'tmux', 'display-message', '-p', '#{session_name}',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                target_session = stdout.decode().strip()
            except:
                # フォールバック
                parts = tmux_env.split(',')
                if parts:
                    socket_path = parts[0]
                    session_name = os.path.basename(socket_path)
                    target_session = session_name if session_name else 'default'
        else:
            click.echo("エラー: スクリプトがtmuxセッション内で実行されていません。", err=True)
            click.echo("`config.toml`で`[tmux].target_session`を明示的に設定してください。", err=True)
            return
    
    # デフォルト値の設定
    # ウィンドウ: デフォルトは "first"（最初のウィンドウ）
    if window_setting is None:
        window_setting = 'first'  # デフォルトを明示的に設定
    
    # ウィンドウ設定の処理
    if window_setting == 'first':
        try:
            result = await asyncio.create_subprocess_exec(
                'tmux', 'list-windows', '-t', target_session, '-F', '#{window_index}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            windows = stdout.decode().strip().split('\n')
            target_window = windows[0] if windows else '0'
        except:
            target_window = '0'
    else:
        target_window = window_setting
    
    # ペイン: デフォルトは "first"（最初のペイン）
    if pane_setting is None:
        pane_setting = 'first'  # デフォルトを明示的に設定
    
    # ペイン設定の処理
    if pane_setting == 'first':
        try:
            result = await asyncio.create_subprocess_exec(
                'tmux', 'list-panes', '-t', f"{target_session}:{target_window}", '-F', '#{pane_index}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            panes = stdout.decode().strip().split('\n')
            target_pane = panes[0] if panes else '0'
        except:
            target_pane = '0'
    else:
        target_pane = pane_setting
    
    target = f"{target_session}:{target_window}.{target_pane}"
    
    try:
        # メッセージを送信
        click.echo(f"tmuxセッション '{target}' にメッセージを送信します...")
        process = await asyncio.create_subprocess_exec(
            'tmux', 'send-keys', '-t', target, message
        )
        await process.wait()
        
        # 1秒待機
        await asyncio.sleep(1)
        
        # Enterキーを送信
        click.echo("Enterキーを送信します...")
        process = await asyncio.create_subprocess_exec(
            'tmux', 'send-keys', '-t', target, 'C-m'
        )
        await process.wait()
        click.echo("tmuxへの送信が完了しました。")
        
    except FileNotFoundError:
        click.echo("エラー: 'tmux'コマンドが見つかりません。パスが通っているか確認してください。", err=True)
    except Exception as e:
        click.echo(f"tmuxコマンドの実行中にエラーが発生しました: {e}", err=True)


# --- CLIコマンド定義 ---

@click.group()
def cli():
    """
    Pushbulletのメッセージをtmuxに送信するCLIツール。
    """
    pass

@cli.command()
@click.option('--name', help='デバイス名（未指定時は環境変数DEVICE_NAME）')
def register(name):
    """
    新しいPushbulletデバイスとして登録します。
    """
    async def _register():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        device_name = name if name else get_device_name()
        
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = await pb.get_devices()
                existing_device = next((d for d in devices if d.get('nickname') == device_name), None)
                
                if existing_device:
                    click.echo(f"デバイス '{device_name}' は既に登録されています。")
                    click.echo(f"  ID: {existing_device['iden']}")
                    click.echo(f"  作成日時: {existing_device['created']}")
                    click.echo(f"  更新日時: {existing_device['modified']}")
                else:
                    device = await pb.create_device(device_name)
                    click.echo(f"デバイス '{device_name}' を登録しました。")
                    click.echo(f"  ID: {device['iden']}")
            except Exception as e:
                click.echo(f"デバイス登録中にエラーが発生しました: {e}", err=True)
    
    asyncio.run(_register())

@cli.command('list-devices')
def list_devices():
    """
    Pushbulletに登録されているデバイス一覧を表示します。
    """
    async def _list_devices():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = await pb.get_devices()
                if not devices:
                    click.echo("登録されているデバイスはありません。")
                    return
                
                click.echo("\n登録されているデバイス一覧:")
                click.echo("=" * 60)
                for device in devices:
                    click.echo(f"\n名前: {device.get('nickname', 'N/A')}")
                    click.echo(f"  ID: {device['iden']}")
                    click.echo(f"  アクティブ: {'はい' if device.get('active', False) else 'いいえ'}")
                    click.echo(f"  作成日時: {device.get('created', 'N/A')}")
                    click.echo(f"  更新日時: {device.get('modified', 'N/A')}")
                    if 'manufacturer' in device:
                        click.echo(f"  製造元: {device['manufacturer']}")
                    if 'model' in device:
                        click.echo(f"  モデル: {device['model']}")
                click.echo("\n" + "=" * 60)
                click.echo(f"合計: {len(devices)} デバイス")
            except Exception as e:
                click.echo(f"デバイス一覧の取得中にエラーが発生しました: {e}", err=True)
    
    asyncio.run(_list_devices())

@cli.command('delete-devices')
@click.option('--name', help='削除するデバイス名（単一削除モード）')
@click.option('--id', 'device_id', help='削除するデバイスID（単一削除モード）')
@click.option('--yes', is_flag=True, help='確認なしで削除（単一削除モード）')
@click.option('--include-inactive', is_flag=True, help='非アクティブなデバイスも表示（複数選択モード）')
def delete_devices(name, device_id, yes, include_inactive):
    """
    Pushbulletデバイスを削除します。
    
    引数なし: インタラクティブに複数デバイスを選択して削除
    --name/--id指定: 特定のデバイスを直接削除
    """
    async def _delete_devices():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        # 単一削除モード（--nameまたは--id指定時）
        if name or device_id:
            async with AsyncPushbullet(api_key) as pb:
                try:
                    devices = await pb.get_devices()
                    target_device = None
                    
                    for device in devices:
                        if device_id and device['iden'] == device_id:
                            target_device = device
                            break
                        elif name and device.get('nickname') == name:
                            target_device = device
                            break
                    
                    if not target_device:
                        if device_id:
                            click.echo(f"エラー: ID '{device_id}' のデバイスが見つかりません。", err=True)
                        else:
                            click.echo(f"エラー: 名前 '{name}' のデバイスが見つかりません。", err=True)
                        return
                    
                    # 削除確認
                    if not yes:
                        click.echo(f"\nデバイス情報:")
                        click.echo(f"  名前: {target_device.get('nickname', 'N/A')}")
                        click.echo(f"  ID: {target_device['iden']}")
                        click.echo(f"  作成日時: {target_device.get('created', 'N/A')}")
                        
                        if not click.confirm("\nこのデバイスを削除しますか？"):
                            click.echo("削除をキャンセルしました。")
                            return
                    
                    await pb.delete_device(target_device['iden'])
                    click.echo(f"デバイス '{target_device.get('nickname', 'N/A')}' (ID: {target_device['iden']}) を削除しました。")
                    
                except Exception as e:
                    click.echo(f"デバイス削除中にエラーが発生しました: {e}", err=True)
                return
        
        # 複数選択削除モード
        async with AsyncPushbullet(api_key) as pb:
            try:
                # デバイス一覧を取得（デフォルトはアクティブのみ）
                devices = await pb.get_devices(active_only=not include_inactive)
                if not devices:
                    if include_inactive:
                        click.echo("登録されているデバイスはありません。")
                    else:
                        click.echo("アクティブなデバイスはありません。")
                        click.echo("非アクティブなデバイスも表示するには --include-inactive オプションを使用してください。")
                    return
                
                # デバイスの選択肢を作成
                choices = []
                for device in devices:
                    device_name = device.get('nickname', 'N/A')
                    iden = device['iden']
                    active = "✓" if device.get('active', False) else " "
                    created = device.get('created', 'N/A')
                    
                    # 作成日時をフォーマット
                    if created != 'N/A':
                        from datetime import datetime
                        try:
                            dt = datetime.fromtimestamp(created)
                            created_str = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            created_str = str(created)
                    else:
                        created_str = 'N/A'
                    
                    # 製造元とモデル情報
                    manufacturer = device.get('manufacturer', '')
                    model = device.get('model', '')
                    device_info = f" ({manufacturer} {model})" if manufacturer or model else ""
                    
                    label = f"[{active}] {device_name:<20} (ID: {iden[:10]}...) 作成: {created_str}{device_info}"
                    choices.append(questionary.Choice(title=label, value=device))
                
                # チェックボックスで複数選択
                selected_devices = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: questionary.checkbox(
                        "削除するデバイスを選択してください (スペースで選択/解除, Enterで確定):",
                        choices=choices
                    ).ask()
                )
                
                if not selected_devices:
                    click.echo("削除をキャンセルしました。")
                    return
                
                # 選択されたデバイスの詳細を表示
                click.echo("\n以下のデバイスを削除します:")
                click.echo("=" * 60)
                for device in selected_devices:
                    click.echo(f"  • {device.get('nickname', 'N/A')} (ID: {device['iden']})")
                click.echo("=" * 60)
                
                # 最終確認
                confirm = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: questionary.confirm(
                        f"\n{len(selected_devices)}個のデバイスを削除してもよろしいですか？"
                    ).ask()
                )
                
                if not confirm:
                    click.echo("削除をキャンセルしました。")
                    return
                
                # デバイスを一括削除
                click.echo("\nデバイスを削除中...")
                success_count = 0
                error_count = 0
                
                for device in selected_devices:
                    try:
                        await pb.delete_device(device['iden'])
                        click.echo(f"  ✓ {device.get('nickname', 'N/A')} (ID: {device['iden']}) を削除しました")
                        success_count += 1
                    except aiohttp.ClientResponseError as e:
                        if e.status == 404:
                            # 既に削除されているデバイス
                            click.echo(f"  ⚠ {device.get('nickname', 'N/A')} (ID: {device['iden']}) は既に削除されています")
                        else:
                            click.echo(f"  ✗ {device.get('nickname', 'N/A')} (ID: {device['iden']}) の削除に失敗: {e}", err=True)
                            error_count += 1
                    except Exception as e:
                        click.echo(f"  ✗ {device.get('nickname', 'N/A')} (ID: {device['iden']}) の削除に失敗: {e}", err=True)
                        error_count += 1
                
                # 結果のサマリーを表示
                click.echo("\n" + "=" * 60)
                click.echo(f"削除完了: {success_count}個のデバイス")
                if error_count > 0:
                    click.echo(f"削除失敗: {error_count}個のデバイス", err=True)
                
            except Exception as e:
                click.echo(f"デバイス一覧の取得中にエラーが発生しました: {e}", err=True)
    
    asyncio.run(_delete_devices())

@cli.command('send-key')
@click.argument('message')
@click.option('--session', help='ターゲットセッション')
@click.option('--window', help='ターゲットウィンドウ')
@click.option('--pane', help='ターゲットペイン')
def send_key(message, session, window, pane):
    """
    tmuxにメッセージを送信します（テスト用）。
    """
    async def _send_key():
        config = load_config()
        
        if session or window or pane:
            if 'tmux' not in config:
                config['tmux'] = {}
            if session:
                config['tmux']['target_session'] = session
            if window:
                config['tmux']['target_window'] = window
            if pane:
                config['tmux']['target_pane'] = pane
        
        await send_to_tmux(config, message, device_name=None)
    
    asyncio.run(_send_key())

async def listen_main(device=None, all_devices=False, auto_route=False, debug=False):
    """
    listen コマンドのメインロジック（hupper 対応）
    """
    api_key = os.getenv('PUSHBULLET_TOKEN')
    if not api_key:
        click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
        return
    
    config = load_config()
    
    # auto-routeモードの場合、全デバイスのメッセージを受信
    if auto_route:
        click.echo("自動ルーティングモード: 全デバイスのメッセージを受信し、対応するtmuxセッションに送信します。")
        
        # デバイス一覧を取得して表示
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = await pb.get_devices(active_only=True)
                if devices:
                    click.echo("\nアクティブなデバイス:")
                    for d in devices:
                        nickname = d.get('nickname', 'N/A')
                        # tmuxセッションの存在確認
                        try:
                            result = await asyncio.create_subprocess_exec(
                                'tmux', 'has-session', '-t', nickname,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            await result.communicate()
                            session_exists = result.returncode == 0
                            status = "✓ tmuxセッションあり" if session_exists else "✗ tmuxセッションなし"
                        except:
                            status = "? tmux確認失敗"
                        
                        click.echo(f"  - {nickname} ({d['iden'][:8]}...) [{status}]")
                    click.echo("")
            except Exception as e:
                click.echo(f"デバイス一覧取得エラー: {e}")
    
    # ターゲットデバイスの特定
    target_device_iden = None
    device_name = None  # デバイス名を保持
    if device and not all_devices and not auto_route:
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = await pb.get_devices()
                for d in devices:
                    if d.get('nickname') == device or d.get('iden') == device:
                        target_device_iden = d['iden']
                        device_name = d.get('nickname', d['iden'])
                        click.echo(f"デバイス '{device_name}' (ID: {d['iden']}) として待ち受けます。")
                        break
                
                if not target_device_iden:
                    click.echo(f"エラー: デバイス '{device}' が見つかりません。", err=True)
                    return
            except Exception as e:
                click.echo(f"デバイス情報の取得中にエラーが発生しました: {e}", err=True)
                return
    elif all_devices and not auto_route:
        click.echo("警告: --all-devicesオプションは無効です。特定のデバイス宛のメッセージのみ処理します。")
    elif not auto_route:
        # デフォルト：現在のデバイス名で登録されているデバイスを使用
        device_name = get_device_name()
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = await pb.get_devices()
                for d in devices:
                    if d.get('nickname') == device_name:
                        target_device_iden = d['iden']
                        click.echo(f"デバイス '{device_name}' (ID: {d['iden']}) として待ち受けます。")
                        break
                
                if not target_device_iden:
                    click.echo(f"エラー: デバイス '{device_name}' が登録されていません。", err=True)
                    click.echo("先に 'push-tmux register' でデバイスを登録してください。", err=True)
                    return
            except Exception as e:
                click.echo(f"デバイス情報を取得できませんでした: {e}", err=True)
                return
    
    # auto-routeモード用のハンドラー
    if auto_route:
        # デバイス情報をキャッシュ
        device_cache = {}
        async with AsyncPushbullet(api_key) as pb:
            devices = await pb.get_devices()
            for d in devices:
                device_cache[d['iden']] = d.get('nickname', d['iden'])
        
        async def on_push_auto_route(push):
            """自動ルーティングモードでのプッシュ処理"""
            # noteタイプのみ処理
            if push.get('type') != 'note':
                return
            
            # デバイス情報を取得
            target_device_iden = push.get('target_device_iden')
            
            # 全デバイス宛のメッセージは無視
            if not target_device_iden:
                return
            
            # デバイス名を取得
            target_device_name = device_cache.get(target_device_iden, None)
            if not target_device_name:
                click.echo(f"警告: 未知のデバイスID: {target_device_iden}")
                return
            
            # tmuxセッションの存在確認
            try:
                result = await asyncio.create_subprocess_exec(
                    'tmux', 'has-session', '-t', target_device_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await result.communicate()
                session_exists = result.returncode == 0
            except:
                session_exists = False
            
            if not session_exists:
                # セッションが存在しない場合はスキップ（ログのみ）
                click.echo(f"[スキップ] {target_device_name}: tmuxセッションが存在しません")
                return
            
            # メッセージ情報を表示
            title = push.get('title', 'メッセージ')
            body = push.get('body', '')
            sender_name = push.get('sender_name', '不明')
            
            click.echo("-" * 40)
            click.echo(f"メッセージを {target_device_name} セッションに送信:")
            click.echo(f"  送信者: {sender_name}")
            click.echo(f"  タイトル: {title}")
            click.echo(f"  本文: {body[:50]}..." if len(body) > 50 else f"  本文: {body}")
            click.echo("-" * 40)
            
            # tmuxに送信（デバイス名を指定）
            await send_to_tmux(config, body, device_name=target_device_name)
        
        on_push = on_push_auto_route
    else:
        # 既存のon_push関数（特定デバイスモード）
        async def on_push(push):
            """プッシュを受信したときの処理"""
            # noteタイプのみ処理
            if push.get('type') != 'note':
                return
            
            # デバイスフィルタリング
            target_device = push.get('target_device_iden')
            
            # 全デバイス宛のメッセージは無視
            if not target_device:
                return
            
            # 特定のデバイス宛のメッセージのみ処理
            # target_device_idenが設定されている場合は、そのデバイス宛のメッセージのみ処理
            if target_device != target_device_iden:
                # 他のデバイス宛のメッセージは無視
                return
            
            title = push.get('title', 'メッセージ')
            body = push.get('body', '')
            sender_name = push.get('sender_name', '不明')
            sender_email = push.get('sender_email', '')
            
            click.echo("-" * 40)
            click.echo(f"新しいメッセージを受信しました:")
            if sender_email:
                click.echo(f"  送信者: {sender_name} ({sender_email})")
            else:
                click.echo(f"  送信者: {sender_name}")
            click.echo(f"  宛先デバイス: {target_device}")
            click.echo(f"  タイトル: {title}")
            click.echo(f"  本文: {body}")
            click.echo("-" * 40)
            
            # tmuxに送信 (デバイス名を渡す)
            # 外側のスコープのdevice_nameを参照
            await send_to_tmux(config, body, device_name=device_name)
    
    # リスナーを開始（デバッグモード対応）
    listener = AsyncPushbulletListener(api_key, on_push, debug=debug)
    
    if debug:
        click.echo("デバッグモードで実行中...")
    click.echo(f"Pushbulletのストリームを開始します。")
    click.echo("Ctrl+Cで終了します。")
    
    try:
        await listener.run()
    except KeyboardInterrupt:
        click.echo("\nストリームを停止します...")
    except Exception as e:
        click.echo(f"Pushbulletのストリームでエラーが発生しました: {e}", err=True)
    finally:
        click.echo("Pushbulletのストリームを終了しました。")


@cli.command()
@click.option('--device', help='メッセージを受信するデバイス名またはID')
@click.option('--all-devices', is_flag=True, help='全デバイス宛のメッセージを受信')
@click.option('--auto-route', is_flag=True, help='デバイス名と同じtmuxセッションに自動ルーティング')
@click.option('--debug', is_flag=True, help='デバッグモードで実行（詳細ログを表示）')
def listen(device, all_devices, auto_route, debug):
    """
    Pushbulletからのメッセージを待ち受け、tmuxに送信します。
    """
    asyncio.run(listen_main(device, all_devices, auto_route, debug))

@cli.command()
@click.option('--device', help='メッセージを受信するデバイス名またはID')
@click.option('--all-devices', is_flag=True, help='全デバイス宛のメッセージを受信')
@click.option('--auto-route', is_flag=True, help='デバイス名と同じtmuxセッションに自動ルーティング')
@click.option('--debug', is_flag=True, help='デバッグモードで実行（詳細ログを表示）')
@click.option('--reload-interval', default=1.0, type=float, help='ファイル監視間隔（秒）')
@click.option('--watch-files', multiple=True, help='追加で監視するファイル')
def daemon(device, all_devices, auto_route, debug, reload_interval, watch_files):
    """
    デーモンモードで listen を実行（自動再起動機能付き）
    
    プロセス異常終了時に自動的に再起動します。
    設定ファイルやコードの変更時にも自動再起動されます。
    """
    import hupper
    import sys
    import os
    
    # 設定読み込み
    config = load_config()
    daemon_config = config.get('daemon', {})
    
    # ログ設定
    setup_logging(config, is_daemon=True)
    
    # hupper の設定
    # hupper から再起動される際のパラメータ渡し
    if hupper.is_active():
        # 子プロセス（実際のワーカー）での実行
        log_daemon_event('start', 'ワーカープロセスを開始')
        try:
            asyncio.run(listen_main(device, all_devices, auto_route, debug))
        except KeyboardInterrupt:
            log_daemon_event('info', 'キーボード割り込みで停止')
        except Exception as e:
            log_daemon_event('error', f'ワーカープロセスでエラー: {e}')
            raise
    else:
        # 親プロセス（監視プロセス）での実行
        log_daemon_event('start', 'プロセス監視を開始')
        
        # reload_interval の設定（引数 > 設定ファイル > デフォルト）
        final_reload_interval = reload_interval or daemon_config.get('reload_interval', 1.0)
        
        # 監視ファイルの設定
        default_watch_files = daemon_config.get('watch_files', ['config.toml', '.env'])
        final_watch_files = list(default_watch_files) + list(watch_files)
        
        log_daemon_event('info', f'監視間隔: {final_reload_interval}秒')
        log_daemon_event('info', f'監視ファイル: {", ".join(final_watch_files)}')
        log_daemon_event('info', f'オプション: device={device}, auto_route={auto_route}, debug={debug}')
        click.echo("[Daemon] Ctrl+C で終了します。")
        click.echo("-" * 50)
        
        # hupper のセットアップ
        def worker_main():
            """ワーカープロセスのメイン関数"""
            try:
                asyncio.run(listen_main(device, all_devices, auto_route, debug))
            except KeyboardInterrupt:
                log_daemon_event('info', 'キーボード割り込みで停止')
                sys.exit(0)
            except Exception as e:
                log_daemon_event('error', f'ワーカープロセスでエラー: {e}')
                sys.exit(1)
        
        # ファイル変更時のコールバック
        def on_reload():
            """ファイル変更時のコールバック"""
            log_daemon_event('file_change', 'ファイル変更を検知、プロセスを再起動')
        
        try:
            # hupper reloader を開始
            reloader = hupper.start_reloader(
                'push_tmux.daemon_worker_main',
                reload_interval=final_reload_interval,
                ignore_files=daemon_config.get('ignore_patterns', ['*.pyc', '__pycache__/*', '.git/*'])
            )
            
            # 監視ファイルを追加
            if reloader:
                reloader.watch_files(final_watch_files)
                log_daemon_event('info', f'監視ファイルを追加: {final_watch_files}')
            
            # グローバル変数でパラメータを保存（hupper での引き渡し用）
            import push_tmux
            push_tmux._daemon_params = {
                'device': device,
                'all_devices': all_devices,
                'auto_route': auto_route,
                'debug': debug
            }
            
            # メインワーカーを実行
            worker_main()
            
        except KeyboardInterrupt:
            log_daemon_event('info', 'デーモンを停止します')
        except Exception as e:
            log_daemon_event('error', f'デーモンでエラーが発生: {e}')
            raise


def daemon_worker_main():
    """daemon コマンド用のワーカーエントリーポイント（hupper 対応）"""
    import push_tmux
    
    # グローバル変数からパラメータを取得
    params = getattr(push_tmux, '_daemon_params', {})
    device = params.get('device')
    all_devices = params.get('all_devices', False)
    auto_route = params.get('auto_route', False)
    debug = params.get('debug', False)
    
    # 設定読み込みとログ設定
    config = load_config()
    setup_logging(config, is_daemon=True)
    
    log_daemon_event('info', f'ワーカー開始 - device={device}, auto_route={auto_route}, debug={debug}')
    
    try:
        # メインロジックを実行
        asyncio.run(listen_main(device, all_devices, auto_route, debug))
    except KeyboardInterrupt:
        log_daemon_event('info', 'ワーカーを停止')
    except Exception as e:
        log_daemon_event('error', f'ワーカーでエラー: {e}')
        raise


if __name__ == "__main__":
    cli()