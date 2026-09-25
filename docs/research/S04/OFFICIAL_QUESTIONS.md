# Official information needed for special delivery

## S04-CLARIFY-02 update, 2026-09-25

The original questions below are retained as historical evidence. Three user-supplied screenshots of contest replies permit an aligned-only formal submission, Attachment3 text-feature extraction as preprocessing, and a reproducible evidence-backed estimated material mapping. They do not identify the original encoder checkpoint or missing-token treatment and do not provide official word timestamps. Screenshot SHA256 values are recorded in `CLARIFY_02_CLOSEOUT.md`; the original posting URL/date were not independently verified.

The remaining Attachment3 question is precise: do the 131 in-support ID-100 positions among the 30 aligned records denote artificial text corruption, and what exact encoder/checkpoint/layer plus order of corruption and embedding generated the expected continuous 50×768 text? The clean TRAIN/VALID replay matches numerically but does not validate the corrupted-token interface. A new common TRAIN/VALID/special pipeline and independently authorized M2-E1 training would be required if original semantics cannot be established; old M2 metrics would not transfer.

Attachment4 no longer waits exclusively for an official timing sidecar. Exact token-to-text replay and checked acoustic estimates support 12/20 aligned records; eight retain text positions only. The official audio/vision feature extraction-to-PTS correspondence and human word-time accuracy remain unknown. No estimated interval is called official truth.

## Attachment3

The 30 official aligned PKLs each contain a sole `test` wrapper whose children are `audio`, `vision`, and `text_bert`. No file contains the 50×768 continuous `text` vectors required by the frozen aligned predictor. The previous inference stopped at the first such file before producing predictions.

1. Is a separate official file or documented field containing the **continuous aligned text features** for these same 30 records available? Please provide its exact filename, shape, source association and order.
2. If the omission is intentional, what is the official expected prediction interface for missing text when a model was trained with continuous text input? We cannot derive that input from the stored float32 3×50 `text_bert` container or uncorrupted samples; its contents have not been interpreted in this structural audit.
3. Please document whether `text_bert` channel 1 in these PKLs retains the same supported-position definition as Attachment2, including dtype and 0/1 conventions.
4. Please confirm whether the aligned and unaligned versions represent the same 30 records and which version is required for official Q2 output. The frozen model accepts aligned only.

No model, threshold, mask meaning or imputation rule was changed after inspecting these structures. The Attachment3 branch is stopped as REQUIRES_OFFICIAL_SCHEMA_CLARIFICATION.

## Attachment4 source mapping

The local Attachment4 inventory has 20 aligned and 20 unaligned feature PKLs, paired with 40 MP4 paths but only 20 unique filename stems. The aligned objects hold continuous text/audio/vision and `text_bert`, plus ID/raw_text, but the inspected structure has no timing sidecar or token-to-video mapping fields.

Please supply the official aligned-feature generation pipeline or a per-record mapping from the 50 model positions (including BERT special tokens, truncation/padding rules) to source text/audio/video time intervals or frame IDs, with video start-offset and variable-frame-rate handling. A matching filename or length alone cannot establish this coordinate mapping. Until verified, we can report feature indices and null timestamps, not source-time evidence.
