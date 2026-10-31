# 迷失之地藏品对照藏品数据

选择鸣徽 / 武备 / 卡牌等画面里，OCR 认出的候选原来直接用文字生成藏品对象，等级记 `?`、是否武备按分类猜。现在先到藏品数据（`LostVoidContext.all_artifact_list`，按分类存在 `cate_2_artifact`）里找对应的藏品，找到了就用数据里的「是否武备」「等级」。

## 规则

`LostVoidContext.find_artifact_data(category, name)`：

- 分类按 `_normalize_category_text` 归一后比较；「卡牌」和「无详情」两类放在一起找。
- 名称用 `str_utils.find_in_list_with_fuzzy` 模糊匹配，`cutoff=0.7`，允许个别错字（如「万能催化剂」读成「万能催化物」）。
- 找不到返回空，说明候选名没识别出来（比如 OCR 读到的是效果描述），这时保留原来的做法：用 OCR 文字生成、等级记 `?`。

用到的地方：

- `[类型]名称` 结构的候选；
- 「xxx」yyy 结构的卡牌候选；
- 没有 `[]` 结构、归为次选的候选；
- 带分支（如 `-α`）的藏品，优先用数据里的分支藏品。

## 每局开始清空动态优先级

`LostVoidContext.reset_for_new_challenge()` 在「出战」「矩阵行动-开始挑战」时调用，清空上一局 `UpdatePriorityOperation` 得到的动态优先级、放弃组和「已更新优先级」标记。原来只在应用启动时清空，连续刷多局时上一局的动态优先级会带到下一局。
