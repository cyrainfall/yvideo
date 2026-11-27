# EP.07 接缝 — 封面 QA 记录（S2E01）

生产线：**/deepseek-whale-girl**（鲸鱼娘插画底图 + frame.md 同源叠字），按 `SERIES-S2-PLAN.md §7.4` 六步 SOP 执行。
出图日期：2026-11-26。ComfyUI `http://100.64.0.8:8188`（`whalegen.py check` 全绿：IPAdapter + animagine-xl-4.0-opt 在位）。

## 1. 方案（cover_plan.py，内容驱动，未手填 --scene）

| 项 | 值 |
| --- | --- |
| 输入文案 | `episodes/ep07/cover-brief.txt`（约 480 字，含 接缝 / capability seam / 三角色 / 服务定义 / 提供方 / 消费方 / 插件 / ctx.shell） |
| 命中关键词 | 插件、注册 |
| 母题 | `plugins` 插件与装配（次选：工具与权限 2 / 会话与上下文 1 / 事件与流 1） |
| 道具骨架 | `panels`（悬浮半透明面板） |
| 姿态 | `three_quarter`（upper body, three-quarter view, looking at viewer, gentle smile） |
| 场景词 | floating translucent UI panels around her, glowing module blocks, blueprint lines, dark background, blue holographic light, holding a small glowing cube… single deepseek blue rim light, warm white highlights, high contrast, cinematic |
| 角色占比 | `char_ratio 0.45`（胸像，手出画） |
| denoise | 0.60（甜区 0.58–0.65） |
| seed | **20261126**（方案原 seed 1600471938；首版耳部三修无果后按 SOP 同方案重出一次，仅换 seed，母题/场景/姿态/占比/denoise 全部保持） |
| 侧 | 方案给的 `side: left` 覆盖为 **right**：whalegen 的 init 压暗固定作用于左侧，只有角色靠右才得到「左标题区 + 右角色」的版式；同时与上一期（left）保持差异 |
| 叠字色 | accent `#4D6BFE` / text `#EDEAE3` / muted `#9BA2AD`（取自 frame.md） |

产出：`cover-base.jpg` 1920×1080（1280×720 生成 → 上采样）。底图**无任何文字**。

## 2. 必查闸门（逐项 read_image 验收）

| # | 项目 | 结果 | 说明与处理 |
| --- | --- | --- | --- |
| 1 | 鳍耳（深蓝鳍体 + 白内缘褶边） | **修后通过** | 首版为粉肉色耳内 + 浅青光边（精灵耳），**3 轮 inpaint 全部失败**（0.62 全糊、0.45 仍保留精灵耳、紧遮罩 0.55 出暗红内耳），按上限「3 修 → 重出一次」重出；重出版本为鳍状、青色鳍体 + 白色描边内缘，但耳内为**砖红色**（越出 frame.md 配色），再以确定性像素级重上色（maroon → 深海军蓝，保亮度、羽化 1.2px，共 2219 px）收敛为「深色鳍体 + 浅色内缘」，非全白羽毛。**记为条件通过**（鳍体非纯深蓝，缩略图尺度不可辨）。 |
| 2 | 发色（发根深蓝、发梢亮青） | 通过 | 发根中蓝、发梢亮青，渐变方向正确；中段偏淡（本机 1MP 常见发奶），未做 grade 以免整体偏色。 |
| 3 | 领口（白立领 + 深蓝领结 + 金边蓝宝石） | 通过 | 白立领 + 荷叶边、海军蓝领结、椭圆蓝宝石均到位；宝石外圈偏白、金边不明显（记为瑕疵，不做局部重绘以免二次崩坏）。 |
| 4 | 白围裙蓝鲸印花 | **修后通过** | 模型漏画 → `stamp` 贴回；裁剪尺度不理想（自带布纹竖线 + 两条深色腰封残条），改为先把 `assets/whale-print.png` 只保留鲸鱼连通域（去掉 3 处布料残片）+ 按帧内蓝/白两类配色重建 alpha，再按同坐标贴回（宽 132 px @ 0.677,0.787）。 |
| 5 | 裙摆金线刺绣 | N/A（胸像出画） | 胸像裁到腰部，裙摆在画外；袖口与胸衣有金色滚边 + 橘金铆钉，作为金色呼应。 |
| 6 | 手 | 通过 | 胸像 framing 让双手出画（首版底部曾有一小截白色手 + 橘色道具残条，重出版本已无）。 |
| 7 | 鲸尾 | N/A（胸像） | 坐姿/胸像几乎必丢，SOP 允许不强求。 |

