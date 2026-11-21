---
name: video-to-aboboo
description: 端到端把英语视频做成 Aboboo「磨耳朵」课件：YouTube 链接或本地视频 → 下载（yt-dlp）→ 转 MP3 → 按约 6 分钟切分 → 剪映重新识别中英字幕 → 子代理合并整句并翻译成双语 SRT → Aboboo 课件编辑器制作课件并上传到小组。剪映识别、翻译和 Aboboo 上传三条线并行流水。触发词：「把这个视频做成 aboboo 课件」「youtube 到 aboboo」「下载视频做磨耳朵课件」「视频切成 mp3 上传 aboboo」「端到端做课件」「老流程，这几个视频」。只做其中一步时：切分用 lesson-splitter，字幕用 jianying-subtitles，课件和上传用 aboboo-courseware。
---

# 视频 → Aboboo 课件（端到端）

先读 `working-preferences`。本流程由四个 skill 串起来，每一步的细节都在对应 skill 里：

| 步骤 | 用哪个 | 产物 |
|---|---|---|
| 1. 下载 | `lesson-splitter` 的 references/download.md | `NN - 标题 [id].mp4` + `.en.srt` |
| 2. 转 MP3 | ffmpeg（见下） | `NN - 标题 [id].mp3` |
| 3. 切分 | `lesson-splitter/scripts/split_lesson.py` | `NN-PP 标题 (起-止).mp3` 等 |
| 4. 编号 | `aboboo-courseware/scripts/make_mapping.py` | `剪映原始字幕/课件编号对照.csv` |
| 5. 剪映识别 | `jianying-subtitles` | `剪映原始字幕/<base>.jy.srt` |
| 6. 分句翻译 | `jianying-subtitles`（后台子代理） | `<id>.job.json` → `<base>.srt`（双语 GBK）+ `<base>.en.srt` |
| 7. 课件上传 | `aboboo-courseware` | `<base>.q99`，已上传到小组 |

随时查看每段走到了哪一步：
```
python -I "<skill>/scripts/status.py" "<mp3文件夹>"
```

## 0. 开工前问清楚（一次问完）

- 视频来源：链接列表、频道 top N，或本地文件
- **课件起始编号**：上一批用到 123，默认从 124 接着编
- 小组和分类：默认「国外日常视频」/ Shawn日常英语 / 磨耳朵（见 aboboo-courseware）
- 课号前缀 `NN`：同一批里每个视频一个两位数，不要和素材文件夹里已有的课号撞

工作目录：一批一个文件夹，例如 `C:\Users\Shugu\Videos\<批名>\`。所有切好的片段统一放进 `<批名>\<批名>-MP3与合并文稿\`，后面几步都在这个文件夹里做。

## 1～2. 下载、转 MP3

- **YouTube**：按 lesson-splitter 的 download.md 用 `python -m yt_dlp` 下载（H.264 720p 加英文字幕）。文件命名 `NN - %(title)s [%(id)s]`，下载放后台跑，同一时间只下一个，不要并发。
- **本地视频**：复制或改名成 `NN - 标题.mp4`。没有字幕的话，放一个只有一条的占位 `NN - 标题.en.srt`（split_lesson.py 必须有 srt 才肯切；真正的字幕由剪映重新生成）：
  ```
  1
  00:00:00,000 --> 00:00:01,000
  .
  ```
- 转 MP3：
  ```
  ffmpeg -n -i "NN - 标题.mp4" -vn -c:a libmp3lame -q:a 2 "NN - 标题.mp3"
  ```

## 3. 切分

```
python -I "<lesson-splitter>/scripts/split_lesson.py" "<批文件夹>" --target 6
```
每课会切到一个 `(MP3拆分)` 子文件夹。把所有片段的 mp3 **复制**到 `<批名>-MP3与合并文稿\`；原来的 `.en.srt` 备份到 `_原始en字幕备份\`。

## 4. 编号

```
python -I "<aboboo-courseware>/scripts/make_mapping.py" "<mp3文件夹>" --start <起始号>
```
把前 3 行和最后一个编号给用户看，确认后再继续。

## 5～7. 三条线流水并行

1. **先做第一个片段的全流程**（剪映 → 翻译 → 课件 → 上传），给用户看效果，确认后再批量。
2. 批量时的节奏：剪映识别一段需要 1～2 分钟，这段时间做 Aboboo 的「制作 + 上传」（每个约 1.5 分钟）；剪映导出一段，就运行 `archive_exports.py`；攒够 2～3 个待翻译的，就开一个后台翻译子代理（模板见 jianying-subtitles/references/translate_prompt.md）。
3. 每个 Aboboo 课件都要等它的双语 srt 生成好再做。按编号顺序上传。
4. 用户较久没收到消息时，用一句话报进度（例如「103–119 已上传，剪映在识别 22-19」）。

## 收尾核对和汇报

- 运行 `status.py`，四列全部为 Y；桌面上没有残留的 `jy_*.srt`。
- 向用户汇报：
  - 课件编号范围
  - 上传异常（报错但其实已通过审核的、重传过的）
  - 剪映把英文识别成中文导致缺句的片段
  - 子代理发现的主要听写错误（英文没改，中文按正确意思翻译了）
  - 文件位置
- 本次用到的最大编号写进 aboboo-courseware 的「编号接续」，方便下一批接着编。

## 权限和安全

- computer-use 需要申请：剪映专业版、Aboboo（文件资源管理器只有点击权限，不能打字）。
- 不碰付费功能。剪映的会员功能（如「智能字幕」的 VIP 选项）不要开。
- 下载不并发，也不用账号 cookie。
