import numpy as np

from ml.metrics import segmented_mae


def test_segmented_mae_splits_by_minutes():
    actual = [10, 0, 5, 0]
    predicted = [8, 1, 3, 2]
    minutes = [90, 0, 45, 0]
    result = segmented_mae(actual, predicted, minutes)

    assert result["mae"] == np.mean([2, 1, 2, 2])
    assert result["played_mae"] == np.mean([2, 2])  # rows 0 and 2
    assert result["unplayed_mae"] == np.mean([1, 2])  # rows 1 and 3
    assert result["played_rows"] == 2
    assert result["unplayed_rows"] == 2


def test_segmented_mae_all_played_returns_none_for_unplayed():
    result = segmented_mae([5, 3], [4, 3], [90, 45])

    assert result["unplayed_mae"] is None
    assert result["unplayed_rows"] == 0
    assert result["played_mae"] == result["mae"]


def test_segmented_mae_all_unplayed_returns_none_for_played():
    result = segmented_mae([0, 0], [1, 2], [0, 0])

    assert result["played_mae"] is None
    assert result["played_rows"] == 0


def test_segmented_mae_empty_input_returns_none():
    result = segmented_mae([], [], [])

    assert result == {
        "mae": None,
        "played_mae": None,
        "unplayed_mae": None,
        "played_rows": 0,
        "unplayed_rows": 0,
    }
