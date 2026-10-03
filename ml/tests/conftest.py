import pytest

from ml.config import load_config
from ml.synthetic import make_synthetic_csv


@pytest.fixture(scope="session")
def cfg(tmp_path_factory):
    d = tmp_path_factory.mktemp("gs")
    csv = d / "raw.csv"
    make_synthetic_csv(csv, days=130, n_houses=6, n_zones=3)
    c = load_config()
    c["paths"].update(raw_csv=str(csv), processed_dir=str(d / "proc"), runs_dir=str(d / "runs"), models_dir=str(d / "models"),
                      reports_dir=str(d / "reports"), docs_dir=str(d / "docs"), contracts_dir=str(d / "contracts"))
    c["backtest"].update(n_folds=2, fold_days=14)
    c["model"]["lgbm"].update(n_estimators=60)
    c["model"]["val_days"] = 7
    c["replay"].update(train_end="2012-10-20", demo_origin="2012-11-05T00:00")
    return c
