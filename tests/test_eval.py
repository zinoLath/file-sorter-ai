import json

from core.eval import load_gold, run_eval
from core.model import ChoiceAnswer

SCHEMA = """<targets>
  <documentos prompt="Documentos">
    <contas prompt="Contas de água, luz e internet" />
    <contratos prompt="Contratos assinados" />
  </documentos>
  <outros prompt="Diversos" />
</targets>"""


class FakeModel:
    def __init__(self, mapping):
        self.mapping = mapping

    def predict_choices(self, requests):
        answers = []
        for request in requests:
            choice = self.mapping.get(request.state["arquivo"], "outros")
            probabilities = {option: 0.0 for option in request.criteria}
            probabilities[choice] = 0.9
            answers.append(ChoiceAnswer(choice, probabilities, 0.9))
        return answers


def write_gold(tmp_path, rows):
    path = tmp_path / "gold.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n")
    return path


def test_load_gold_validates_rows(tmp_path):
    path = write_gold(tmp_path, [{"state": {"arquivo": "a.txt"}, "target": "outros"}])
    [case] = load_gold(path)
    assert case.target == "outros"
    assert case.source == "synthetic"


def test_eval_metrics_and_confusion(tmp_path):
    schema = tmp_path / "schema.xml"
    schema.write_text(SCHEMA, encoding="utf-8")
    gold = write_gold(
        tmp_path,
        [
            {"state": {"arquivo": "a.txt"}, "target": "documentos/contas"},
            {"state": {"arquivo": "b.txt"}, "target": "documentos/contas"},
            {"state": {"arquivo": "c.txt"}, "target": "outros", "source": "local"},
        ],
    )
    backend = FakeModel(
        {
            "a.txt": "documentos/contas",
            "b.txt": "documentos/contratos",
            "c.txt": "documentos/contas",
        }
    )
    report = run_eval(schema, gold, backend=backend)
    assert report.total == 3
    assert report.correct == 1
    assert report.accuracy == 1 / 3
    assert report.confusion["documentos/contas"]["documentos/contratos"] == 1
    assert report.confusion["outros"]["documentos/contas"] == 1
    assert report.by_source["synthetic"]["total"] == 2
    assert report.by_source["local"]["total"] == 1
    assert "threshold" not in report.to_dict()
