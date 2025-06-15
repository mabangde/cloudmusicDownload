# 网易云音乐下载




核心是调用pycloudmusic库实现音乐下载，工具亮点是不受下载次数限制（VIP用户默认只能下载300首版权音乐），原理是获取播放会下载未加密的音乐文件

- VIP用户二维码登录
- 歌单 单曲批量下载
- 不受下载次数限制 
- 根据信息填充音乐包括专辑图片、歌词等ID3标签（元数据）省去二次刮削整理


## 参数说明
```
PLAYLIST_IDS = [13743018730]   # 待下载歌单列表任意数量
SONG_IDS = []  # 待下载歌曲列表任意数量
QUALITY = "mp3"  # 建议auto 默认下载能播放的最高音质，此处指定mp3 只下载mp3音乐
```


## 相关项目
- https://github.com/FengLiuFeseliud/pycloudmusic
- https://github.com/taurusxin/ncmdump
