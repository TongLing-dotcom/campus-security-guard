# 大文件获取说明（Releases）

为保证仓库轻量，**视频与音频素材不纳入 Git 历史**，通过 GitHub Releases 分发。
用 `git clone` 拿到的是完整可读的**文档 + 脚本 + 字幕 + 提示词 + 配置模板**；
需要重跑合成或观看成片时，再按本文下载素材。

---

## 一、需要下载的文件

| # | GitHub 上的文件名 | 中文说明 | 大小 | 放置到 |
| :-: | :-- | :-- | --: | :-- |
| 1 | `film_v12.7_1080p.mp4` | **成片**（56.30s / 1080p） | 29.4 MB | `release/成片/` |
| 2 | `bgm_a_tension.mp3` | 配乐 A · 悬念压迫 | 4.1 MB | `release/audio/` |
| 3 | `bgm_b_warmth.mp3` | 配乐 B · 温暖释然 | 7.5 MB | `release/audio/` |
| 4 | `audio_mix_v12.7.wav` | 人声 ＋ BGM ＋ 铃声 混合音轨 | 10.3 MB | `release/audio/` |
| 5 | `source_footage.mp4` | **源画面《改3》**（重出片必需） | 16.3 MB | `release/源画面/` |

> **下面这些体积很小，已直接包含在仓库中，无需下载**：
> 15 条人声（`assets/voice/`，共 230 KB）、原创电话铃声（`assets/audio/`）、17 张 UI 素材（`assets/ui/`）。

---

## 二、下载方式

### 方式 A：网页下载（推荐）

1. 打开仓库页右侧 **Releases** → 选择最新版本（如 `v12.7`）
2. 在 **Assets** 区下载上表文件
3. 按「放置到仓库内路径」一列解压 / 移动即可

### 方式 B：命令行（需已安装 [GitHub CLI](https://cli.github.com/)）

```bash
gh release download v12.7 --repo <你的用户名>/anti-fraud-short-video
```

---

## 三、作为维护者：如何发布这些文件

```bash
cd anti-fraud-short-video

# 1. 把要分发的素材放到 release/ 下（该目录已在 .gitignore 中）
mkdir -p release/成片 release/audio release/源画面
cp "/你的路径/真假妈妈_成片_v12.7_配音音乐字幕_56.3s_1080p.mp4" release/成片/
cp "/你的路径/配音音乐混合轨_v12.7.wav"                        release/audio/
cp "/你的路径/BGM_A_悬念压迫.mp3" "/你的路径/BGM_B_温暖释然.mp3"  release/audio/
cp "/你的路径/改3.mp4"                                          release/源画面/

# 2. 创建 Release 并上传
gh release create v12.7 \
  --title "v12.7 · 真妈妈台词语病修正版" \
  --notes "成片 56.30s / 1080p；修正镜7③「没事啥啊」→「没啥事啊」。" \
  release/成片/*.mp4 release/audio/* release/源画面/*.mp4
```

---

## 四、素材哈希（校验用）

| 文件 | 大小 |
| :-- | --: |
| 成片 v12.7 | 30,819,020 B |
| 源画面 `改3.mp4` | MD5 `c865587097b9af63daa215153309e53f` |

> 源画面 `改3.mp4` 自始至终**只读未改动**，MD5 在多次出片前后保持一致。

---

## 五、为什么不直接放进仓库？

- 单次成片 + 音频即约 78 MB，会让 `git clone` 变慢，且视频无版本控制价值（每次重出片都会变）；
- GitHub 对单文件超过 50 MB 会告警、超过 100 MB 直接拒绝；
- 需要版本化大文件时，应使用 **Git LFS**，本项目为纯文本 + Release 的简单结构，无需引入 LFS。
