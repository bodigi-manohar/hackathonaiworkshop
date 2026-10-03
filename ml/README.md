# ml/ (Member 1) - run in this order, from the repo root

    export GRIDSIGHT_RAW_CSV=/kaggle/input/datasets/manoharbodigi/ausgrid-com25/Ausgrid_Community_Final.csv   # or put the CSV at data/raw/
    python -m ml.data                                                  # Step 2: parquet + reports/data_quality.json + docs/DATA_SCHEMA.md
    python -m ml.run_cycle --origin 2013-02-15T00:00 --model baseline  # Step 3: first contract file (sync S1)
    python -m pytest ml/tests -q                                       # leakage, aggregation, contract tests
    python -m ml.backtest                                              # Step 5: reports/backtest.md, metrics_backtest.json, results.xlsx, docs/RESULTS.md
    python -m ml.train --train-end 2013-02-01                          # final models (origins on/after this day are out-of-sample)
    python -m ml.run_cycle --origin 2013-02-15T00:00                   # Steps 6-7: full run bundle in runs/<run_id>/
    # faster backtest while iterating: python -m ml.backtest --levels portfolio,zone
