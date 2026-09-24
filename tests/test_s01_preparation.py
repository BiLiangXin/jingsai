"""SYNTHETIC_ONLY: mechanics and safety, never competition model performance."""
from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pytest
import torch
from mosei.s01.authorization import AuthorizationError, approval_question, require_official_authority
from mosei.s01.contracts import ARCHITECTURES, MODS, SEEDS, digest, synthetic_batch
from mosei.s01.engine import (evaluate, fit, joint_loss, load_checkpoint, optimizer_step, save_checkpoint,
                              validate_recipe)
from mosei.s01.models import (LateModel, PriorModel, R01Model, parameter_count, prior_statistics)
from mosei.s01.normalization import Normalizer
from mosei.s01.protocol import (CheckpointSelector, ValidationLibrary, final_choice, metric_report,
                                reference, seed_mean, select_normalizer, train_availability)
from mosei.s01.registry import EventRegistry, preregister, recipe, validate_preregistration

torch.set_num_threads(2)


@pytest.mark.parametrize("architecture", ARCHITECTURES)
def test_dual_heads_shapes_loss_backward_and_safe_masks(architecture):
    batch = synthetic_batch(3)
    model = R01Model(architecture)
    result = model(batch.inputs())
    assert result["logits"].shape == (3, 3)
    assert result["regression"].shape == (3,)
    assert torch.isfinite(joint_loss(result, batch))
    joint_loss(result, batch).backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
    changed = copy.deepcopy(batch)
    for m in MODS:
        changed.features[m][~changed.observed[m]] = float("nan")
    masked = model(changed.inputs())
    assert torch.equal(masked["logits"], result["logits"])
    assert torch.equal(masked["regression"], result["regression"])
    for m in MODS:
        changed.features[m][~changed.observed[m]] = 1e30
    assert torch.equal(model(changed.inputs())["logits"], result["logits"])
    bad = copy.deepcopy(batch)
    bad.features["text"][0, 0, 0] = float("nan")
    with pytest.raises(ValueError, match="Active nonfinite"):
        model(bad.inputs())


@pytest.mark.parametrize("architecture", ARCHITECTURES)
def test_init_seed_determinism_and_actual_parameter_counts(architecture):
    expected = dict(zip(ARCHITECTURES, (49476, 5060, 2564, 56452, 56604, 56604, 93660, 98012, 97932)))
    a, b = R01Model(architecture, 29), R01Model(architecture, 29)
    assert parameter_count(a) == expected[architecture]
    assert all(torch.equal(a.state_dict()[k], v) for k, v in b.state_dict().items())


def test_matched_encoder_and_head_initialization():
    a, b = R01Model("C0"), R01Model("R0")
    assert all(torch.equal(a.state_dict()[k], v) for k, v in b.state_dict().items())
    base = R01Model("R1").state_dict()
    for architecture in ("R2", "R1-CAP"):
        other = R01Model(architecture).state_dict()
        assert all(torch.equal(v, other[k]) for k, v in base.items())


def test_partial_convolution_formula():
    batch = synthetic_batch(1, dense=True)
    active = {m: torch.zeros_like(batch.support) for m in MODS}
    active["text"][0, :3] = True
    active["text"][0, 1] = False
    model = R01Model("R1")
    for p in model.parameters():
        p.data.zero_()
    model.projections["text"].weight.data[0, 0] = 1
    model.convolutions["text"].weight.data[0, 0, :] = 1
    batch.features["text"][0, 0, 0] = 2
    batch.features["text"][0, 2, 0] = 6
    observed_h = []
    hook = model.classifier.register_forward_pre_hook(lambda module, args: observed_h.append(args[0].detach()))
    model(batch.inputs(active))
    hook.remove()
    assert observed_h[0][0, 0] == 4  # two isolated active centers, each k_t=1
    assert torch.allclose(observed_h[0][0, 64:], torch.tensor([1., 0., 0., 2/50, 0., 0.]))


@pytest.mark.parametrize("architecture", ("C0", "R0", "R1", "R2", "R1-CAP"))
def test_all_empty_available_is_finite_train_prior(architecture):
    batch = synthetic_batch(2)
    model = R01Model(architecture, prior=(.2, .3, .5), median=.4)
    active = {m: torch.zeros_like(batch.support) for m in MODS}
    result = model(batch.inputs(active))
    assert torch.allclose(result["logits"].softmax(1), torch.tensor([[.2, .3, .5]]).expand(2, 3))
    assert torch.allclose(result["regression"], torch.full((2,), .4))


