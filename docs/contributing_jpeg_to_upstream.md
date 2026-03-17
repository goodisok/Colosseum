# 将 JPEG 压缩改动提交给 Colosseum 上游

## 推荐流程（全新克隆、只贡献 JPEG）

1. 新目录克隆上游并拉子模块：
   ```bash
   git clone https://github.com/CodexLabsLLC/Colosseum.git Colosseum-PR
   cd Colosseum-PR
   git submodule update --init
   ```
2. 添加你的 Fork：`git remote add goodisok https://github.com/goodisok/Colosseum.git`
3. 建分支：`git checkout -b feature/jpeg-compression origin/main`
4. 按 `docs/airsim_jpeg_compression_modifications.md` 只改 8 个文件
5. 提交并推送：`git add -A` → `git commit -m "Add JPEG compression..."` → `git push goodisok feature/jpeg-compression`
6. 在 GitHub 上对 CodexLabsLLC/Colosseum 提 Pull Request

## 远程说明

- **origin**：克隆的仓库（如 CodexLabsLLC/Colosseum）
- **goodisok**：你的 Fork，推送用 `git push goodisok 分支名`
