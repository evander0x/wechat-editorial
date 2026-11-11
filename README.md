# wechat-editorial

公众号排版模板「编辑手记」：把 Markdown 渲染成**可直接粘进微信编辑器**的 HTML——全内联样式，无外链字体、无脚本，微信不会剥样式。

## 特性

- 5 套主题一键切换：

| 主题 | 风格 | 参考来源 |
|---|---|---|
| `teal`（默认） | 深青「编辑手记」版式：序号块 / 高亮 / 卡片 / 金句区 | — |
| `ink` | 墨色版 | — |
| `orange` | 橙色科技流：一句一段、32px 橙色编号、浅橙描边图片 | 逛逛GitHub |
| `yicai` | 财经蓝快讯流：17px 两端对齐 + 蓝色小节标题 | 第一财经 |
| `deepseek` | 蓝发布体：15px 深灰左对齐 + 黑色加粗小节 + 品牌蓝链接 | 深度求索 |

- 内置约定语法：栏目标签、导语、`==高亮==`、数字序号小节、清单卡片、金句区、地址胶囊、图注、代码块、表格
- `--fragment` 产出无外壳正文片段，供推草稿箱等程序直接使用

## 安装

把整个目录复制或软链到你的 Agent 技能目录即可：

```bash
ln -s /path/to/wechat-editorial ~/.workbuddy/skills/wechat-editorial
# 或 ~/.claude/skills/ 等同类目录
```

## 使用

```bash
python3 wechat_layout.py article.md -o article.html                 # 默认 teal
python3 wechat_layout.py article.md -o article.html --theme orange  # 换主题
python3 wechat_layout.py article.md -o fragment.html --fragment     # 正文片段（推草稿箱用）
```

浏览器打开 `article.html`，白卡内正文全选复制进公众号编辑器即可保留样式。

Markdown 写法（栏目标签、高亮、卡片、金句等约定）见 [SKILL.md](SKILL.md)。

## 相关仓库

- [autopilot-wechat](https://github.com/evander0x/autopilot-wechat) — 主仓库：全流程自动化、完整文档与主题样式演示
- [wechat-autopilot](https://github.com/evander0x/wechat-autopilot) — 配套的全流程编排 skill（选题 → 写稿 → 审稿 → 排版 → 推草稿箱）

## 安全

输出全部为内联样式，不含 `<style>`、外链字体与脚本；不读取、不存储任何公众号凭证。

## License

MIT