额外清理：重出后呆毛上有一道品红/粉描边（约 400 px），按局部像素替换回发色（两轮阈值收紧），现仅剩极淡冷调边，缩略图不可见。

## 3. 叠字层（publish/cover-overlay.html）

沿用 S1 `cover-template.html` 的排字纪律：110px 边距、左上「系列名 36/800 + 期号 mono 22 0.18em」、下方 mono 副标签、超大字重标题、单行副标题 + 唯一 `<em>`、右列等宽小字逐行变淡、底部发丝线 + 页脚。

- 版式避让：主标题与副标题落在**左下实测暗区**（`(100,720)-(760,920)` 亮度 mean 46.8 / p99 49.2，无一个 >150 像素），完全避开左侧插件面板（面板最低到 y 697）与角色；右列落在右上暗区（`(1560,60)-(1880,340)` max 94），不与头发/头饰相碰。
- 唯一彩色：只有副标题的 `意大利面` 用 `#4D6BFE`；右列等宽字用暖白 + 透明度梯度（0.82 / 0.70 / 0.52），**没有第二个蓝**，符合 frame.md「一帧一个蓝焦点」。
- 色值全部取自 frame.md：`#0A0B0D` / `#EDEAE3` / `#9BA2AD` / `#5B6370` / `#232833` / `rgba(57,64,78,.9)` / `#4D6BFE`。
- 底部发丝线用 `line-strong`（`#39404E`）而非 `#232833`：叠在底图上 `#232833` 几乎不可见。

**渲染**：Chrome headless 在本机窗口高度上会吃掉约 40px（`--window-size=1920,1080` 实际视口 1040，底部留黑边），故按 `--window-size=1920,1120` 渲染后裁到 1920×1080。命令：

```bash
cd /Users/cyx/repo/yvideo
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --hide-scrollbars \
  --window-size=1920,1120 --screenshot=/tmp/cover-r3.png projects/dsh-anatomy/publish/cover-overlay.html
# 再裁剪 (0,0,1920,1080) → publish/ep07/cover.png
```

## 4. 最终文件

| 文件 | 说明 |
| --- | --- |
| `publish/ep07/cover-base.jpg` | 定稿底图 1920×1080，`sha256 5d317de7…e0205`（stamp + 耳色 + 呆毛清理后） |
| `publish/ep07/cover.png` | 最终封面 1920×1080 PNG，`sha256 b300233c…9264`，1.74 MB |
| `publish/ep07/cover-plan.json` | cover_plan.py 产出方案（seed 字段为方案原值，实际种子见上文） |
| `publish/cover-overlay.html` | 叠字页（1920×1080，引 `ep07/cover-base.jpg`） |
| `publish/ep07/qa/` | 验收裁图、被否首版（`cover-base-v1-rejected.jpg`）、三版耳部修复、缩略图（`thumb-final-640.png`）、init 垫图、未采用的 salt v2 方案 |
| `episodes/ep07/cover-brief.txt` | 内容 brief（cover_plan 输入） |

## 5. 未解 / 留给后面的事

- 鳍耳颜色仍未到「深蓝鳍体 + 白褶边」的教科书状态：本机无 ControlNet，inpaint 在小区域（~150px）没有 IP-Adapter 约束时只会反复画回精灵耳；这一项是这条生产线目前最脆的闸门。建议后续在 `whalegen.py` 的 inpaint 分支打开 `--ipa-weight 0.6`（当前硬编码 0）后再试，或换 0.58–0.62 之外的姿态候选。
- 底图里仍有 1–2 处模型自发的高饱和细节（胸衣橘金铆钉、耳内亮边），属角色原设定色范围，未越出 frame.md 的「一帧一蓝焦点」。
- 本集简介必须带署名行（角色原型 上善无形「溟月」、女仆装二创 ZipZipPipe，CC BY-NC-SA 4.0）——见 §7.4 版权条款。
