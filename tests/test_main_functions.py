#!/usr/bin/env python3
"""
メイン機能のテスト（カバレッジ向上）
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import json
import aiohttp
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asyncpushbullet import AsyncPushbullet, LiveStreamListener


@pytest.mark.skip(reason="PyPI asyncpushbulletパッケージに移行したため無効化")
class TestAsyncPushbulletRequest:
    """AsyncPushbulletの_requestメソッドのテスト（PyPIパッケージに移行したため無効化）"""
    
    @pytest.fixture
    def api_key(self):
        return "test_api_key"
    
    @pytest.fixture
    def pb(self, api_key):
        return AsyncPushbullet(api_key)
    
    @pytest.mark.asyncio
    async def test_request_without_session(self, pb):
        """セッションがない状態でのリクエスト"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"test": "data"})
        mock_response.raise_for_status = MagicMock()
        
        mock_session = MagicMock()
        mock_session.request = MagicMock()
        mock_session.request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.request.return_value.__aexit__ = AsyncMock()
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await pb._request("GET", "test")
            
        assert result == {"test": "data"}
        assert pb.session == mock_session
    
    @pytest.mark.asyncio
    async def test_request_with_session(self, pb):
        """セッションがある状態でのリクエスト"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"test": "data"})
        mock_response.raise_for_status = MagicMock()
        
        mock_session = MagicMock()
        mock_session.request = MagicMock()
        mock_session.request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.request.return_value.__aexit__ = AsyncMock()
        pb.session = mock_session
        
        result = await pb._request("GET", "test")
        
        assert result == {"test": "data"}
        mock_session.request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_request_http_error(self, pb):
        """HTTPエラーのテスト"""
        # モックレスポンスを作成
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), 
            history=(), 
            status=404,
            message="Not Found",
            headers={}
        )
        mock_response.json = AsyncMock(return_value={})
        
        # セッションをモック
        mock_session = MagicMock()
        mock_session.request = MagicMock()
        mock_session.request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.request.return_value.__aexit__ = AsyncMock(return_value=False)
        
        pb.session = mock_session
        
        with pytest.raises(aiohttp.ClientResponseError):
            await pb._request("GET", "test")


@pytest.mark.skip(reason="PyPI asyncpushbulletパッケージに移行したため無効化")
class TestAsyncPushbulletListenerFullFlow:
    """AsyncPushbulletListenerの完全なフローテスト（PyPIパッケージに移行したため無効化）"""
    
    @pytest.fixture
    def api_key(self):
        return "test_api_key"
    
    @pytest.fixture
    def on_push_handler(self):
        return AsyncMock()
    
    @pytest.fixture
    def listener(self, api_key, on_push_handler):
        return AsyncPushbulletListener(api_key, on_push_handler)
    
    @pytest.mark.asyncio
    async def test_listener_message_processing(self, listener):
        """リスナーのメッセージ処理フロー（シンプル版）"""
        # tickleを直接テストすることで、WebSocketループの複雑さを回避
        mock_pushes = [
            {"iden": "push1", "active": True, "dismissed": False, "type": "note"}
        ]
        
        # listener.pb_clientを直接モック
        listener.pb_client.get_pushes = AsyncMock(return_value=mock_pushes)
        
        # _handle_tickleメソッドを直接テスト
        await listener._handle_tickle()
        
        # on_pushハンドラーが呼ばれた
        assert listener.on_push.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_handle_tickle_with_pushes(self, listener):
        """tickle処理でプッシュがある場合"""
        mock_pushes = [
            {"iden": "push1", "active": True, "dismissed": False, "type": "note"},
            {"iden": "push2", "active": False, "dismissed": False, "type": "note"},
            {"iden": "push3", "active": True, "dismissed": True, "type": "note"}
        ]
        
        # listener.pb_clientを直接モック
        listener.pb_client.get_pushes = AsyncMock(return_value=mock_pushes)
        
        await listener._handle_tickle()
        
        # アクティブで未読のプッシュのみ処理
        assert listener.on_push.call_count == 1
        listener.on_push.assert_called_with(mock_pushes[0])
    
    @pytest.mark.asyncio
    async def test_handle_tickle_no_pushes(self, listener):
        """tickle処理でプッシュがない場合"""
        with patch('async_pushbullet.AsyncPushbullet') as MockPB:
            mock_pb = AsyncMock()
            mock_pb.get_pushes = AsyncMock(return_value=[])
            mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
            mock_pb.__aexit__ = AsyncMock()
            MockPB.return_value = mock_pb
            
            await listener._handle_tickle()
            
            # プッシュがないのでon_pushは呼ばれない
            listener.on_push.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_tickle_exception(self, listener):
        """tickle処理で例外が発生した場合"""
        with patch('async_pushbullet.AsyncPushbullet') as MockPB:
            mock_pb = AsyncMock()
            mock_pb.get_pushes = AsyncMock(side_effect=Exception("API Error"))
            mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
            mock_pb.__aexit__ = AsyncMock()
            MockPB.return_value = mock_pb
            
            # 例外が発生してもクラッシュしない
            await listener._handle_tickle()
            listener.on_push.assert_not_called()


@pytest.mark.skip(reason="PyPI asyncpushbulletパッケージに移行したため無効化")
class TestAsyncPushbulletEdgeCases:
    """AsyncPushbulletのエッジケーステスト（PyPIパッケージに移行したため無効化）"""
    
    @pytest.fixture
    def api_key(self):
        return "test_api_key"
    
    @pytest.fixture
    def pb(self, api_key):
        return AsyncPushbullet(api_key)
    
    @pytest.mark.asyncio
    async def test_get_devices_empty_response(self, pb):
        """get_devicesで空のレスポンスの場合"""
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}  # devicesキーがない
            
            result = await pb.get_devices()
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_pushes_with_all_params(self, pb):
        """get_pushesで全パラメータを指定した場合"""
        mock_response = {"pushes": [{"iden": "test"}]}
        
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await pb.get_pushes(
                modified_after=1234567890,
                limit=50,
                active=False
            )
            
            # パラメータが正しく渡された
            call_args = mock_request.call_args
            params = call_args[1]["params"]
            assert params["modified_after"] == 1234567890
            assert params["limit"] == 50
            # active=Falseの場合、activeパラメータは送信されない
            assert "active" not in params
    
    @pytest.mark.asyncio
    async def test_create_device_custom_model(self, pb):
        """create_deviceでカスタムモデル指定"""
        mock_response = {"iden": "new_device"}
        
        with patch.object(pb, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await pb.create_device("Test Device", model="custom-model")
            
            # カスタムモデルが使用された
            call_args = mock_request.call_args
            json_data = call_args[1]["json"]
            assert json_data["model"] == "custom-model"
            assert json_data["nickname"] == "Test Device"
            assert json_data["manufacturer"] == "push-tmux"