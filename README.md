# 大白饭庄园

种萝卜、蒸米饭，招几个帮手。等 DSH 跑任务的时候，可以回来收一波菜，或者看看商业街今天卖了多少。

**[打开浏览器试玩](https://jjjacksong.github.io/dsh-plugin-white-rice-farm/)** · **[下载 v0.6.0-preview.8](https://github.com/JJJACKsong/dsh-plugin-white-rice-farm/releases/tag/v0.6.0-preview.8)**

## 这一版怎么玩

- 先收掉成熟的萝卜。选好作物后点地块种植，拖动地图可以查看别处。
- 点「商业街」，上面是手绘的两间店、田野和石板路，下面看仓库、货架和成交。单品满 6 份可以批发，也可以一件件上架零售。
- 田园农产铺开局就能用。庄园 Lv.3 解锁大白食品铺，也能让磨坊和面包房加工米粉、米糕。

进度存在当前浏览器或 DSH 里。换浏览器、换设备，或从 DSH 转到网页版时，可以在「设置」里导出存档，再到新入口导入。网页版也可以下载单个 HTML 文件离线玩。 同一浏览器开了两个农场页面时，关闭正在玩的页面后，可在另一个页面重新打开并接续存档。

## 在 DSH 里玩

从 Release 下载 `dsh-plugin-white-rice-farm-0.6.0-preview.8.tgz`。桌面端退出 DSH 后，用随桌面 App 安装的 `dsh` 执行下面的命令，将文件名替换成下载包的实际路径。

```sh
dsh plugin --profile desktop add ./dsh-plugin-white-rice-farm-0.6.0-preview.8.tgz
```

重新打开 DSH，点侧栏的「大白饭庄园」。DSH Web 用户可把命令里的 `desktop` 换成对应的 Web 配置名，例如 `web`。

## 本地构建

需要 Node.js 20 或更新版本和 Python 3。

```sh
npm run build
npm test
```

`index.html` 是独立网页版，`lib/client.js` 是 DSH 客户端。安装 `requirements-dev.txt` 中的依赖和 Playwright Chromium 后，可运行 `npm run verify` 检查游戏规则、素材和浏览器交互。

试玩问题可以发到 [GitHub Issues](https://github.com/JJJACKsong/dsh-plugin-white-rice-farm/issues)。反馈时附上浏览器或 DSH 版本，以及出问题前的操作。

本仓库供查看源码和试玩，项目未授予开源许可证。素材来源见 [素材清单](assets/asset-manifest.json)。
