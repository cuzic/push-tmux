#!/usr/bin/env python3
"""
async_pushbullet.pyのテスト
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from async_pushbullet import AsyncPushbullet, AsyncPushbulletListener


class TestAsyncPushbullet:
    """AsyncPushbulletクラスのテスト"""
    
    @pytest.fixture
    def api_key(self):
        return "test_api_key_123"
    
    @pytest.fixture
    def pb(self, api_key):
        return AsyncPushbullet(api_key)
    
    @pytest.mark.asyncio
    async def test_init(self, api_key):
        """初期化のテスト"""
        pb = AsyncPushbullet(api_key)
        assert pb.api_key == api_key
        assert pb.session is None
        assert pb._headers["Access-Token"] == api_key
        assert pb._headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_context_manager(self, pb):
        """コンテキストマネージャーのテスト"""
        async with pb as client:
            assert client.session is not None
            assert isinstance(client.session, aiohttp.ClientSession)
        # __aexit__後はセッションがクローズされる
        assert pb.session.closed
    
    @pytest.mark.asyncio
    async def test_get_user(self, pb):
        """get_userメソッドのテスト"""
        mock_response = {"email": "test@example.com", "name": "Test User"}
        
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await pb.get_user()
            
            mock_request.assert_called_once_with("GET", "users/me")
            assert result == mock_response
    
    @pytest.mark.asyncio
    async def test_get_devices(self, pb):
        """get_devicesメソッドのテスト"""
        mock_devices = [
            {"iden": "dev1", "nickname": "Device 1", "active": True},
            {"iden": "dev2", "nickname": "Device 2", "active": False}
        ]
        mock_response = {"devices": mock_devices}
        
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # 全デバイス取得
            result = await pb.get_devices()
            assert result == mock_devices
            
            # アクティブなデバイスのみ
            result = await pb.get_devices(active_only=True)
            assert len(result) == 1
            assert result[0]["active"] is True
    
    @pytest.mark.asyncio
    async def test_create_device(self, pb):
        """create_deviceメソッドのテスト"""
        mock_response = {"iden": "new_device", "nickname": "Test Device"}
        
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await pb.create_device("Test Device")
            
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0] == ("POST", "devices")
            assert call_args[1]["json"]["nickname"] == "Test Device"
            assert result == mock_response
    
    @pytest.mark.asyncio
    async def test_delete_device(self, pb):
        """delete_deviceメソッドのテスト"""
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            await pb.delete_device("device_id_123")
            
            mock_request.assert_called_once_with("DELETE", "devices/device_id_123")
    
    @pytest.mark.asyncio
    async def test_push_note(self, pb):
        """push_noteメソッドのテスト"""
        mock_response = {"iden": "push_123", "type": "note"}
        
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # 全デバイス宛
            result = await pb.push_note("Title", "Body")
            call_args = mock_request.call_args
            assert call_args[0] == ("POST", "pushes")
            assert call_args[1]["json"]["type"] == "note"
            assert call_args[1]["json"]["title"] == "Title"
            assert call_args[1]["json"]["body"] == "Body"
            assert "device_iden" not in call_args[1]["json"]
            
            # 特定デバイス宛
            result = await pb.push_note("Title", "Body", device_iden="dev_123")
            call_args = mock_request.call_args
            assert call_args[1]["json"]["device_iden"] == "dev_123"
    
    @pytest.mark.asyncio
    async def test_get_pushes(self, pb):
        """get_pushesメソッドのテスト"""
        mock_pushes = [{"iden": "push1"}, {"iden": "push2"}]
        mock_response = {"pushes": mock_pushes}
        
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await pb.get_pushes()
            assert result == mock_pushes
            
            # パラメータ付き
            result = await pb.get_pushes(modified_after=123456, limit=10)
            call_args = mock_request.call_args
            assert call_args[1]["params"]["modified_after"] == 123456
            assert call_args[1]["params"]["limit"] == 10
    
    @pytest.mark.asyncio
    async def test_dismiss_push(self, pb):
        """dismiss_pushメソッドのテスト"""
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            await pb.dismiss_push("push_123")
            
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0] == ("POST", "pushes/push_123")
            assert call_args[1]["json"]["dismissed"] is True
    
    @pytest.mark.asyncio
    async def test_close(self, pb):
        """closeメソッドのテスト"""
        # セッションがない場合
        await pb.close()  # エラーなく実行される
        
        # セッションがある場合
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        pb.session = mock_session
        await pb.close()
        mock_session.close.assert_called_once()


class TestAsyncPushbulletListener:
    """AsyncPushbulletListenerクラスのテスト"""
    
    @pytest.fixture
    def api_key(self):
        return "test_api_key_123"
    
    @pytest.fixture
    def on_push(self):
        return AsyncMock()
    
    @pytest.fixture
    def listener(self, api_key, on_push):
        return AsyncPushbulletListener(api_key, on_push)
    
    @pytest.mark.asyncio
    async def test_init(self, api_key, on_push):
        """初期化のテスト"""
        listener = AsyncPushbulletListener(api_key, on_push)
        assert listener.api_key == api_key
        assert listener.on_push == on_push
    
    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(self, listener):
        """キーボード割り込みのテスト"""
        with patch('websockets.connect', side_effect=KeyboardInterrupt):
            await asyncio.wait_for(listener.run(), timeout=1)  # タイムアウト付きで実行
    
    @pytest.mark.asyncio
    async def test_handle_tickle(self, listener):
        """tickleハンドリングのテスト"""
        mock_pushes = [
            {"iden": "push1", "active": True, "dismissed": False},
            {"iden": "push2", "active": False, "dismissed": False},
            {"iden": "push3", "active": True, "dismissed": True}
        ]
        
        with patch('async_pushbullet.AsyncPushbullet') as MockPB:
            mock_pb = AsyncMock()
            mock_pb.get_pushes = AsyncMock(return_value=mock_pushes)
            mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
            mock_pb.__aexit__ = AsyncMock()
            MockPB.return_value = mock_pb
            
            await listener._handle_tickle()
            
            # アクティブで未読のプッシュのみ処理される
            assert listener.on_push.call_count == 1
            listener.on_push.assert_called_with(mock_pushes[0])