def test_predictor_allowlist_and_subset_fail_closed():
    batch = synthetic_batch(2)
    model = R01Model("B-CAT")
    for key in ("label", "ID", "raw_text", "split", "token_ID"):
        with pytest.raises(ValueError, match="allowlist"):
            model(dict(batch.inputs(), **{key: "forbidden"}))
    inputs = copy.deepcopy(batch.inputs())
    inputs["available"]["text"][0, 49] = True
    inputs["support"][0, 49] = False
    with pytest.raises(ValueError):
        model(inputs)


@pytest.mark.parametrize("method", ("identity", "zscore"))
def test_train_only_normalizer_and_state_roundtrip(method):
    batch = synthetic_batch(4)
    original = copy.deepcopy(batch)
    for split in ("valid", "test", "attachment3", "attachment4"):
        with pytest.raises(ValueError, match="TRAIN"):
            Normalizer(method).fit([batch], split=split)
    normalizer = Normalizer(method).fit([batch], split="train")
    transformed = normalizer.transform(batch)
    restored = Normalizer.from_state_dict(normalizer.state_dict()).transform(batch)
    for m in MODS:
        assert torch.equal(batch.features[m], original.features[m])
        assert torch.equal(transformed.observed[m], original.observed[m])
        assert torch.equal(transformed.features[m], restored.features[m])
        if method == "zscore":
            active = transformed.features[m][transformed.observed[m]].double()
            assert active.mean(0).abs().max() < 1e-6
            assert torch.allclose(active.var(0, unbiased=False), torch.ones(active.shape[1], dtype=torch.float64), atol=1e-6)


def test_normalization_constant_feature_does_not_reclassify_structural_zero():
    batch = synthetic_batch(3)
    batch.features["audio"][batch.observed["audio"]] = 5
    normalized = Normalizer("zscore").fit([batch], split="train").transform(batch)
    assert normalized.features["audio"][normalized.observed["audio"]].eq(0).all()
    assert torch.equal(normalized.observed["audio"], batch.observed["audio"])


def test_loss_fixed_ce_mae_strict_classes_and_large_shift():
    batch = synthetic_batch(3)
    out = dict(logits=torch.full((3, 3), 1e20), regression=torch.zeros(3))
    assert math.isclose(float(joint_loss(out, batch)), math.log(3) + 2/9, rel_tol=1e-6)
    batch.values[1] = 1e-12
    with pytest.raises(ValueError, match="neutral"):
        joint_loss(out, batch)


def test_fixed_three_classes_and_pearson_null():
    score = reference.metrics([2], [1.], [2], [1.])
    assert score["macro_F1"] == 1/3
    assert score["Pearson"] is None and score["Pearson_reason"] == "insufficient_n"
    assert reference.pearson([0., 0.], [0., 1.]) == (None, "zero_target_variance")
    assert reference.pearson([-1., 1.], [0., 0.]) == (None, "zero_prediction_variance")


def test_mask_key_exact_reference_pairing_96_144_and_clean_once():
    batch = synthetic_batch(3, dense=True)
    first, info = train_availability(batch, 17, 2)
    second, _ = train_availability(batch, 17, 2)
    assert all(torch.equal(first[m], second[m]) for m in MODS)
    for i in range(3):
        draw = reference.train_attempt(batch.support[i].tolist(), {s: batch.observed[m][i].tolist()
                     for m, s in zip(MODS, ("T", "A", "V"))}, 17, 2, i)
        assert all(first[m][i].tolist() == draw["A"][s] for m, s in zip(MODS, ("T", "A", "V")))
    batch.support[:, 1:] = False
    for m in MODS:
        batch.observed[m] = batch.support.clone()
    library = ValidationLibrary(batch)
    assert len(library.views) == 96 and sum(map(len, library.views.values())) == 144
    for views in library.views.values():
        for view in views:
            assert view["eligible"] == [False] * 3
            assert all(torch.equal(view["available"][m], batch.observed[m]) for m in MODS)
    model = R01Model("R0")
    with patch.object(model, "forward", wraps=model.forward) as forward:
        score = evaluate(model, batch, seed=17, library=library)
        assert forward.call_count == 1
    assert score["attempted96"]["MAE"] == score["clean"]["MAE"]


