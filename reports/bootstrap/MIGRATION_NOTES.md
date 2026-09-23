# Selective migration

The old `E` workspace is a source only. The official repository is a fresh clone of the verified remote `main` at `50cd572e47274903b43230dcd3add65f34447c84`. Its `.git` directory was never copied.

`MIGRATION_INVENTORY.csv` records each inspected candidate by repository-relative path, disposition, and risk flag. Two small engineering sources (`pyproject.toml` and `src/mosei/provenance.py`) were copied after text scanning. Six governance files were rebuilt for the current task. Earlier stage plans, models, tests, flow wrappers, and reports were left in the old workspace. The existing competition DOCX arrived through the clean clone. Original data directories were listed by name only and were never copied or opened. Local path configuration was excluded. Binary candidates were not silently migrated.

The baseline source has earlier tracked raw data; this fresh remote clone has zero raw-data paths in its index, history path listing, and reachable object path listing. The old workspace remains untouched.
