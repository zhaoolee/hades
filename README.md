# Hades 中英台词全集

> **Hades Listener 网页版：** [https://zhaoolee.github.io/hades/](https://zhaoolee.github.io/hades/)<br>
> 直接查看完整中英台词，或使用浏览器英文语音进行听写练习。拥有正版游戏的用户还可以在本地提取游戏原声。无需登录，学习进度保存在本机浏览器。

从本机安装的《Hades》一代游戏文件中提取并合并完整中英台词。新版实现不再依赖旧版 `pandas` 脚本，也不会按台词文本全局去重；**每个台词 ID 都会保留**。

![Hades](./images/5ab320be-5da4-4bd3-9cdc-9ba933fcab4d.gif)

## 当前本地生成结果

- 唯一台词 ID：**20,694**
- 中英非空配对：**20,694**（即两种语言字段均非空）
- 缺英文：**0**
- 缺中文：**0**
- 台词频道：**42**
- 游戏字幕 CSV 双语 ID：**13,305**
- 最终版 SJSON/Lua 活动台词：**7,390**
- 两套编号重叠：**1**

完整数据见：

- [`generated/README.md`](./generated/README.md)：频道索引与统计
- [`generated/all.csv`](./generated/all.csv)：完整 CSV
- [`generated/all.json`](./generated/all.json)：完整 JSON
- [`generated/audit.json`](./generated/audit.json)：重复、冲突、Lua 候选和来源审计
- [`generated/characters/`](./generated/characters/)：按台词频道拆分的 Markdown

## 数据来源

程序从游戏目录读取：

```text
Content/Subtitles/en/*.csv
Content/Subtitles/zh-CN/*.csv
Content/Game/Text/zh-CN/_*.zh-CN.sjson
Content/Scripts/*.lua
```

合并策略：

1. 游戏自带英文/简中字幕 CSV 按 ID 配对，保留旧语音表中的短语音、战斗语音、歌曲等内容。
2. 最终版简中 SJSON 提供当前活动台词的 ID、中文、Speaker 和事件上下文。
3. Lua 中与 `Cue = "/VO/<ID>"` 同一层台词表的直接 `Text` 字段提供英文；同 ID 有多个候选时，优先使用 SJSON 事件注释消歧，无法唯一消歧时采用确定性回退并在 `audit.json` 的 `method` 字段中明确标记。
4. `MegaeraField_0003` 等只存在于结构化 Lua 块注释中的台词使用受控回退恢复。
5. ID 是唯一键；即使两条台词文本完全相同，也不会互相覆盖。

所有输出中的来源路径均相对于游戏根目录，不包含本机绝对路径。

## 网页版：Hades Listener

网页位于 `web/`，使用 Preact、TypeScript 与 Vite 构建，可直接部署到 GitHub Pages。

- **查看模式**：按角色筛选、全文搜索、浏览中英对照并朗读英文。
- **听写模式**：隐藏英文原文，根据中文提示和语音输入答案，逐词显示遗漏与多余内容。
- **学习进度**：记录完成数、正确率和待复习台词，数据只保存在浏览器 `localStorage`。
- **语音说明**：默认使用设备自带的浏览器英文 TTS；本地提取原声后自动优先播放游戏语音，缺失或加载失败时回退 TTS。

### 从本机正版游戏提取原声

原版语音版权归 Supergiant Games 所有，仓库和 GitHub Pages **不分发游戏音频**。以下命令只从用户自己安装的正版游戏中提取语音到 `web/public/audio/`；该目录已加入 `.gitignore`，不会被提交。

```bash
uv venv .venv-audio
uv pip install --python .venv-audio/bin/python -r requirements-audio.txt

# 回退解码需要系统提供 ffmpeg（Ubuntu/Debian：sudo apt install ffmpeg）
ffmpeg -version

# 下载官方 vgmstream Linux 版并解压（处理 fsb5 不认识的少量 Vorbis 头）
mkdir -p .tools/vgmstream
curl -fL https://github.com/vgmstream/vgmstream/releases/download/r2117/vgmstream-linux.zip \
  -o /tmp/vgmstream-linux.zip
unzip -oq /tmp/vgmstream-linux.zip -d .tools/vgmstream

.venv-audio/bin/python -m hades_dialogue extract-audio \
  --game-root "$HOME/.local/share/Steam/steamapps/common/Hades" \
  --vgmstream-cli .tools/vgmstream/vgmstream-cli
```

`fsb5` 会快速无损重建绝大多数 Ogg；遇到其旧版头部表不认识的语音时，程序自动通过官方 [vgmstream](https://github.com/vgmstream/vgmstream) 解码，并用系统 `ffmpeg` 转为 Ogg。提取过程会持续显示进度。完成后启动网页：

```bash
cd web
npm install
npm run dev
```

`web/scripts/prepare-data.mjs` 会读取本地音频清单，只给成功提取的台词附加原声路径。没有本地音频时，网页行为与 GitHub Pages 一致，继续使用浏览器 TTS。

### 从本机正版游戏提取人物立绘

人物立绘同样只从用户自己的正版游戏中提取，不随仓库或 GitHub Pages 分发。提取结果保存在已被 Git 忽略的 `web/public/portraits/`：

```bash
uv venv .venv-portraits
uv pip install --python .venv-portraits/bin/python -r requirements-portraits.txt

.venv-portraits/bin/python -m hades_dialogue extract-portraits \
  --game-root "$HOME/.local/share/Steam/steamapps/common/Hades"
```

提取工具会从 `GUI.pkg` 中导出主要角色立绘、裁去透明边缘并转换为适合网页加载的 WebP。网页会按台词频道显示对应人物；本地图片缺失时仍可正常显示纯文字界面。

本地启动：

```bash
cd web
npm install
npm run dev
```

测试及构建：

```bash
cd web
npm test
npm run build
```

推送到 `main` 后，`.github/workflows/pages.yml` 会使用 Node.js 24 运行测试、构建并部署网页。

## 使用方法

要求 Python 3.11 或更高版本，无第三方依赖。

### 生成完整数据

```bash
python3 -m hades_dialogue extract \
  --game-root "/path/to/Steam/steamapps/common/Hades" \
  --output generated
```

本机 Steam 默认安装路径示例：

```bash
python3 -m hades_dialogue extract \
  --game-root "$HOME/.local/share/Steam/steamapps/common/Hades" \
  --output generated
```

命令执行成功后会输出统计 JSON。若存在缺失英文或中文，退出码非零。

### 只做审计

```bash
python3 -m hades_dialogue audit \
  --game-root "/path/to/Steam/steamapps/common/Hades"
```

### 兼容旧入口

```bash
python3 main.py extract --game-root "/path/to/Hades" --output generated
```

`main.py` 现在只是 `python -m hades_dialogue` 的兼容入口；旧版依赖 pandas 的 README 生成逻辑已停用。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖：

- CSV BOM、引号、重复和冲突
- 多段下划线及字母后缀台词 ID
- SJSON 注释、Speaker 和中文字符串
- Lua 嵌套表、跨多行 `Cue`/`Text`
- Lua 前置/后置行注释及块注释回退
- 同 ID 多候选消歧
- 相同文本、不同 ID 不被去重
- 确定性重复生成
- 错误游戏路径处理

## 可重复性

同一份游戏输入连续生成两次，所有受管输出文件应保持字节级一致。生成结果不包含时间戳、随机值或游戏目录的绝对路径。

## 历史内容

`images/`、`videos/`、旧版 `Subtitles/` 与海报素材均予以保留，便于追溯项目早期版本。当前完整数据以 `generated/` 为准。
