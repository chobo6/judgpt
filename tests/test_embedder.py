import pytest

from judgpt.embedder import FakeEmbedder, cosine_similarity


def test_fake_embedder_returns_prepared_vector():
    embedder = FakeEmbedder({"안녕": [1.0, 0.0]})
    assert embedder.embed("안녕") == [1.0, 0.0]


def test_fake_embedder_raises_for_unprepared_text():
    embedder = FakeEmbedder({})
    with pytest.raises(AssertionError):
        embedder.embed("모르는 텍스트")


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_negative_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_handles_zero_vector_without_crashing():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
