# glitch-mv-toolkit（AI エージェント向け）

- まず `README.md` と `docs/HOWTO-glitch-mv.md` を読む。作業の進め方は `.claude/skills/glitch-mv-scripted-edit/SKILL.md`。
- 素材・前の版は上書きしない。版を上げて別名で出す。
- 確認は軽いプレビュー（`MODE=preview`）で出し、依頼者の OK のあとで本番（`MODE=final`、4K は `SCALE=2`）。
- 見ていない・聴いていないことは「未確認」と書く。音は `tools/loudness_curve.py`、映像は `tools/contact_sheet.sh`、版の比較は `tools/compare_versions.py` で測る。
- フォントや大きな映像・音は Git に入れない（`.gitignore` 済み）。作例の素材は `media/images/` とリリース `media-v1` にある。
- 有料の生成（動画・画像・曲）は、依頼された分だけにする。
