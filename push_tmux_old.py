#!/usr/bin/env python3
"""
Pushbulletのメッセージをtmuxに送信するCLIツール（非同期版）
"""
import asyncio
import click
import os
import toml
import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path
from collections import ChainMap
from dotenv import load_dotenv
from asyncpushbullet import AsyncPushbullet, LiveStreamListener
import questionary
import aiohttp

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
        with config_path.open('r', encoding='utf-8') as f:
            return toml.load(f)
    except Exception:
        return {}


def _merge_configs(default_config, user_config):
    """デフォルト設定とユーザー設定をマージ"""
    merged_config = {}
    
    # デフォルト設定をベースにマージ
    for key in default_config:
        if (key in user_config and 
            isinstance(default_config[key], dict) and 
            isinstance(user_config[key], dict)):
            merged_config[key] = dict(ChainMap(user_config[key], default_config[key]))
        else:
            merged_config[key] = user_config.get(key, default_config[key])
    
    # ユーザー設定にのみ存在するキーを追加
    for key in user_config:
        if key not in merged_config:
            merged_config[key] = user_config[key]
    
    return merged_config


def load_config():
    """
    設定ファイル (config.toml) を読み込む
    ファイルが存在しない場合はデフォルト設定を返す
    """
    default_config = _get_default_config()
    config_path = Path(CONFIG_FILE) if isinstance(CONFIG_FILE, str) else CONFIG_FILE
    
    if not config_path.exists():
        return default_config
    
    user_config = _load_user_config(config_path)
    return _merge_configs(default_config, user_config)

def save_config(config):
    """
    設定をTOML形式で設定ファイルに書き込む
    """
    config_path = Path(CONFIG_FILE) if isinstance(CONFIG_FILE, str) else CONFIG_FILE
    with config_path.open('w', encoding='utf-8') as f:
        toml.dump(config, f)

def setup_logging(config, is_daemon=False):
    """
    ログ設定のセットアップ (logging.config 使用)
    """
    daemon_config = config.get('daemon', {})
    logging_config = daemon_config.get('logging', {})
    
    # ログレベル設定
    log_level = logging_config.get('log_level', 'INFO').upper()
    log_file = logging_config.get('log_file', '')
    
    # ログ設定辞書を構築
    config_dict = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'daemon': {
                'format': '%(asctime)s [%(levelname)s] [Daemon] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'daemon' if is_daemon else 'standard',
                'stream': 'ext://sys.stdout'
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console']
        }
    }
    
    # ファイルハンドラーを追加
    if log_file and log_file.strip():
        config_dict['handlers']['file'] = {
            'class': 'logging.FileHandler',
            'level': log_level,
            'formatter': 'daemon' if is_daemon else 'standard',
            'filename': log_file,
            'encoding': 'utf-8'
        }
        config_dict['root']['handlers'].append('file')
    
    try:
        logging.config.dictConfig(config_dict)
        return logging.getLogger()
    except Exception as e:
        # フォールバック: 基本的なログ設定
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        if log_file:
            click.echo(f"警告: ログファイル '{log_file}' を開けません: {e}", err=True)
        return logging.getLogger()


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
    return os.getenv('DEVICE_NAME', Path.cwd().name)

