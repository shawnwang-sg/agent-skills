# 用 yt-dlp 下载 YouTube 频道 top N 视频 + 英文字幕

全部用 `python -m yt_dlp`（pip 装的最新版），不要用 System32 里的旧 exe。

## 1. 列出频道全部视频并按播放量排序
YouTube 频道页的 `?sort=p`（热门排序）参数已失效，yt-dlp 拿到的仍是最新发布顺序，所以要自己排：
```bash
python -m yt_dlp --flat-playlist --print "%(view_count)s|%(duration)s|%(id)s|%(title)s" "https://www.youtube.com/@频道名/videos" > all_videos.txt
sort -t'|' -k1,1nr all_videos.txt | head -20 > top20_list.txt
```
一个 600 多视频的频道约 1 分钟。把 `top20_list.txt` 一起复制到输出目录做备案（命名 `00_top20_list.txt`）。

## 2. 下载（H.264 720p + AAC + 英文 srt）
按排名逐个下载，这样文件名前缀就是排名，用户临时说"第 2 个不要"只需跳过那一行：
```bash
n=0; while IFS='|' read -r views dur id title; do n=$((n+1)); rank=$(printf "%02d" "$n");
python -m yt_dlp "https://www.youtube.com/watch?v=$id" \
  -f "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b" \
  --merge-output-format mp4 --write-subs --write-auto-subs --sub-langs en --convert-subs srt \
  -N 4 --no-overwrites --download-archive "OUT/archive.txt" --newline --progress-delta 120 \
  -o "OUT/$rank - %(title)s [%(id)s].%(ext)s"; done < top20_list.txt
```
- `vcodec^=avc1` 很重要：不加会选到 AV1（格式 398），部分播放器放不了。H.264 720p 是格式 136。
- 19 个视频约 12 小时内容 ≈ 4 GB，几分钟到半小时不等，用 `run_in_background` 跑，日志写到 scratchpad。
- 用户已有某个视频（例如桌面上网页下载的 1080p）时，直接 `mv` 进目录按 `NN - 标题 [id].mp4` 改名，再只补字幕：
  ```bash
  python -m yt_dlp "https://www.youtube.com/watch?v=ID" --skip-download --write-subs --write-auto-subs --sub-langs en --convert-subs srt -o "OUT/NN - %(title)s [%(id)s].%(ext)s"
  ```

## 3. 常见警告（可忽略）
- `No supported JavaScript runtime could be found` —— 不装 deno 也能下到 720p/1080p 全部格式。
- `no impersonate target is available` —— 不影响下载。
- 文件名里的 `:`、`?` 会被 yt-dlp 换成全角 `：`、`？`，`split_lesson.py` 会在生成片段名时再转回 ASCII。