def test_real_tensor_eligibility_reports_and_equal_repeat_weight():
    batch = synthetic_batch(3, dense=True)
    library = ValidationLibrary(batch)
    scores = evaluate(R01Model("R1"), batch, seed=29, library=library)
    grid = {s: copy.deepcopy(scores["condition_reports"]) for s in SEEDS}
    for reports in grid.values():
        for cid, repeats in reports.items():
            for r in repeats:
                r["attempted"]["macro_F1"] = 1. if cid.endswith("random") else 0.
    assert reference.aggregate(grid)["across_seeds"]["macro_F1"] == .25
    grid[43]["T:0.1:random"][1]["pairing"]["view"] = "f" * 64
    with pytest.raises(ValueError, match="corruption view"):
        reference.aggregate(grid)


def test_checkpoint_tiny_progress_tie_early_stop_and_baseline_objective():
    selector = CheckpointSelector()
    assert selector.update(.5, 1)["save"]
    assert selector.update(.50001, 1)["save"]
    for _ in range(8):
        assert not selector.update(.50001, 1)["stop"]
    last = selector.update(.50001, 1)
    assert last["stop"] and last["best_epoch"] == 2
    assert recipe("C0", "identity", 17)["checkpoint_objective"] == "attempted96"
    assert recipe("B-T", "identity", 17)["checkpoint_objective"] == "clean"


def test_normalizer_three_seed_tie_and_missing_seed_rejection():
    rows = {s: dict(macro_F1=.5, MAE=1.) for s in SEEDS}
    assert select_normalizer(dict(identity=rows, zscore=rows)) == "identity"
    zscore = copy.deepcopy(rows); zscore[43]["macro_F1"] += .1
    assert select_normalizer(dict(identity=rows, zscore=zscore)) == "zscore"
    with pytest.raises(ValueError):
        seed_mean({17: rows[17]})


def test_final_seed_guard_no_runner_up_or_lucky_seed():
    def records(clean_fs):
        output = {}
        for s, f in zip(SEEDS, clean_fs):
            grid = {reference.condition_id(c): [dict(attempted=dict(macro_F1=.9, MAE=.4, n=1),
                    eligible_count=1, total_count=1, pairing=reference.pairing_stamp([0], [True], str(rep)*64, rep))
                    for rep in range(3 if c[2] == "random" else 1)] for c in reference.conditions()}
            output[s] = dict(clean=dict(macro_F1=f, MAE=.5), condition_reports=grid,
                             attempted96=reference.checkpoint_score(grid, s), parameters=10)
        return output
    configs = {"B*": records([.8]*3), "winner": records([.6, .9, .9]), "runner_up": records([.8]*3)}
    for r in configs["runner_up"].values():
        for repeats in r["condition_reports"].values():
            for report in repeats:
                report["attempted"]["macro_F1"] = .8
        r["attempted96"] = reference.checkpoint_score(r["condition_reports"])
    assert final_choice(configs, "B*")["configuration"] == "B*"
    assert final_choice(configs, "B*")["seed"] == 17


def test_checkpoint_actual_save_restore_and_provenance(tmp_path):
    batch = synthetic_batch(4)
    norm = Normalizer("identity").fit([batch], split="train")
    cfg = recipe("R2", "identity", 17)
    model = R01Model("R2")
    opt = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    optimizer_step(model, opt, batch)
    before = model(batch.inputs())["logits"].detach().clone()
    checkpoint = tmp_path / "synthetic.pt"
    save_checkpoint(checkpoint, model, opt, norm, epoch=1, trace=[(.4, 1.)], config=cfg,
                    provenance={"synthetic": True})
    optimizer_step(model, opt, batch)
    load_checkpoint(checkpoint, model, opt, config=cfg, provenance={"synthetic": True})
    assert torch.equal(before, model(batch.inputs())["logits"])
    with pytest.raises(ValueError, match="provenance"):
        load_checkpoint(checkpoint, model, opt, config=cfg, provenance={"synthetic": False})


def test_synthetic_one_epoch_fit_checkpoint_and_repeat_determinism(tmp_path):
    train, valid = synthetic_batch(4, 17), synthetic_batch(3, 29)
    norm = Normalizer("identity").fit([train], split="train")
    cfg = recipe("B-CAT", "identity", 17)
    model, result = fit(train, valid, norm, cfg, output_dir=tmp_path / "first", provenance={"synthetic": True}, data_kind="SYNTHETIC_ONLY")
    other, other_result = fit(train, valid, norm, cfg, output_dir=tmp_path / "second", provenance={"synthetic": True}, data_kind="SYNTHETIC_ONLY")
    assert result["selected_epoch"] == other_result["selected_epoch"] == 1
    assert all(torch.equal(v, other.state_dict()[k]) for k, v in model.state_dict().items())


