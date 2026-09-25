"""Render existing verified S02 aggregates, without model or data access."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def render(folder):
    folder = Path(folder)
    def read(name):
        return json.loads((folder / name).read_bytes())
    def write(name, value):
        with (folder / name).open('x', encoding='utf8', newline='') as stream:
            stream.write(value)
    def table_csv(name, rows):
        with (folder / name).open('x', encoding='utf8', newline='') as stream:
            writer = csv.DictWriter(stream, list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    def fmt(value):
        return 'null' if value is None else f'{value:.6f}'
    comparison, summary, fits = read('COMPARISON.json'), read('SUMMARY.json'), read('FITS.json')
    for item in read('MANIFEST.json')['files']:
        raw = (folder / item['path']).read_bytes()
        if len(raw) != item['size'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Verified aggregate changed')
    candidates = [comparison['baseline'], *comparison['candidates']]
    metrics = [('clean', 'Accuracy'), ('clean', 'macro_F1'), ('clean', 'MAE'),
               ('clean', 'Pearson'), ('attempted96', 'macro_F1'), ('attempted96', 'MAE')]
    eligible = {row['id']: row for row in comparison['selection']['eligibility']}
    rows = []
    lines = ['# S02 有界改进：完整结果', '',
        'VERIFIED：12/12 新 fit、15/15 固定后处理配置全部完成，无失败、无资源停止、无重试。'
        '这些结果来自官方 TRAIN/VALID，未评价 TEST 或附件3/4。', '',
        f"执行代码：`{summary['code_commit']}`；执行配置 SHA256：`{summary['execution_config_sha256']}`（规范 JSON）。",
        f"内部 campaign 耗时 {summary['runtime_seconds']:.3f} 秒；外部监督器完整耗时见 RUN_RECEIPT.json。"
        '各 fit 的训练与最终验证用时见 FITS.json，不能把 campaign 总耗时叫作纯优化时间。', '',
        '## 冠军与比较范围', '',
        '**M2，固定 seed17，晋升。** M2 是文本主干残差融合加 TRAIN 类别权重。'
        '候选在三 seed 均值和固定 seed17 两个层面相对旧 S01 的六项指标均不劣，并存在严格增益。'
        '完整比较后恢复 seed17 的 clean＋144 views，预测张量数值一致，原子指针已更新；旧模型继续保留。', '',
        '完整三 seed 均值用于排序；最终 seed17 并非按其表现挑选。晋升合格候选为 '
        + '、'.join(row['id'] for row in eligible.values() if row['eligible'])
        + '，M2 的 attempted96 平均 macro-F1 在合格者中最高。', '',
        '## 全部配置的三 seed 均值 ± 样本 SD', '',
        '|配置|clean Accuracy ↑|clean macro-F1 ↑|clean MAE ↓|clean Pearson ↑|attempted96 F1 ↑|attempted96 MAE ↓|晋升资格|',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for candidate in candidates:
        identity = candidate['id']
        qualification = eligible.get(identity, dict(eligible=False, reasons=['ORIGINAL_REFERENCE']))
        row = dict(configuration=identity, complete=candidate['complete'], parameters=candidate['parameters'],
                   full144_inference_seconds=candidate['inference_cost'], promotion_eligible=qualification['eligible'],
                   promotion_reasons=';'.join(qualification['reasons']))
        cells = []
        for scope, key in metrics:
            mean, sd = candidate['means'][scope][key], candidate['seed_sd'][scope][key]
            row[f'{scope}_{key}_mean'] = mean
            row[f'{scope}_{key}_seed_sd_ddof1'] = sd
            row[f'{scope}_{key}_seed17'] = candidate['per_seed']['17'][scope][key]
            cells.append(fmt(mean) + ' ± ' + fmt(sd))
        rows.append(row)
        lines.append('|' + '|'.join([identity, *cells, 'YES' if qualification['eligible'] else 'NO']) + '|')
    table_csv('CANDIDATE_COMPARISON.csv', rows)
    lines += ['', 'SD 描述三个固定训练 seed 的离散程度，不是置信区间或显著性。'
              '推理成本是本机完整144-view测量，W 使用其组件测量之和，不是生产延迟基准。', '',
              '## 全部配置的固定 seed17', '',
              '|配置|Accuracy|macro-F1|MAE|Pearson|attempted96 F1|attempted96 MAE|',
              '|---|---:|---:|---:|---:|---:|---:|']
    for candidate in candidates:
        values = [candidate['per_seed']['17'][scope][key] for scope, key in metrics]
        lines.append('|' + '|'.join([candidate['id'], *map(fmt, values)]) + '|')
    lines += ['', '## Pareto、robust 排序与未采用理由', '',
              'clean 四指标均值的 Pareto 集：' + '、'.join(comparison['clean_pareto']['pareto_ids']) + '。', '',
              '通过 clean F1/MAE guard 后的 robust 排序（不同于严格晋升资格）：', '',
              ' → '.join(comparison['robust_ranking']), '',
              '所有未采用候选的具体退化项如下；NO_STRICT_IMPROVEMENT 表示未产生超过数值容差的严格改善。', '']
    for item in eligible.values():
        reason = '满足严格资格，但冻结排序落后于 M2' if item['eligible'] and item['id'] != 'M2' else '最终晋升' if item['id'] == 'M2' else '; '.join(item['reasons'])
        lines.append(f"- {item['id']}：{reason}。")
    lines += ['', '### 负结果与机制解释边界', '',
        '- W1 beta=0 真实恢复验证了 CAT 分类＋T 回归的互补性：分类保持原样，回归改善；但其鲁棒分类得分低于 M2。',
        '- 非零中性偏置以及 W2 等权组合均未满足全指标严格晋升条件，不能仅展示某一项增益。',
        '- M1 的三 seed clean macro-F1 低于旧模型，因此即使其他指标改善也不能晋升；其较低 MAE、较高 Pearson 使其仍在 clean Pareto 集。',
        '- M3 相对 M1 的 attempted96 均值 F1 更低、MAE 更高；本轮没有证据支持该增强改善这两项均值。',
        '- M4 相对 M3 的 attempted96 均值有小幅改善，但没有超过 M2；KD 并非本轮胜者。',
        '- M2/M1 的配对设计隔离类别权重差异；这些探索性 VALID 观察不证明普遍因果机制。S02 与 S01 的结构和 checkpoint 协议不同，不能声称跨阶段仅改变一个因素。', '',
        '## 全部 fit 与逐轮数据', '',
        '|fit|选中 epoch|完成 epoch|fit 秒|144-view 推理秒|状态|', '|---|---:|---:|---:|---:|---|']
    for fit in fits:
        lines.append(f"|{fit['id']}|{fit['selected_epoch']}|{fit['evaluated_epochs']}|{fit['runtime_seconds']:.3f}|{fit['inference_seconds']:.3f}|{fit['status']}|")
    epoch_count = read('EPOCH_CURVES.json')['total_completed_epoch_rows']
    lines += ['', f'共 **{epoch_count}** 条完成 epoch 记录。`EPOCH_CURVES.csv` 及 `epochs/*.json` 保存每个 seed 的全部轮次，不仅是最优轮次。', '',
        'TRAIN loss 按样本数加权。TRAIN online 指标来自每个 batch 更新前、当前训练 view 上的预测；权重在一轮内变化，'
        '因此不能将它标成整轮结束 checkpoint 的 clean TRAIN 评价。VALID 是该轮结束的 clean 验证。'
        '曲线包括 CE、加权 CE、MAE、加权 KD、总 loss、学习率、耗时、早停、选点及人工缺失资格计数。', '',
        '## 连续缺失与符号不一致', '',
        '`conditions/*.json` 给出19配置各96条件的每 seed、均值和样本SD；`FACTOR_DESCRIPTIVES.csv` '
        '按模态组、位置和支持坐标窗口比例分组。先 random replicate 平均，再条件等权，再 seed 平均，'
        '不能把144视图直接等权。条件 coverage 使用单次728条 attempted总体，非独立新样本；无合法窗口 CLEAN_ONCE，未删除样本。', '',
        '`SIGN_DISAGREEMENT.csv` 保存全部候选和 seed 的分类/回归符号不一致率。严格0为Neutral；'
        '不为减少不一致而重定义标签或拟合新阈值。', '',
        '## 来源、可恢复性与局限', '',
        'SOURCE SHA256：`' + summary['source_sha256'] + '`。训练 seeds17/29/43，mask roots2207/1103。'
        '设计、公式与公开论文的采用/否决见 `docs/research/S02/PROTOCOL.md` 和 `SOURCES.md`；外部论文效果不是本赛题结果。', '',
        '`MODEL_REGISTRY.json` 绑定 M2-s17 best checkpoint/config/code 与旧冠军哈希。模型、normalizer、optimizer/RNG、私有预测保留本地，'
        '公开仓库只有安全聚合；仅凭公开文件不能重新恢复私有权重。`RUN_RECEIPT.json` 记录实际执行命令的路径替代和环境来源。', '',
        'S02 是看到 S01 结果后的探索；同一个 VALID 参与选轮次、候选和偏置，存在乐观选择偏差。'
        '未做 TEST 或附件3/4评价，无显著性结论、无全局最优结论。KNOWN_AVAILABILITY 仅为仿真接口；附件3可靠mask仍 UNKNOWN，'
        '自然结构零不能自动解释为人工缺失。正式专项部署和Q3需另获授权。', '',
        '本轮12/12、15/15全部完成，失败与资源停止计数实际为0；并非将未运行指标填0。'
        '旧R01/S01未运行候选仍保留原NOT_RUN状态。新授权已经消费，retry=0，不继续增加fit。', '']
    sign_rows = []
    records = [(fit['recipe'], fit['seed'], fit['metrics']) for fit in fits]
    records += [(p['id'], r['seed'], r) for p in read('POSTPROCESS.json') for r in p['per_seed']]
    for identity, seed, record in records:
        sign = record['sign_disagreement_clean']
        sign_rows.append(dict(configuration=identity, seed=seed, clean_disagreement_count=sign['disagreement_count'],
            clean_total_count=sign['total_count'], clean_fraction=sign['fraction'],
            attempted96_equal_condition_fraction=record['sign_disagreement_attempted96']))
    table_csv('SIGN_DISAGREEMENT.csv', sign_rows)
    write('RESULTS.md', '\n'.join(lines))
    write('README.md', '# S02 verified results\n\nStart with RESULTS.md. For paper curves use EPOCH_CURVES.csv; '
          'for all candidate mean/SD/fixed-seed comparisons use CANDIDATE_COMPARISON.csv. '
          'FACTOR_DESCRIPTIVES.csv, conditions/*.json and SIGN_DISAGREEMENT.csv retain all configurations.\n\n'
          'MANIFEST.json binds the original38 aggregate exports. PUBLICATION_MANIFEST.json separately binds this report, '
          'receipts, code and governance updates. Existing S01 records remain historical and immutable.\n')
    return dict(status='RENDERED', configurations=len(candidates), epoch_rows=epoch_count, sign_rows=len(sign_rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', required=True)
    print(json.dumps(render(parser.parse_args().folder)))
