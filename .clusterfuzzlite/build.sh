#!/bin/bash
set -eu
pyinstaller --distpath "$OUT" --workpath /tmp/evaluator-pyinstaller --onefile \
  --paths "$SRC/evaluator" --paths "$SRC/evaluator/fuzz" \
  --add-data "$SRC/evaluator/schemas:schemas" \
  --name composer_fuzzer.pkg "$SRC/evaluator/fuzz/composer_fuzzer.py"
cat > "$OUT/composer_fuzzer" <<'EOF'
#!/bin/sh
# LLVMFuzzerTestOneInput: Atheris entry point for ClusterFuzzLite detection.
this_dir=$(dirname "$0")
exec "$this_dir/composer_fuzzer.pkg" "$@"
EOF
chmod +x "$OUT/composer_fuzzer"
cp "$SRC/evaluator/fuzz/composer_fuzzer.options" "$OUT/composer_fuzzer.options"
python3 - "$SRC/evaluator/fuzz/corpus" "$OUT/composer_fuzzer_seed_corpus.zip" <<'PY'
import pathlib
import sys
import zipfile
with zipfile.ZipFile(sys.argv[2], "w") as archive:
    for seed in pathlib.Path(sys.argv[1]).iterdir():
        archive.write(seed, seed.name)
PY
