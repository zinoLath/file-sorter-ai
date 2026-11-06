import pytest

from core.budget import BudgetError, build_budget, check_budget, estimate_tokens


class FakeTokenizer:
    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": list(range(len(text.split()) * 2))}


def test_estimate_tokens_is_conservative():
    assert estimate_tokens("uma frase curta") == 5
    assert estimate_tokens("") == 0


def test_check_budget_accepts_short_options():
    check_budget("Escolha a pasta.", {"a": "contas", "b": "fotos"})


def test_check_budget_rejects_option_over_48_tokens():
    with pytest.raises(BudgetError) as error:
        check_budget("Escolha.", {"a": "palavra " * 40})
    assert error.value.option == "a"


def test_check_budget_rejects_combined_over_512_tokens():
    criteria = {str(index): "palavra " * 18 for index in range(20)}
    with pytest.raises(BudgetError) as error:
        check_budget("Escolha.", criteria)
    assert error.value.option is None


def test_budget_uses_tokenizer_when_available():
    report = build_budget("uma frase", {"a": "duas palavras"}, tokenizer=FakeTokenizer())
    assert report.approximate is False
    assert report.option_tokens["a"] == 4
    assert report.total_tokens > 0


def test_budget_without_tokenizer_is_marked_approximate():
    report = build_budget("uma frase", {"a": "duas palavras"})
    assert report.approximate is True
    assert report.option_tokens["a"] == estimate_tokens("duas palavras")
