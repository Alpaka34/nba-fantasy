"""Ligden bağımsız sayfalarda kullanılan standart fantasy puanlaması.

Her ligin kendi puanlama ayarı vardır. Ligden bağımsız "kim kaç puan aldı"
sorusu için Yahoo'nun varsayılan puanlı lig ayarlarını kullanıyoruz.
"""

DEFAULT_POINTS = {
    "pts": 1.0,
    "reb": 1.2,
    "ast": 1.5,
    "stl": 3.0,
    "blk": 3.0,
    "tov": -1.0,
}


def fantasy_points(stats: dict, weights: dict = DEFAULT_POINTS) -> float:
    return round(sum(stats.get(k, 0) * w for k, w in weights.items()), 1)
