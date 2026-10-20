---
name: eval-validate-judge
description: 校准大模型评委：把人工标注数据切成训练 / 开发 / 测试三份，在开发集上反复改评委直到真阳性率（TPR）和真阴性率（TNR）都超过 90%，在测试集上只跑一次拿最终结果，再用 Rogan-Gladen 公式修正线上通过率并给出置信区间。用户说「评委准不准」「校准 LLM 评估」「自动评估能不能信」「评测结果怎么报给老板」时使用。代码类检查不需要它，写单元测试即可。
whenToUse: 用 eval-judge-prompt 写好评委之后、正式用它的结果做决策之前。
---

# 校准大模型评委

> 改编自 [hamelsmu/evals-skills](https://github.com/hamelsmu/evals-skills) 的 `validate-evaluator`（MIT，Hamel Husain）。改动：中文化；名字改为 `eval-validate-judge`；补了向非技术干系人汇报的写法；产出物默认存进 AIPM 工坊的评测目录。代码和公式保持原样。

让大模型评委和人的判断对齐。

## 总览

1. 人工标注数据切成训练（10%～20%）、开发（40%～45%）、测试（40%～45%）
2. 在开发集上跑评委，算 TPR / TNR
3. 改评委，直到开发集上 TPR 和 TNR 都 > 90%
4. 在留出的测试集上跑一次，得到最终 TPR / TNR
5. 用偏差修正公式处理线上数据

## 前提

- 已经写好评委提示词（见 `eval-judge-prompt`）
- 人工标注数据：约 100 条轨迹，每个失败类别都有通过 / 失败标签
  - 尽量 50 条通过、50 条失败（即使真实分布不均衡，也要平衡）
  - 标签必须来自懂业务的人，不能外包给不懂行的标注员
- 准备好可当示例的候选数据

## 流程

### 第 1 步：切分数据

切成三份互不重叠的集合：

| 集合 | 大小 | 用途 | 规则 |
|---|---|---|---|
| **训练集** | 10%～20%（约 10～20 条） | 评委提示词里的示例来源 | 只放明确的通过和失败，直接写进提示词 |
| **开发集** | 40%～45%（约 40～45 条） | 反复改评委 | 绝不放进提示词，可以反复评 |
| **测试集** | 40%～45%（约 40～45 条） | 最终无偏的准确度 | 开发期间**不看**，最后只用一次 |

目标：开发集和测试集合起来，通过和失败各 30～50 条。即使真实分布倾斜也用平衡切分，否则失败样本太少，TNR 测不准。

```python
from sklearn.model_selection import train_test_split

# 第一刀：切出测试集
train_dev, test = train_test_split(
    labeled_data, test_size=0.4, stratify=labeled_data['label'], random_state=42
)
# 第二刀：从剩下的里切出训练示例
train, dev = train_test_split(
    train_dev, test_size=0.75, stratify=train_dev['label'], random_state=42
)
# 结果：约 15% 训练，45% 开发，40% 测试
```

### 第 2 步：在开发集上跑评委

开发集每条都跑一遍，和人工标签对比。

### 第 3 步：算 TPR 和 TNR

**TPR（真阳性率）**：人说通过的，评委有多少也说通过？

```
TPR = (评委说通过 且 人说通过) / (人说通过)
```

**TNR（真阴性率）**：人说失败的，评委有多少也说失败？

```
TNR = (评委说失败 且 人说失败) / (人说失败)
```

```python
from sklearn.metrics import confusion_matrix

tn, fp, fn, tp = confusion_matrix(human_labels, evaluator_labels,
                                   labels=['Fail', 'Pass']).ravel()
tpr = tp / (tp + fn)
tnr = tn / (tn + fp)
```

用 TPR / TNR，不用精确率 / 召回率，也不用原始准确率。这两个指标直接对应后面的偏差修正公式。Cohen's Kappa 只用来衡量两个标注员之间的一致性，不用来衡量评委和标准答案。

### 第 4 步：逐条看分歧

评委和人工不一致的每一条都看：

| 分歧类型 | 评委 | 人 | 怎么改 |
|---|---|---|---|
| **误放行** | 通过 | 失败 | 评委太松。加强失败的定义，或加边界示例 |
| **误拦截** | 失败 | 通过 | 评委太严。说清通过的定义，或调整示例 |

每条分歧决定：
- 改评委提示词的措辞
- 从训练集里换或加示例
- 给这个边界情况加明确规则
- 把标准拆成更细的子检查

### 第 5 步：迭代

改评委提示词，在开发集上重跑，直到 TPR 和 TNR 稳定。

**停止标准：**
- **目标**：TPR > 90% 且 TNR > 90%
- **最低可接受**：TPR > 80% 且 TNR > 80%

**卡住时：**

| 问题 | 办法 |
|---|---|
| TPR 和 TNR 都低 | 换更强的模型当评委 |
| 一个低一个还行 | 专门看低的那个指标的分歧 |
| 都卡在目标以下 | 把标准拆成更小、更原子的检查 |
| 某类输入总判错 | 从训练集加针对性示例 |
| 人工标签本身前后不一 | 回头检查标签，可能是标注规则要改 |

### 第 6 步：在测试集上最终测量

在留出的测试集上**只跑一次**，记下最终 TPR 和 TNR。

看了测试集结果以后不能再改了接着测。要改就拿新的开发数据回到第 4 步。

### 第 7 步（可选）：估计真实成功率（Rogan-Gladen 修正）

评委在未标注的线上数据上给出的原始分数是有偏的。要报告准确的整体通过率，就修正已知的评委误差：

```
theta_hat = (p_obs + TNR - 1) / (TPR + TNR - 1)
```

其中：
- `p_obs` = 评委判为通过的未标注轨迹占比
- `TPR`、`TNR` = 测试集上测得的值
- `theta_hat` = 修正后的真实成功率估计

结果截断到 [0, 1]。TPR + TNR - 1 接近 0 时公式失效（评委和瞎猜差不多）。

**例：**
- 评委 TPR = 0.92，TNR = 0.88
- 500 条线上轨迹，400 条判为通过 → p_obs = 0.80
- theta_hat = (0.80 + 0.88 - 1) / (0.92 + 0.88 - 1) = 0.68 / 0.80 = **0.85**
- 真实成功率约 85%，不是原始的 80%

### 第 8 步：置信区间

只给一个点估计不够，要用 bootstrap 算置信区间。

```python
import numpy as np

def bootstrap_ci(human_labels, eval_labels, p_obs, n_bootstrap=2000):
    """修正后成功率的 bootstrap 95% 置信区间。"""
    n = len(human_labels)
    estimates = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        h = np.array(human_labels)[idx]
        e = np.array(eval_labels)[idx]

        tp = ((h == 'Pass') & (e == 'Pass')).sum()
        fn = ((h == 'Pass') & (e == 'Fail')).sum()
        tn = ((h == 'Fail') & (e == 'Fail')).sum()
        fp = ((h == 'Fail') & (e == 'Pass')).sum()

        tpr_b = tp / (tp + fn) if (tp + fn) > 0 else 0
        tnr_b = tn / (tn + fp) if (tn + fp) > 0 else 0
        denom = tpr_b + tnr_b - 1

        if abs(denom) < 1e-6:
            continue
        theta = (p_obs + tnr_b - 1) / denom
        estimates.append(np.clip(theta, 0, 1))

    return np.percentile(estimates, 2.5), np.percentile(estimates, 97.5)

lower, upper = bootstrap_ci(test_human, test_eval, p_obs=0.80)
print(f"95% CI: [{lower:.2f}, {upper:.2f}]")
```

也可以用 `judgy`（`pip install judgy`）：

```python
from judgy import estimate_success_rate

# judgy 要求 0/1 整数标签（1 = 通过，0 = 失败）
test_labels = [1 if l == 'Pass' else 0 for l in test_human_labels]
test_preds = [1 if l == 'Pass' else 0 for l in test_eval_labels]
unlabeled_preds = [1 if l == 'Pass' else 0 for l in prod_eval_labels]

theta_hat, lower, upper = estimate_success_rate(
    test_labels, test_preds, unlabeled_preds
)
print(f"修正后成功率: {theta_hat:.2f}")
print(f"95% CI: [{lower:.2f}, {upper:.2f}]")
```

## 实践建议

- **锁定评委的模型版本**：用带日期的快照版本号，不用会自动更新的别名。服务商会悄悄更新模型，造成无声的漂移。
- **重新校准**：改了评委提示词、换了模型、或线上置信区间突然变宽时。
- 约 100 条标注（50 通过 / 50 失败）。少于 60 条，置信区间会很宽。
- **一位信得过的业务专家**标注效率最高。做不到的话，让两个人各自独立标 20～50 条，先解决分歧再继续。
- **提高 TPR 比提高 TNR 更能收窄置信区间**：修正公式除以 `(TPR + TNR - 1)`，TPR 低会让分母变小，放大估计误差。

## 向老板汇报时

非技术干系人只需要三句话：评委和人工判断的一致程度（TPR / TNR，用「人说好的它认出了多少、人说不好的它抓住了多少」来讲）；修正后的真实成功率；这个数字的可信范围（置信区间）。不要只报一个原始通过率。

## 反模式

- **默认评委「就是准的」**，不做校准。评委可能一直漏掉失败，或一直误伤通过的。
- **用原始准确率或一致百分比。** 用 TPR 和 TNR。类别不平衡时原始准确率会误导：90% 都通过时，一个永远说「通过」的评委准确率 90%，却一个失败都没抓到。
- **开发集、测试集的数据当示例。** 数据泄露。
- **把开发集表现当最终准确度。** 开发集数字偏乐观，测试集才是无偏估计。
- **只报原始评委分数，不做偏差修正。** 报整体通过率就要用 Rogan-Gladen 公式（第 7 步）。
- **只给点估计，不给置信区间。** 测试集小的时候，85% 很可能是 78%～92%，要把范围告诉大家。

## 产出位置

在 AIPM 工坊里存到当前项目的 `05-评测/`：`评委校准-<失败类别>.md`（切分方式、开发集迭代记录、测试集 TPR / TNR、修正后成功率和置信区间）。