def test_prior_late_reuse_empty_fallback_and_midpoint_median():
    batch = synthetic_batch(2)
    prior, median = prior_statistics(batch, split="train")
    assert median == -.5
    late = LateModel({m: R01Model(a) for m, a in zip(MODS, ("B-T", "B-A", "B-V"))}, prior, median)
    assert parameter_count(late) == sum(parameter_count(x) for x in late.components.values())
    empty = {m: torch.zeros_like(batch.support) for m in MODS}
    output = late(batch.inputs(empty))
    assert torch.allclose(output["logits"].softmax(1), torch.tensor(prior).expand(2, 3))
    assert output["regression"].eq(median).all()
    assert parameter_count(PriorModel(prior, median)) == 0


def test_preregistered_39_full_fields_and_optional_rejection():
    records = preregister()
    validate_preregistration(records)
    assert len(records) == 39 and all(r["metrics"] is None and r["status"] == "NOT_RUN" for r in records)
    assert all(r["config_hash"] == digest(r["config"]) for r in records)
    bad = copy.deepcopy(records); bad[0]["architecture"] = "D-MASK"
    with pytest.raises(ValueError):
        validate_preregistration(bad)
    for key, value in (("loss", "Huber"), ("architecture", "KD"), ("batch_size", 64), ("recipe", "T1")):
        with pytest.raises(ValueError):
            validate_recipe(dict(recipe("R1", "identity", 17), **{key: value}))


def test_event_ledger_preserves_failure_no_retry(tmp_path):
    records = preregister(); path = tmp_path / "events.jsonl"
    log = EventRegistry(path, records)
    log.event(records[0]["trial_id"], "RUNNING", metrics=None)
    log.event(records[0]["trial_id"], "FAILED", metrics=None, failure_reason="synthetic injected failure")
    with pytest.raises(ValueError, match="retry"):
        log.event(records[0]["trial_id"], "RUNNING")
    assert len(path.read_text().splitlines()) == 2
    with pytest.raises(ValueError, match="overwritten"):
        EventRegistry(path, records)


@pytest.mark.parametrize("split", ("train", "valid", "test", "attachment3", "attachment4"))
def test_authorization_default_rejects_before_io(split):
    with patch("pathlib.Path.open", side_effect=AssertionError("No data/config IO expected")):
        with pytest.raises(AuthorizationError):
            require_official_authority({"training_authorized": False}, split=split)


def test_authorization_true_cli_style_boolean_and_fake_receipt_do_not_grant():
    with pytest.raises(AuthorizationError):
        require_official_authority(dict(training_authorized=True, owner_approved=True), split="train")
    with pytest.raises(AuthorizationError):
        require_official_authority(dict(training_authorized=True), split="valid", optimizer=True)
    binding = dict(task_id="S01_CORE_39_EXECUTION", commit="a"*40, protocol_freeze="R01-FREEZE-01", execution_config_sha256="b"*64)
    assert approval_question(binding) != approval_question(dict(binding, commit="c"*40))


def test_official_loader_rejects_before_source_access(tmp_path):
    from mosei.s01.execution import load_official
    with patch("pathlib.Path.open", side_effect=AssertionError("Source must not be opened")):
        with pytest.raises(AuthorizationError):
            load_official(dict(training_authorized=False), tmp_path / "aligned_50.pkl")


def test_command_has_no_authorization_override_flag(tmp_path):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/s01_train.py"), "official",
                             "--output-dir", str(tmp_path / "out"), "--training-authorized"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2 and "unrecognized arguments" in result.stderr
    assert not (tmp_path / "out").exists()


def test_baseline_clean_checkpoint_final_grid_once(tmp_path):
    batch = synthetic_batch(2, dense=True)
    norm = Normalizer("identity").fit([batch], split="train")
    library = ValidationLibrary(batch)
    import mosei.s01.engine as engine
    with patch.object(engine, "evaluate", wraps=engine.evaluate) as calls:
        fit(batch, batch, norm, recipe("B-CAT", "identity", 17), output_dir=tmp_path / "fit",
            provenance={"synthetic": True}, data_kind="SYNTHETIC_ONLY", library=library)
    assert calls.call_count == 2
    assert calls.call_args_list[0].kwargs["library"] is None
    assert calls.call_args_list[1].kwargs["library"] is library


