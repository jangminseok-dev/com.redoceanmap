import statistics

from game.domain.rng import deterministic as rng


def test_같은_키는_같은_값이다():
    assert rng.u64("ns", "key") == rng.u64("ns", "key")
    assert rng.uniform("ns", "key") == rng.uniform("ns", "key")
    assert rng.normal("ns", "key") == rng.normal("ns", "key")


def test_네임스페이스가_다르면_값이_다르다():
    assert rng.u64("a", "key") != rng.u64("b", "key")


def test_균등난수는_0이상_1미만이다():
    values = [rng.uniform("test", str(i)) for i in range(2_000)]
    assert all(0.0 <= v < 1.0 for v in values)


def test_균등난수의_평균과_분산이_이론값에_가깝다():
    values = [rng.uniform("test", str(i)) for i in range(5_000)]
    assert abs(statistics.fmean(values) - 0.5) < 0.02
    assert abs(statistics.pstdev(values) - (1 / 12) ** 0.5) < 0.02


def test_정규난수의_평균과_표준편차가_이론값에_가깝다():
    values = [rng.normal("test", str(i)) for i in range(5_000)]
    assert abs(statistics.fmean(values)) < 0.05
    assert abs(statistics.pstdev(values) - 1.0) < 0.05