async def _check_session_exists(session_name):
    """tmuxセッションが存在するかチェック"""
    try:
        result = await asyncio.create_subprocess_exec(
            'tmux', 'has-session', '-t', session_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.communicate()
        return result.returncode == 0
    except:
        return False


async def _resolve_device_mapping(device_name, device_mapping):
    """デバイスマッピングから設定を解決"""
    if device_name not in device_mapping:
        return None, None, None
    
    mapping = device_mapping[device_name]
    
    # マッピングが文字列の場合（セッションのみ指定）
    if isinstance(mapping, str):
        return mapping, None, None
    # マッピングが辞書の場合（詳細指定）
    elif isinstance(mapping, dict):
        return (
            mapping.get('session'),
            mapping.get('window'),
            mapping.get('pane')
        )
    
    return None, None, None


async def _get_current_session():
    """現在のtmuxセッション名を取得"""
    tmux_env = os.environ.get('TMUX')
    if not tmux_env:
        return None
    
    # tmux display-messageで現在のセッション名を取得
    try:
        result = await asyncio.create_subprocess_exec(
            'tmux', 'display-message', '-p', '#{session_name}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await result.communicate()
        return stdout.decode().strip()
    except:
        # フォールバック
        parts = tmux_env.split(',')
        if parts:
            socket_path = parts[0]
            session_name = Path(socket_path).name
            return session_name if session_name else 'default'
    return None


async def _try_mapped_session(device_name, device_mapping):
    """デバイスマッピングによるセッション解決を試行"""
    mapped_session, mapped_window, mapped_pane = await _resolve_device_mapping(device_name, device_mapping)
    
    if mapped_session and await _check_session_exists(mapped_session):
        click.echo(f"デバイス '{device_name}' のマッピング設定に従い、tmuxセッション '{mapped_session}' を使用します。")
        return mapped_session, mapped_window, mapped_pane
    elif mapped_session:
        click.echo(f"警告: マッピングされたtmuxセッション '{mapped_session}' が存在しません。デフォルトに戻ります。")
    
    return None, None, None


async def _try_device_name_session(device_name, device_mapping):
    """デバイス名と同名のセッション解決を試行"""
    if await _check_session_exists(device_name):
        click.echo(f"デバイス名と同じtmuxセッション '{device_name}' を使用します。")
        return device_name, None, None
    elif device_name not in device_mapping:
        click.echo(f"警告: tmuxセッション '{device_name}' が存在しません。")
    
    return None, None, None


async def _show_session_not_found_error(device_name):
    """セッションが見つからない場合のエラーメッセージ表示"""
    if device_name:
        click.echo(f"エラー: tmuxセッション '{device_name}' が見つかりません。", err=True)
        click.echo(f"以下のいずれかの対処を行ってください:", err=True)
        click.echo(f"  1. tmuxセッション '{device_name}' を作成する", err=True)
        click.echo(f"  2. config.tomlの[device_mapping]セクションでマッピングを設定する", err=True)
        click.echo(f"  3. config.tomlの[tmux].target_sessionを明示的に設定する", err=True)
    else:
        click.echo("エラー: tmuxセッションが見つかりません。", err=True)
        click.echo("`config.toml`で`[tmux].target_session`を明示的に設定してください。", err=True)


async def _resolve_target_session(config, device_name):
    """ターゲットセッションを決定"""
    tmux_config = config.get('tmux', {})
    session_setting = tmux_config.get('target_session')
    device_mapping = config.get('device_mapping', {})
    
    # 1. configに明示的な設定がある場合はそれを優先
    if session_setting and session_setting != 'current':
        return session_setting, None, None
    
    # 2. device_nameがある場合の処理
    if device_name:
        # まずdevice_mappingを確認
        result = await _try_mapped_session(device_name, device_mapping)
        if result[0]:
            return result
        
        # デバイス名と同じ名前のtmuxセッションが存在するか確認
        result = await _try_device_name_session(device_name, device_mapping)
        if result[0]:
            return result
    
    # 3. 現在のセッションを使用
    current_session = await _get_current_session()
    if current_session:
        click.echo(f"現在のtmuxセッション '{current_session}' を使用します。")
        return current_session, None, None
    
    # 4. エラー処理
    await _show_session_not_found_error(device_name)
    return None, None, None


async def _resolve_first_window(target_session):
    """最初のウィンドウを取得"""
    try:
        result = await asyncio.create_subprocess_exec(
            'tmux', 'list-windows', '-t', target_session, '-F', '#{window_index}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await result.communicate()
        windows = stdout.decode().strip().split('\n')
        return windows[0] if windows else '0'
    except:
        return '0'


async def _resolve_first_pane(target_session, target_window):
    """最初のペインを取得"""
    try:
        result = await asyncio.create_subprocess_exec(
            'tmux', 'list-panes', '-t', f"{target_session}:{target_window}", '-F', '#{pane_index}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await result.communicate()
        panes = stdout.decode().strip().split('\n')
        return panes[0] if panes else '0'
    except:
        return '0'


async def _apply_mapping_overrides(window_setting, pane_setting, mapped_window, mapped_pane):
    """マッピングのオーバーライドを適用"""
    if mapped_window is not None:
        window_setting = mapped_window
    if mapped_pane is not None:
        pane_setting = mapped_pane
    return window_setting, pane_setting


async def _resolve_window_pane(target_session, window_setting, pane_setting, mapped_window, mapped_pane):
    """ウィンドウとペインの設定を解決"""
    # マッピングで指定されたウィンドウ・ペインがあれば使用
    window_setting, pane_setting = await _apply_mapping_overrides(window_setting, pane_setting, mapped_window, mapped_pane)
    
    # デフォルト値の設定
    if window_setting is None:
        window_setting = 'first'
    if pane_setting is None:
        pane_setting = 'first'
    
    # ウィンドウ設定の処理
    if window_setting == 'first':
        target_window = await _resolve_first_window(target_session)
    else:
        target_window = window_setting
    
    # ペイン設定の処理
    if pane_setting == 'first':
        target_pane = await _resolve_first_pane(target_session, target_window)
    else:
        target_pane = pane_setting
    
    return target_window, target_pane


async def _send_tmux_commands(target, message):
    """tmuxにメッセージとEnterキーを送信"""
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


async def send_to_tmux(config, message, device_name=None):
    """
    tmuxにメッセージとEnterキーを送信する
    
    Args:
        config: 設定辞書
        message: 送信するメッセージ
        device_name: デバイス名（tmuxセッション名として使用）
    """
    tmux_config = config.get('tmux', {})
    window_setting = tmux_config.get('target_window')
    pane_setting = tmux_config.get('target_pane')
    
    # ターゲットセッションを決定
    target_session, mapped_window, mapped_pane = await _resolve_target_session(config, device_name)
    if target_session is None:
        return
    
    # ウィンドウとペインの設定を解決
    target_window, target_pane = await _resolve_window_pane(
        target_session, window_setting, pane_setting, mapped_window, mapped_pane
    )
    
    target = f"{target_session}:{target_window}.{target_pane}"
    
    # tmuxコマンドを送信
    await _send_tmux_commands(target, message)


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

def _find_target_device(devices, name, device_id):
    """デバイス一覧からターゲットデバイスを検索"""
    for device in devices:
        if device_id and device['iden'] == device_id:
            return device
        elif name and device.get('nickname') == name:
            return device
    return None


async def _delete_single_device(api_key, name, device_id, yes):
    """単一デバイスの削除"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            devices = await pb.get_devices()
            target_device = _find_target_device(devices, name, device_id)
            
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


def _format_created_time(created):
    """作成日時をフォーマット"""
    if created == 'N/A':
        return 'N/A'
    
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(created)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return str(created)


def _create_device_choice(device):
    """デバイス情報から選択ラベルを作成"""
    device_name = device.get('nickname', 'N/A')
    iden = device['iden']
    active = "✓" if device.get('active', False) else " "
    created = device.get('created', 'N/A')
    created_str = _format_created_time(created)
    
    # 製造元とモデル情報
    manufacturer = device.get('manufacturer', '')
    model = device.get('model', '')
    device_info = f" ({manufacturer} {model})" if manufacturer or model else ""
    
    label = f"[{active}] {device_name:<20} (ID: {iden[:10]}...) 作成: {created_str}{device_info}"
    return questionary.Choice(title=label, value=device)


async def _select_devices_for_deletion(devices):
    """削除対象デバイスの選択"""
    choices = [_create_device_choice(device) for device in devices]
    
    # チェックボックスで複数選択
    selected_devices = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: questionary.checkbox(
            "削除するデバイスを選択してください (スペースで選択/解除, Enterで確定):",
            choices=choices
        ).ask()
    )
    return selected_devices


async def _confirm_deletion(selected_devices):
    """削除確認"""
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
    return confirm


async def _delete_multiple_devices(pb, selected_devices):
    """複数デバイスの削除実行"""
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


async def _delete_devices_interactive(api_key, include_inactive):
    """複数選択削除モード"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            # デバイス一覧を取得
            devices = await pb.get_devices(active_only=not include_inactive)
            if not devices:
                if include_inactive:
                    click.echo("登録されているデバイスはありません。")
                else:
                    click.echo("アクティブなデバイスはありません。")
                    click.echo("非アクティブなデバイスも表示するには --include-inactive オプションを使用してください。")
                return
            
            # デバイス選択
            selected_devices = await _select_devices_for_deletion(devices)
            if not selected_devices:
                click.echo("削除をキャンセルしました。")
                return
            
            # 確認
            confirm = await _confirm_deletion(selected_devices)
            if not confirm:
                click.echo("削除をキャンセルしました。")
                return
            
            # 削除実行
            await _delete_multiple_devices(pb, selected_devices)
            
        except Exception as e:
            click.echo(f"デバイス一覧の取得中にエラーが発生しました: {e}", err=True)


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
            await _delete_single_device(api_key, name, device_id, yes)
        else:
            # 複数選択削除モード
            await _delete_devices_interactive(api_key, include_inactive)
    
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

async def _display_auto_route_devices(api_key):
    """自動ルーティングモード用のデバイス一覧表示"""
    click.echo("自動ルーティングモード: 全デバイスのメッセージを受信し、対応するtmuxセッションに送信します。")
    
    async with AsyncPushbullet(api_key) as pb:
        try:
            devices = await pb.get_devices(active_only=True)
            if devices:
                click.echo("\nアクティブなデバイス:")
                for d in devices:
                    nickname = d.get('nickname', 'N/A')
                    # tmuxセッションの存在確認
                    session_exists = await _check_session_exists(nickname)
                    status = "✓ tmuxセッションあり" if session_exists else "✗ tmuxセッションなし"
                    click.echo(f"  - {nickname} ({d['iden'][:8]}...) [{status}]")
                click.echo("")
        except Exception as e:
            click.echo(f"デバイス一覧取得エラー: {e}")


async def _find_device_by_name_or_id(devices, search_term):
    """デバイス一覧から名前またはIDでデバイスを検索"""
    for d in devices:
        if d.get('nickname') == search_term or d.get('iden') == search_term:
            return d['iden'], d.get('nickname', d['iden'])
    return None, None


async def _resolve_specific_device(api_key, device):
    """特定デバイスの解決"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            devices = await pb.get_devices()
            target_device_iden, device_name = await _find_device_by_name_or_id(devices, device)
            
            if target_device_iden:
                click.echo(f"デバイス '{device_name}' (ID: {target_device_iden}) として待ち受けます。")
                return target_device_iden, device_name
            else:
                click.echo(f"エラー: デバイス '{device}' が見つかりません。", err=True)
                return None, None
        except Exception as e:
            click.echo(f"デバイス情報の取得中にエラーが発生しました: {e}", err=True)
            return None, None


async def _resolve_default_device(api_key):
    """デフォルトデバイスの解決"""
    device_name = get_device_name()
    async with AsyncPushbullet(api_key) as pb:
        try:
            devices = await pb.get_devices()
            for d in devices:
                if d.get('nickname') == device_name:
                    target_device_iden = d['iden']
                    click.echo(f"デバイス '{device_name}' (ID: {target_device_iden}) として待ち受けます。")
                    return target_device_iden, device_name
            
            click.echo(f"エラー: デバイス '{device_name}' が登録されていません。", err=True)
            click.echo("先に 'push-tmux register' でデバイスを登録してください。", err=True)
            return None, None
        except Exception as e:
            click.echo(f"デバイス情報を取得できませんでした: {e}", err=True)
            return None, None


async def _resolve_target_device(api_key, device, all_devices, auto_route):
    """ターゲットデバイスの特定"""
    if device and not all_devices and not auto_route:
        return await _resolve_specific_device(api_key, device)
    elif all_devices and not auto_route:
        click.echo("警告: --all-devicesオプションは無効です。特定のデバイス宛のメッセージのみ処理します。")
        return None, None
    elif not auto_route:
        return await _resolve_default_device(api_key)
    else:
        return None, None


async def _create_auto_route_handler(api_key, config):
    """自動ルーティング用のメッセージハンドラーを作成"""
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
        session_exists = await _check_session_exists(target_device_name)
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
    
    return on_push_auto_route


def _create_specific_device_handler(config, target_device_iden, device_name):
    """特定デバイス用のメッセージハンドラーを作成"""
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
        await send_to_tmux(config, body, device_name=device_name)
    
    return on_push


async def _start_message_listener(api_key, on_push, debug):
    """メッセージリスナーを開始"""
    async with AsyncPushbullet(api_key) as pb:
        listener = LiveStreamListener(pb, types=('push',))
        
        if debug:
            click.echo("デバッグモードで実行中...")
        click.echo(f"Pushbulletのストリームを開始します。")
        click.echo("Ctrl+Cで終了します。")
        
        try:
            async for push in listener:
                await on_push(push)
        except KeyboardInterrupt:
            click.echo("\nストリームを停止します...")
        except Exception as e:
            click.echo(f"Pushbulletのストリームでエラーが発生しました: {e}", err=True)
        finally:
            click.echo("Pushbulletのストリームを終了しました。")


async def listen_main(device=None, all_devices=False, auto_route=False, debug=False):
    """
    listen コマンドのメインロジック（hupper 対応）
    """
    api_key = os.getenv('PUSHBULLET_TOKEN')
    if not api_key:
        click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
        return
    
    config = load_config()
    
    # auto-routeモードの場合、デバイス一覧を表示
    if auto_route:
        await _display_auto_route_devices(api_key)
        on_push = await _create_auto_route_handler(api_key, config)
    else:
        # ターゲットデバイスの特定
        target_device_iden, device_name = await _resolve_target_device(
            api_key, device, all_devices, auto_route
        )
        if target_device_iden is None and device_name is None:
            return
        
        on_push = _create_specific_device_handler(config, target_device_iden, device_name)
    
    # リスナーを開始
    await _start_message_listener(api_key, on_push, debug)


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