def test_one_use_campaign_rejects_new_directory_replay(tmp_path):
    from mosei.s01.authorization import claim_campaign
    grant = dict(binding=dict(campaign_id="synthetic-test-only", private_output_sha256="a"*64), owner_event={"synthetic": True})
    with patch("mosei.s01.authorization._claims_root", return_value=tmp_path):
        claim_campaign(grant)
        grant["binding"]["private_output_sha256"] = "b"*64
        with pytest.raises(AuthorizationError, match="already launched"):
            claim_campaign(grant)
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize("budget", (24, 30, 39))
def test_finite_scheduler_and_failure_persistence(tmp_path, budget):
    import contextlib
    import mosei.s01.execution as execution
    cfg = json.loads((ROOT / "configs/s01_execution.json").read_text())
    cfg.update(execution_fit_budget=budget, latest_compute_finish="2099-01-01T00:00:00+08:00")
    batch = synthetic_batch(2)
    score = dict(clean=dict(macro_F1=.3, MAE=1.), parameters=1, checkpoint="private-synthetic")
    fit_calls = []
    def fake_fit(train, valid, norm, trial, **kwargs):
        destination = kwargs["output_dir"]
        destination.mkdir(parents=True)
        fit_calls.append(trial["architecture"])
        return R01Model(trial["architecture"]), copy.deepcopy(score)
    def stack():
        ctx = contextlib.ExitStack()
        ctx.enter_context(patch.object(execution, "require_official_authority", return_value={"synthetic": True}))
        ctx.enter_context(patch.object(execution, "claim_campaign"))
        ctx.enter_context(patch.object(execution, "load_official", return_value=({"train":batch,"valid":batch}, "synthetic")))
        ctx.enter_context(patch.object(execution, "ValidationLibrary", return_value=object()))
        ctx.enter_context(patch.object(execution, "fit", side_effect=fake_fit))
        ctx.enter_context(patch.object(execution, "evaluate", return_value=copy.deepcopy(score)))
        ctx.enter_context(patch.object(execution, "final_choice", return_value={"synthetic": True}))
        return ctx
    with stack():
        execution.execute_core(cfg, "never-opened", tmp_path / "ok", device="cpu")
    assert len(fit_calls) == budget
    if budget == 30:
        assert set(fit_calls) == {"B-T","B-A","B-V","B-CAT","C0","R0"}
    events = [json.loads(x) for x in (tmp_path / "ok/events.jsonl").read_text().splitlines()]
    assert len(events) == budget * 2 and all(e["status"] == "COMPLETED" for e in events[1::2])
    write = execution.write_json
    def broken_write(path, value):
        if path.name == "evaluation.json":
            raise OSError("injected result persistence failure")
        write(path, value)
    with stack(), patch.object(execution, "write_json", side_effect=broken_write):
        with pytest.raises(OSError, match="injected result persistence failure"):
            execution.execute_core(cfg, "never-opened", tmp_path / "fail", device="cpu")
    failed = [json.loads(x) for x in (tmp_path / "fail/events.jsonl").read_text().splitlines()]
    assert [x["status"] for x in failed] == ["RUNNING", "FAILED"]
    assert not list((tmp_path / "fail").rglob("evaluation.json"))


def test_changed_frozen_mask_roots_rejected():
    for k, v in (("train_mask_root", 1), ("valid_mask_root", 1), ("protocol_freeze", "fake")):
        with pytest.raises(ValueError, match="Frozen T0"):
            validate_recipe(dict(recipe("R0", "identity", 17), **{k:v}))


def test_device_and_absolute_deadline_checked_before_owner_io(tmp_path):
    cfg = json.loads((ROOT / "configs/s01_execution.json").read_text())
    cfg.update(training_authorized=True, resource_cap_status="OWNER_APPROVED")
    with patch("mosei.s01.authorization._git", side_effect=AssertionError("must fail before git/owner journal")):
        with pytest.raises(AuthorizationError, match="device"):
            require_official_authority(cfg, split="train", device="cpu", output_dir=tmp_path)
        cfg["latest_compute_finish"] = "2020-01-01T00:00:00+08:00"
        with pytest.raises(AuthorizationError, match="deadline passed"):
            require_official_authority(cfg, split="train", device="cuda", output_dir=tmp_path, launch=True)
