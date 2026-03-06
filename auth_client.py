import aiohttp
import jwt
import time
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AuthClient:
    def __init__(self, auth_server_url, uid, password):
        self.auth_server_url = auth_server_url
        self.uid = uid
        self.password = password
        self.token = None
        self.token_expiry = 0
        self.lock = asyncio.Lock()
    
    async def _request_token(self):
        """Minta token baru dari auth-server"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.auth_server_url}/login",
                    json={"uid": self.uid, "password": self.password},
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.token = data['token']
                        # Hitung expiry (simpan dalam timestamp)
                        self.token_expiry = time.time() + data['expires_in'] - 60  # buffer 60 detik
                        logger.info("✅ Token JWT berhasil didapatkan")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"Gagal login: {resp.status} - {error}")
                        return False
        except Exception as e:
            logger.error(f"Error saat minta token: {str(e)}")
            return False
    
    async def get_valid_token(self):
        """Dapatkan token yang masih valid (refresh jika perlu)"""
        async with self.lock:
            # Jika token tidak ada atau akan expired dalam 60 detik, refresh
            if not self.token or time.time() >= self.token_expiry:
                logger.info("Token expired atau tidak ada, minta baru...")
                success = await self._request_token()
                if not success:
                    raise Exception("Tidak bisa mendapatkan token autentikasi")
            return self.token
    
    async def get_ff_api_key(self):
        """Ambil Free Fire API key dari auth-server menggunakan token"""
        token = await self.get_valid_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.auth_server_url}/get_ff_api_key",
                headers={"Authorization": f"Bearer {token}"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['ff_api_key']
                else:
                    logger.error(f"Gagal ambil FF API key: {resp.status}")
                    return None
