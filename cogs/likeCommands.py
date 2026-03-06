import discord
from discord.ext import commands
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

# Daftar endpoint Free Fire API untuk fallback
FF_API_ENDPOINTS = [
    "https://api.freefire.com/v1/like",
    "https://api.freefireapi.com/v1/like", 
    "https://ff-api.garena.com/v1/like",
    "https://api.ff.garena.com/v1/like"
]

class LikeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def cog_load(self):
        """Dipanggil saat cog dimuat"""
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Dipanggil saat cog dibongkar"""
        if self.session:
            await self.session.close()

    @commands.command(name='like', aliases=['fflike', 'likeff'])
    async def like_player(self, ctx, player_id: str = None):
        """Like a Free Fire player menggunakan ID player"""
        
        # Validasi input
        if not player_id:
            embed = discord.Embed(
                title="❌ Error",
                description="Masukkan ID player Free Fire!\nContoh: `!like 123456789`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Cek apakah auth_client tersedia
        if not self.bot.auth_client:
            embed = discord.Embed(
                title="🔴 Auth Server Error",
                description="Tidak terhubung ke auth-server. Fitur like tidak tersedia.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Kirim status loading
        status_msg = await ctx.send(f"🔄 Memproses like untuk player `{player_id}`...")

        try:
            # 1. Dapatkan token JWT dari auth-client
            token = await self.bot.auth_client.get_token()
            
            # 2. Coba kirim like ke Free Fire API (coba semua endpoint)
            success = False
            last_error = None

            for endpoint in FF_API_ENDPOINTS:
                try:
                    url = f"{endpoint}/{player_id}"
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }

                    async with self.session.post(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            # Like berhasil
                            data = await resp.json() if resp.content_type == 'application/json' else {}
                            
                            embed = discord.Embed(
                                title="✅ Like Berhasil!",
                                description=f"Player **{player_id}** berhasil di-like",
                                color=discord.Color.green()
                            )
                            
                            # Tambah info tambahan jika ada
                            if data.get('player_name'):
                                embed.add_field(name="Nama Player", value=data['player_name'])
                            if data.get('total_likes'):
                                embed.add_field(name="Total Likes", value=data['total_likes'])
                            
                            await status_msg.edit(content=None, embed=embed)
                            success = True
                            break
                            
                        elif resp.status == 401:
                            # Token tidak valid
                            logger.warning(f"Token invalid untuk endpoint {endpoint}")
                            continue  # Coba endpoint lain
                            
                        elif resp.status == 404:
                            # Player tidak ditemukan
                            embed = discord.Embed(
                                title="❌ Player Tidak Ditemukan",
                                description=f"Player dengan ID `{player_id}` tidak ditemukan di Free Fire.",
                                color=discord.Color.red()
                            )
                            embed.add_field(
                                name="💡 Tips",
                                value="• Pastikan ID benar\n• Player mungkin mengganti ID\n• Coba cek di game langsung",
                                inline=False
                            )
                            await status_msg.edit(content=None, embed=embed)
                            return  # Stop kalau 404, karena pasti salah ID
                            
                        elif resp.status == 429:
                            # Rate limited
                            retry_after = resp.headers.get('Retry-After', '60')
                            last_error = f"Rate limited, tunggu {retry_after} detik"
                            continue
                            
                        else:
                            last_error = f"Error {resp.status}"
                            continue
                            
                except asyncio.TimeoutError:
                    last_error = "Timeout"
                    continue
                except aiohttp.ClientError as e:
                    last_error = f"Connection error: {str(e)}"
                    continue

            # Jika semua endpoint gagal
            if not success:
                embed = discord.Embed(
                    title="🔴 Free Fire API Error",
                    description="Tidak dapat terhubung ke server Free Fire saat ini.",
                    color=discord.Color.red()
                )
                
                # Kasih info tambahan
                if last_error:
                    embed.add_field(name="Error Detail", value=f"`{last_error}`", inline=False)
                
                embed.add_field(
                    name="💡 Saran",
                    value="• Coba lagi dalam beberapa menit\n• Cek status server Free Fire\n• Laporkan ke developer jika terus terjadi",
                    inline=False
                )
                
                await status_msg.edit(content=None, embed=embed)
                
        except Exception as e:
            # Error tidak terduga
            logger.exception(f"Unexpected error in like command: {str(e)}")
            embed = discord.Embed(
                title="⚠️ Internal Error",
                description="Terjadi kesalahan internal. Tim developer telah diberitahu.",
                color=discord.Color.red()
            )
            await status_msg.edit(content=None, embed=embed)

    @commands.command(name='ffstatus', aliases=['ffapi'])
    async def check_api_status(self, ctx):
        """Cek status koneksi ke Free Fire API"""
        
        embed = discord.Embed(
            title="📊 Status Free Fire API",
            description="Mengecek koneksi ke server...",
            color=discord.Color.blue()
        )
        
        status_msg = await ctx.send(embed=embed)
        
        # Cek auth-server dulu
        auth_status = "✅ Online" if self.bot.auth_client else "❌ Offline"
        
        # Test tiap endpoint
        working_endpoints = []
        failed_endpoints = []
        
        async with aiohttp.ClientSession() as session:
            for endpoint in FF_API_ENDPOINTS:
                try:
                    async with session.get(f"{endpoint.replace('/like', '/status')}", timeout=5) as resp:
                        if resp.status < 500:  # 200-499 berarti server merespon
                            working_endpoints.append(endpoint)
                        else:
                            failed_endpoints.append(endpoint)
                except:
                    failed_endpoints.append(endpoint)
        
        # Buat embed baru dengan hasil
        result_embed = discord.Embed(
            title="📊 Status Free Fire API",
            color=discord.Color.green() if working_endpoints else discord.Color.red()
        )
        
        result_embed.add_field(
            name="Auth Server",
            value=auth_status,
            inline=False
        )
        
        if working_endpoints:
            endpoints_text = "\n".join([f"✅ `{ep}`" for ep in working_endpoints[:3]])
            result_embed.add_field(
                name="Endpoint Tersedia",
                value=endpoints_text,
                inline=False
            )
        
        if failed_endpoints:
            failed_text = "\n".join([f"❌ `{ep}`" for ep in failed_endpoints[:3]])
            result_embed.add_field(
                name="Endpoint Gagal",
                value=failed_text,
                inline=False
            )
        
        result_embed.set_footer(text=f"Total {len(working_endpoints)}/{len(FF_API_ENDPOINTS)} endpoint aktif")
        
        await status_msg.edit(embed=result_embed)

    @commands.command(name='likeinfo', aliases=['ffinfo'])
    async def player_info(self, ctx, player_id: str = None):
        """Lihat info player Free Fire tanpa like"""
        
        if not player_id:
            await ctx.send("❌ Masukkan ID player! Contoh: `!ffinfo 123456789`")
            return

        if not self.bot.auth_client:
            await ctx.send("🔴 Tidak terhubung ke auth-server")
            return

        status_msg = await ctx.send(f"🔍 Mencari info player `{player_id}`...")

        try:
            token = await self.bot.auth_client.get_token()
            
            # Coba cari info player (gunakan endpoint GET)
            async with aiohttp.ClientSession() as session:
                url = f"https://api.freefire.com/v1/player/{player_id}"
                headers = {"Authorization": f"Bearer {token}"}
                
                try:
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            embed = discord.Embed(
                                title=f"👤 Info Player {player_id}",
                                color=discord.Color.blue()
                            )
                            
                            if data.get('player_name'):
                                embed.add_field(name="Nama", value=data['player_name'])
                            if data.get('level'):
                                embed.add_field(name="Level", value=data['level'])
                            if data.get('guild'):
                                embed.add_field(name="Guild", value=data['guild'])
                            if data.get('likes'):
                                embed.add_field(name="Total Likes", value=data['likes'])
                            if data.get('account_created'):
                                embed.add_field(name="Akun Dibuat", value=data['account_created'])
                            
                            await status_msg.edit(content=None, embed=embed)
                            
                        elif resp.status == 404:
                            await status_msg.edit(content=f"❌ Player `{player_id}` tidak ditemukan")
                        else:
                            await status_msg.edit(content=f"⚠️ Error {resp.status}")
                            
                except asyncio.TimeoutError:
                    await status_msg.edit(content="⏰ Timeout, server tidak merespon")
                    
        except Exception as e:
            await status_msg.edit(content=f"❌ Error: {str(e)}")

async def setup(bot):
    await bot.add_cog(LikeCommands(bot))
