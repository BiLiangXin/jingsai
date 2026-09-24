"""Render final SAFE S01 exports; no training, selection, or private input access.

Reads only SUMMARY.json, FITS.json, CONFIGURATION_SUMMARY.json and
BASELINE_AND_SELECTION.json. Writes RESULTS.md and CONFIGURATION_TABLE.csv to
a new directory outside any Git repository. Missing results remain missing.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
from pathlib import Path

NAMES = ("SUMMARY.json", "FITS.json", "CONFIGURATION_SUMMARY.json", "BASELINE_AND_SELECTION.json")
SEEDS = (17, 29, 43)
BASE_ARCHS = ("B-T", "B-A", "B-V", "B-CAT")
NORMALIZERS = ("identity", "zscore")
BASE_IDS = tuple(a + "-" + n for a in BASE_ARCHS for n in NORMALIZERS) + ("LATE-identity", "LATE-zscore", "PRIOR")
FINAL_IDS = set(BASE_IDS) | {a + "-" + n for a in ("C0", "R0") for n in NORMALIZERS}
PEARSON_REASONS = {"insufficient_n", "zero_target_variance", "zero_prediction_variance"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def number(value, low=None, high=None):
    require(type(value) in (int, float) and math.isfinite(value), "Nonfinite/nonnumeric metric")
    require((low is None or value >= low) and (high is None or value <= high), "Out-of-range number")
    return value


def integer(value, low=0):
    require(type(value) is int and value >= low, "Invalid integer")
    return value


def hash_value(value, length=64, nullable=False):
    if value is None and nullable:
        return None
    require(isinstance(value, str) and re.fullmatch("[a-f0-9]{" + str(length) + "}", value), "Invalid provenance digest")
    return value


def finite_tree(value):
    if isinstance(value, float):
        require(math.isfinite(value), "Nonfinite JSON value")
    elif isinstance(value, dict):
        for item in value.values():
            finite_tree(item)
    elif isinstance(value, list):
        for item in value:
            finite_tree(item)


def no_redirect(path):
    for part in (path, *path.parents):
        if part.exists():
            require(not part.is_symlink() and not (getattr(part.lstat(), "st_file_attributes", 0) & 0x400), "Redirected path")


def read_inputs(source):
    values, fingerprints = {}, {}
    for name in NAMES:
        path = source / name
        no_redirect(path)
        require(path.is_file() and path.stat().st_size <= 32 * 2**20, "Missing or oversized safe export")
        raw = path.read_bytes()
        def unique_pairs(items):
            out = {}
            for key, value in items:
                require(key not in out, "Duplicate JSON key")
                out[key] = value
            return out
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
        require(isinstance(value, dict), "Safe export must be an object")
        finite_tree(value)
        values[name] = value
        fingerprints[name] = dict(sha256=digest(raw), size_bytes=len(raw))
    return values, fingerprints


def clean_score(metric):
    result = {key: number(metric[key], 0, 1 if key != "MAE" else 6)
              for key in ("Accuracy", "macro_F1", "MAE")}
    pearson, reason = metric["Pearson"], metric["Pearson_reason"]
    if pearson is None:
        require(reason in PEARSON_REASONS, "Null Pearson needs its recorded reason")
    else:
        number(pearson, -1 - 1e-12, 1 + 1e-12)
        require(reason is None, "Finite Pearson cannot have a null-reason code")
    result.update(Pearson=pearson, Pearson_reason=reason)
    return result


def aggregate(seeds, objective):
    if set(seeds) != set(SEEDS):
        return None
    out = {}
    for key, high in (("macro_F1", 1), ("MAE", 6)):
        vals = [number(seeds[s][objective][key], 0, high) for s in SEEDS]
        out[key] = dict(mean=math.fsum(vals) / 3, seed_sd_ddof1=statistics.stdev(vals))
    return out


def format_metric(value):
    return "—" if value is None else f"{number(value):.6f}"


def fmt_pair(score, key):
    return "—" if score is None else format_metric(score[key]["mean"]) + " ± " + format_metric(score[key]["seed_sd_ddof1"])


def collect(values):
    summary, fits_payload = values["SUMMARY.json"], values["FITS.json"]
    config_payload, choice = values["CONFIGURATION_SUMMARY.json"], values["BASELINE_AND_SELECTION.json"]
    require(summary["S01_EXECUTION_STATUS"] in ("COMPLETED", "FAILED", "PARTIAL_RESOURCE_STOP"), "Campaign must have exited")
    require(summary["data_kind"] in ("OFFICIAL_TRAIN_VALID", "SYNTHETIC_TEST_FIXTURE"), "Wrong evidence scope")
    for key in ("TEST_USED_FOR_SELECTION", "ATTACHMENT3_4_INSPECTED"):
        require(summary[key] == "NO", "Unauthorized evaluation scope")
    require(summary["ATTACHMENT3_MASK_AVAILABILITY"] == "UNKNOWN", "Special mask conclusion changed")
    budget = integer(summary["EXECUTION_FIT_BUDGET"])
    require(budget in (24, 30) and summary["REGISTERED_FITS"] == fits_payload["registered_fits"] == 39, "Finite budget mismatch")
    binding = summary["authorization"]
    campaign = binding["campaign_id"]
    require(isinstance(campaign, str) and re.fullmatch(r"S01-[A-Za-z0-9-]{8,100}", campaign), "Unsafe campaign name")
    require(campaign == fits_payload["campaign_id"] == choice["campaign_id"], "Campaign mismatch")
    for key, length in (("code_commit", 40), ("execution_config_sha256", 64), ("authorized_manifest_sha256", 64)):
        hash_value(binding[key], length)
    require(binding["execution_fit_budget"] == budget, "Authorization budget mismatch")
    number(summary["runtime_seconds"], 0)
    fits = fits_payload["fits"]
    require(len(fits) == len({r["trial_id"] for r in fits}) == 39, "Exact39 fits required")
    expected_identities = {(a, n, s) for a in BASE_ARCHS for n in NORMALIZERS for s in SEEDS} | {
        (a, "common_preselected", s) for a in ("C0", "R0", "R1", "R2", "R1-CAP") for s in SEEDS}
    require({(r["architecture"], r["registered_normalizer"], r["seed"]) for r in fits} == expected_identities,
            "Preregistered fit identity set mismatch")
    groups, status_counts = {}, {}
    for row in fits:
        require(re.fullmatch(r"[A-Za-z0-9-]{1,80}", row["trial_id"]), "Unsafe trial name")
        require(row["architecture"] in BASE_ARCHS + ("C0", "R0", "R1", "R2", "R1-CAP") and row["seed"] in SEEDS, "Unknown fit identity")
        status = row["status"]
        require(status in ("NOT_RUN", "RUNNING", "COMPLETED", "FAILED", "RESOURCE_CAP_STOP"), "Unexpected fit status")
        status_counts[status] = status_counts.get(status, 0) + 1
        normalizer = row["normalizer"] or row["registered_normalizer"]
        require(normalizer in NORMALIZERS + ("common_preselected",), "Unknown normalizer")
        cid = row["architecture"] + "-" + normalizer
        groups.setdefault(cid, []).append(row)
        if status == "COMPLETED":
            require(row["normalizer"] in NORMALIZERS, "Completed normalizer unresolved")
            clean_score(row["metrics"]["clean"])
            for key, high in (("macro_F1", 1), ("MAE", 6)):
                number(row["metrics"]["attempted96"][key], 0, high)
            for key in ("checkpoint_sha256", "resolved_config_sha256", "source_sha256"):
                hash_value(row[key])
            hash_value(row["code_commit"], 40)
        else:
            require(row["metrics"] is None, "Incomplete fit cannot supply final metrics")
        if row["architecture"] in ("R1", "R2", "R1-CAP"):
            require(status == "NOT_RUN" and row["selected_for_campaign"] is False, "Deferred architecture executed")
    expected = {"COMPLETED_FITS": status_counts.get("COMPLETED", 0), "FAILED_FITS": status_counts.get("FAILED", 0),
                "RESOURCE_CAP_STOP_FITS": status_counts.get("RESOURCE_CAP_STOP", 0),
                "INCOMPLETE_FITS_WITHOUT_TERMINAL_EVENT": status_counts.get("RUNNING", 0),
                "EXECUTED_FITS": 39 - status_counts.get("NOT_RUN", 0)}
    require(all(integer(summary[k]) == v for k, v in expected.items()), "Summary/fit counts disagree")
    require(sum(row["selected_for_campaign"] is True for row in fits) == budget, "Selected fit count disagrees")
    baseline, selected = choice["baseline"], choice["selection"]
    require(summary["selection"] == selected, "Recorded selections disagree")
    require(summary["S01_EXECUTION_STATUS"] != "COMPLETED" or selected is not None,
            "Completed campaign lacks final selection")
    if baseline is not None:
        require(baseline["common_normalizer"] in NORMALIZERS and baseline["B_star"] in BASE_IDS, "Invalid locked baseline")
        require(summary["COMMON_NORMALIZER"] == baseline["common_normalizer"] and summary["B_STAR"] == baseline["B_star"], "Baseline/summary disagree")
        require(set(baseline["baseline_clean_reports"]) == set(BASE_IDS), "All11 baseline configurations required")
    else:
        require(summary["B_STAR"] is None and summary["COMMON_NORMALIZER"] == "NOT_RESOLVED", "Missing baseline lock")
    records = []
    for cid in BASE_IDS:
        group = groups.get(cid, [])
        completed = {r["seed"]: r["metrics"] for r in group if r["status"] == "COMPLETED"}
        if baseline is not None:
            provided = baseline["baseline_clean_reports"][cid]
            require(set(provided) == {str(s) for s in SEEDS}, "Baseline seed set missing")
            provided = {s: {"clean": provided[str(s)]["clean"]} for s in SEEDS}
            for row in provided.values():
                clean_score(row["clean"])
            if cid.startswith("B-"):
                require(set(completed) == set(SEEDS) and all(completed[s]["clean"] == provided[s]["clean"] for s in SEEDS), "B fit and baseline metrics disagree")
            complete = provided
        else:
            complete = completed
        score = aggregate(complete, "clean")
        status = "COMPLETE_3_SEEDS" if score else "INCOMPLETE_SEED_SET" if any(r["status"] != "NOT_RUN" for r in group) else "NOT_RUN" if cid.startswith("B-") else "NOT_EVALUATED"
        records.append(dict(configuration=cid, block="BASELINE", status=status, completed_seeds=sorted(complete),
                            additional_fits=3 if cid.startswith("B-") else 0, clean=score,
                            attempted96=aggregate(completed, "attempted96") if len(completed) == 3 else None))
    common = baseline["common_normalizer"] if baseline else "common_preselected"
    for architecture in ("C0", "R0", "R1", "R2", "R1-CAP"):
        group = [r for r in fits if r["architecture"] == architecture]
        complete = {r["seed"]: r["metrics"] for r in group if r["status"] == "COMPLETED"}
        require(len(complete) == sum(r["status"] == "COMPLETED" for r in group), "Duplicate completed seed")
        clean = aggregate(complete, "clean")
        attempted = aggregate(complete, "attempted96")
        status = "COMPLETE_3_SEEDS" if clean else "INCOMPLETE_SEED_SET" if any(r["status"] != "NOT_RUN" for r in group) else "NOT_RUN"
        records.append(dict(configuration=architecture + "-" + (common if architecture in ("C0", "R0") else "common_preselected"),
                            block="MECHANISM" if architecture in ("C0", "R0") else "DEFERRED",
                            status=status, completed_seeds=sorted(complete), additional_fits=3,
                            clean=clean, attempted96=attempted))
    expected_configurations = {r["architecture"] + "-" + r["normalizer"] for r in fits if r["status"] == "COMPLETED"}
    supplied_configs = config_payload["configurations"]
    require(len(supplied_configs) == len({r["configuration"] for r in supplied_configs}) and
            {r["configuration"] for r in supplied_configs} == expected_configurations, "Configuration summary set mismatch")
    require(config_payload["aggregation_order"] == ["random_replicate", "equal_weight_nominal_condition", "seed"], "Aggregation order changed")
    for row in supplied_configs:
        ours = next(r for r in records if r["configuration"] == row["configuration"])
        if ours["clean"] is None:
            require(row["mean_metrics"] is None, "Partial seed mean incorrectly reported")
        else:
            for objective in ("clean", "attempted96"):
                for metric in ("macro_F1", "MAE"):
                    for stat in ("mean", "seed_sd_ddof1"):
                        require(math.isclose(number(row["mean_metrics"][objective][metric][stat]),
                                             ours[objective][metric][stat], rel_tol=1e-10, abs_tol=1e-12), "Configuration mean/SD mismatch")
    selected_clean, selected_row, selected_components = None, None, []
    if selected is not None:
        require(summary["S01_EXECUTION_STATUS"] == "COMPLETED" and summary["COMPLETED_FITS"] == budget,
                "Selection supplied for incomplete campaign")
        require(selected["seed"] == 17 and selected["configuration"] in FINAL_IDS and
                selected["reason"] in ("WINNER_FIXED_SEED_GUARD_PASS", "CLEAN_REFERENCE_FALLBACK"), "Invalid final selection")
        cid = selected["configuration"]
        if cid.startswith("LATE-") or cid == "PRIOR":
            require(baseline is not None and cid == baseline["B_star"], "Unbound zero-fit reference selection")
            selected_clean = baseline["baseline_clean_reports"][cid]["17"]["clean"]
            if cid.startswith("LATE-"):
                norm = cid.removeprefix("LATE-")
                selected_components = [r for r in fits if r["seed"] == 17 and r["architecture"] in ("B-T", "B-A", "B-V") and r["normalizer"] == norm and r["status"] == "COMPLETED"]
                require(len(selected_components) == 3, "LATE selected components missing")
        else:
            matching = [r for r in fits if r["status"] == "COMPLETED" and r["seed"] == 17 and r["architecture"] + "-" + r["normalizer"] == cid]
            require(len(matching) == 1, "Selected seed17 fit missing")
            selected_row = matching[0]
            selected_clean = selected_row["metrics"]["clean"]
        clean_score(selected_clean)
    return summary, fits, baseline, selected, records, selected_clean, selected_row, selected_components


def render(source, destination):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    no_redirect(source)
    no_redirect(destination)
    require(not destination.exists() and not destination.resolve().is_relative_to(source.resolve()), "New separate output directory required")
    require(not any((p / ".git").exists() for p in (destination, *destination.parents)), "Output cannot be inside a Git repository")
    values, fingerprints = read_inputs(source)
    summary, fits, baseline, selection, rows, selected_clean, chosen_fit, components = collect(values)
    csv_stream = io.StringIO(newline="")
    fields = ["configuration", "block", "status", "completed_seeds", "additional_fits_in_full_protocol",
              "clean_macro_F1_mean", "clean_macro_F1_seed_sd_ddof1", "clean_MAE_mean", "clean_MAE_seed_sd_ddof1",
              "attempted96_macro_F1_mean", "attempted96_macro_F1_seed_sd_ddof1", "attempted96_MAE_mean", "attempted96_MAE_seed_sd_ddof1"]
    writer = csv.DictWriter(csv_stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        out = {"configuration": row["configuration"], "block": row["block"], "status": row["status"],
               "completed_seeds": ";".join(map(str, row["completed_seeds"])), "additional_fits_in_full_protocol": row["additional_fits"]}
        for objective in ("clean", "attempted96"):
            for metric in ("macro_F1", "MAE"):
                for stat in ("mean", "seed_sd_ddof1"):
                    out[objective + "_" + metric + "_" + stat] = "" if row[objective] is None else format(row[objective][metric][stat], ".17g")
        writer.writerow(out)
    csv_bytes = csv_stream.getvalue().encode("utf-8")
    binding = summary["authorization"]
    runtime = summary["runtime_seconds"]
    lines = ["# S01 有限实验执行结果", ""]
    if summary["data_kind"] == "SYNTHETIC_TEST_FIXTURE":
        lines += ["**仅合成渲染测试夹具；下列数字不是比赛实验结果。**", ""]
    lines += [f"状态：**{summary['S01_EXECUTION_STATUS']}**。预先选择 {summary['EXECUTION_FIT_BUDGET']} fits；已启动 {summary['EXECUTED_FITS']}、完成 {summary['COMPLETED_FITS']}、失败 {summary['FAILED_FITS']}、资源停止 {summary['RESOURCE_CAP_STOP_FITS']}、缺少终止事件 {summary['INCOMPLETE_FITS_WITHOUT_TERMINAL_EVENT']}。保留全部 39 项预注册记录。",
              f"实际总耗时：{runtime:.3f} 秒（{runtime / 3600:.3f} 小时）。该数字来自最终安全导出，不是预计完成时间。",
              f"公共 normalizer：**{summary['COMMON_NORMALIZER']}**；已锁定 clean 参考 B*：**{summary['B_STAR'] or 'NOT_LOCKED'}**。",
              "渲染器只展示已有选择记录并复核描述性均值/标准差，没有重新排序、选模型、挑 seed 或读取训练数据。", "",
              "## 已记录的最终模型", ""]
    if selection is None:
        lines += ["**没有完整、已锁定的最终模型选择。** 部分结果不能冒充完成方案；缺少指标保留为空，也不自动挑选当前最好模型。", ""]
    else:
        reason = "获胜配置的固定 seed17 clean 守卫通过" if selection["reason"] == "WINNER_FIXED_SEED_GUARD_PASS" else "固定 seed17 clean 守卫未通过，按协议回退 B* seed17"
        lines += [f"配置：**{selection['configuration']}**；固定 seed：**17**。记录理由：{reason}。", "",
                  "| clean VALID 指标 | seed17 实际记录 |", "|---|---:|"]
        for key in ("Accuracy", "macro_F1", "MAE", "Pearson"):
            value = selected_clean[key]
            text = "null（" + selected_clean["Pearson_reason"] + "）" if key == "Pearson" and value is None else format_metric(value)
            lines.append(f"| {key} | {text} |")
        lines += ["", "Pearson 为 null 时保留原因，不能填 0。以上是已选 seed17 的指标，不是三 seed 均值，也不是 ensemble 指标。", ""]
        if chosen_fit:
            lines += [f"选中 epoch：{integer(chosen_fit['selected_epoch'], 1)}；已评价 epoch：{integer(chosen_fit['evaluated_epochs'], 1)}。",
                      f"checkpoint SHA256：`{chosen_fit['checkpoint_sha256']}`。",
                      f"该 fit 已解析配置 SHA256：`{chosen_fit['resolved_config_sha256']}`。", ""]
        elif components:
            lines += ["LATE 复用三个单模态 seed17 checkpoint，没有新增训练 fit。", "", "| 组件 | checkpoint SHA256 |", "|---|---|"]
            lines += [f"| {r['architecture']} | `{r['checkpoint_sha256']}` |" for r in components]
            lines.append("")
        else:
            lines += ["PRIOR 是 train 先验/中位数常数参考，没有可训练模型 checkpoint；不虚构权重文件或新增 fit。", ""]
    lines += ["## Clean 基线比较", "", "| 配置 | 状态 / 完成 seed 数 | macro-F1 均值 ± SD | MAE 均值 ± SD |", "|---|---|---:|---:|"]
    for row in rows[:11]:
        lines.append(f"| {row['configuration']} | {row['status']} / {len(row['completed_seeds'])} | {fmt_pair(row['clean'], 'macro_F1')} | {fmt_pair(row['clean'], 'MAE')} |")
    lines += ["", "8 个 B 配置各用预先指定的 17/29/43 三 seed；2 个 LATE 配置复用同 normalizer、同 seed 的单模态模型。PRIOR 的三个记录是同一确定性统计参考，重复记录产生的 SD 不代表独立训练稳定性。未齐全三 seed 时不计算部分均值来替代完整结果。", "",
              "## C0 / R0 连续局部缺失比较", "", "| 配置 | 状态 / 完成 seed 数 | clean F1 ± SD | clean MAE ± SD | attempted96 F1 ± SD | attempted96 MAE ± SD |", "|---|---|---:|---:|---:|---:|"]
    for row in rows[11:13]:
        lines.append(f"| {row['configuration']} | {row['status']} / {len(row['completed_seeds'])} | {fmt_pair(row['clean'], 'macro_F1')} | {fmt_pair(row['clean'], 'MAE')} | {fmt_pair(row['attempted96'], 'macro_F1')} | {fmt_pair(row['attempted96'], 'MAE')} |")
    c0, r0 = rows[11:13]
    if c0["clean"] is not None and r0["clean"] is not None:
        lines += ["", "以下差值固定为 R0 − C0，仅作描述；F1 越高越好，MAE 越低越好。负增益同样保留，不追加模型或搜索幸运 seed。", "", "| 评价条件 | Δmacro-F1 | ΔMAE |", "|---|---:|---:|"]
        for objective in ("clean", "attempted96"):
            lines.append(f"| {objective} | {r0[objective]['macro_F1']['mean'] - c0[objective]['macro_F1']['mean']:+.6f} | {r0[objective]['MAE']['mean'] - c0[objective]['MAE']['mean']:+.6f} |")
    else:
        lines += ["", "C0/R0 尚未同时完成三个预指定 seed，因此不报告两者完整比较或缺失增强效果结论。"]
    lines += ["", "SD 为三个 seed 的样本标准差（ddof=1），不是置信区间或显著性检验。attempted96 先按每个随机条件的 replicate 求均值，再对 96 个名义条件等权平均，最后跨 seed 汇总；144 视图不是 144 个独立样本。无合法窗口使用 CLEAN_ONCE，不删除样本。", "",
              "## 执行范围与未运行项", "",
              "本轮上限为预先授权的 30 fits（B24 + C0/R0 各3）；若执行前锁定 24-fit 降级，则仅 B24，不能声称完成增强机制比较。冻结核心总表仍为 39 fits。R1、R2、R1-CAP 合计 9 fits 继续 NOT_RUN，指标为空；不得写成时序或门控优越性的消融证据。D/T/L、KD、重建、cross-attention、ensemble、unaligned、TAV-local、66-fit 扩展均未纳入。", "",
              "FAILED、RESOURCE_CAP_STOP、缺终止事件及 NOT_RUN 均保留在 FITS.json；不只展示最佳 seed 或成功尝试。本报告不授权重试、继续训练、test 或专项推理。", "",
              "## 数据隔离及论文解释边界", "",
              "仅 train 学习参数和归一化统计；VALID 用于 checkpoint、normalizer、配置和最终守卫选择。重复使用同一 VALID 会带来选择乐观偏差，普通 bootstrap 或三 seed SD 不能消除；本报告不作显著性或无偏泛化结论。test 未用于选择，Attachment3/4 未检查。",
              "结果条件为 KNOWN_AVAILABILITY 人工连续缺失模拟。可靠专项 mask availability 仍为 UNKNOWN；natural structural-zero 不自动等于 artificial missing。窗口比例是 supported 坐标上的位置比例，不能换写成秒级时长；未验证真实时间映射。主 96 条件只覆盖已注册的单/双模态共同窗口，不补写 TAV-local 或 Q3 结论。", "",
              "## 来源与复现指纹", "",
              f"campaign：`{binding['campaign_id']}`；协议：`R01-FREEZE-01`。",
              f"实际执行代码 commit：`{binding['code_commit']}`。",
              f"执行配置 SHA256：`{binding['execution_config_sha256']}`。",
              f"授权执行 manifest SHA256：`{binding['authorized_manifest_sha256']}`。"]
    source_evidence = summary.get("source_verification")
    if source_evidence is not None:
        lines += [f"官方输入整体 SHA256：`{hash_value(source_evidence['sha256'])}`；来源是安全导出，本渲染器没有重读原数据。"]
    else:
        lines += ["源数据核验记录缺失；不推断数据已成功加载。"]
    lines += ["每个已完成 fit 的源码、预注册/已解析配置、checkpoint 和证据哈希均保留在 FITS.json；checkpoint 本体、原始数据、样本行和私有路径不进入报告。", "",
              "| 本次只读输入 | SHA256 | 字节数 |", "|---|---|---:|"]
    for name in NAMES:
        lines.append(f"| {name} | `{fingerprints[name]['sha256']}` | {fingerprints[name]['size_bytes']} |")
    lines += ["", f"CONFIGURATION_TABLE.csv SHA256：`{digest(csv_bytes)}`。",
              "Markdown 指标显示到小数点后6位；CSV 保留17位有效数字，原 JSON 为完整事实依据。", "",
              "离线报告重现命令（不训练）：", "", "```text",
              "python -B -X utf8 render_results_report.py --input-dir SAFE_EXPORTED_JSON_DIRECTORY --output-dir NEW_EXTERNAL_REPORT_DIRECTORY", "```", "",
              "正式训练命令仅作接口记录，以下占位符不能作为执行授权；本次一次性 campaign 已消费，任何重跑须另行取得未来授权：", "", "```text",
              "python -B -X utf8 tools/s01_train.py official --source AUTHORIZED_ALIGNED_SOURCE --output-dir NEW_AUTHORIZED_PRIVATE_DIRECTORY", "```", ""]
    md_bytes = "\n".join(lines).encode("utf-8")
    require(not re.search(rb"[A-Za-z]:[\\/]", md_bytes) and not re.search(rb"(?:/Users/|/home/)", md_bytes), "Private absolute path in rendered report")
    destination.mkdir(parents=True)
    for name, raw in (("RESULTS.md", md_bytes), ("CONFIGURATION_TABLE.csv", csv_bytes)):
        with (destination / name).open("xb") as stream:
            stream.write(raw)
    return dict(status="RENDERED_SAFE_AGGREGATE_REPORT", configuration_rows=len(rows), selection_recomputed=False,
                campaign_status=summary["S01_EXECUTION_STATUS"], files=[dict(path=name, sha256=digest(raw), size_bytes=len(raw))
                for name, raw in (("RESULTS.md", md_bytes), ("CONFIGURATION_TABLE.csv", csv_bytes))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        result = render(args.input_dir, args.output_dir)
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps(dict(status="RENDER_REJECTED", exception_type=type(exc).__name__, detail_sha256=digest(str(exc).encode()))))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
