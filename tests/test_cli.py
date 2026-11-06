from core.cli import main
from core.model import ChoiceAnswer
from core.plans import PlanStore

SCHEMA = """<targets>
  <documentos prompt="Documentos importantes">
    <contas prompt="Contas de luz e água" />
  </documentos>
  <outros prompt="Diversos" />
</targets>"""


class FakeModel:
    model_id = "fake-model"

    def __init__(self, choice="documentos/contas"):
        self.choice = choice

    def predict_choices(self, requests):
        answers = []
        for request in requests:
            probabilities = {option: 0.0 for option in request.criteria}
            probabilities[self.choice] = 0.9
            answers.append(ChoiceAnswer(self.choice, probabilities, 0.9))
        return answers


def setup(tmp_path):
    schema = tmp_path / "schema.xml"
    schema.write_text(SCHEMA, encoding="utf-8")
    source = tmp_path / "downloads"
    source.mkdir()
    (source / "a.txt").write_text("conta de luz", encoding="utf-8")
    store = PlanStore(tmp_path / "plans")
    return schema, source, store


def test_plan_ephemeral_does_not_persist(tmp_path, capsys):
    schema, source, store = setup(tmp_path)
    code = main(
        ["plan", "--schema", str(schema), "--source", str(source), "--ephemeral"],
        backend=FakeModel(),
        store=store,
    )
    assert code == 0
    assert "1 arquivo" in capsys.readouterr().out
    assert store.list_plans() == []


def test_plan_persists_and_apply_moves(tmp_path):
    schema, source, store = setup(tmp_path)
    assert main(["plan", "--schema", str(schema), "--source", str(source)], backend=FakeModel(), store=store) == 0
    [plan] = store.list_plans()
    assert plan.id == 1
    assert main(["apply", "--plan", "0"], backend=FakeModel(), store=store) == 0
    assert (source / "documentos" / "contas" / "a.txt").exists()
    assert not (source / "a.txt").exists()
    assert store.load(1).status == "applied"


def test_apply_reports_failure_and_exit_code(tmp_path, capsys):
    schema, source, store = setup(tmp_path)
    main(["plan", "--schema", str(schema), "--source", str(source)], backend=FakeModel(), store=store)
    (source / "a.txt").unlink()
    capsys.readouterr()
    assert main(["apply", "--plan", "1"], store=store) == 1
    output = capsys.readouterr().out
    assert "falhou" in output.lower() or "failed" in output.lower()


def test_list_show_and_forget(tmp_path, capsys):
    import json

    schema, source, store = setup(tmp_path)
    main(["plan", "--schema", str(schema), "--source", str(source)], backend=FakeModel(), store=store)
    capsys.readouterr()

    assert main(["list"], store=store) == 0
    assert "0001" in capsys.readouterr().out

    assert main(["show", "--plan", "1", "--json"], store=store) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["id"] == 1
    assert data["entries"][0]["reason"] == "chosen"

    assert main(["forget", "--plan", "1"], store=store) == 0
    assert store.list_plans() == []


def test_plan_without_model_gives_fetch_instruction(tmp_path, monkeypatch, capsys):
    schema, source, store = setup(tmp_path)
    monkeypatch.setenv("FSORT_MODEL_PATH", str(tmp_path / "missing"))
    code = main(["plan", "--schema", str(schema), "--source", str(source)], store=store)
    assert code == 1
    assert "fsort fetch-model" in capsys.readouterr().err


def test_fetch_model_command(tmp_path, monkeypatch, capsys):
    from core import fetch

    def fake_fetch(dest, revision, progress=None):
        path = tmp_path / "Julia-1"
        path.mkdir()
        return path

    monkeypatch.setattr(fetch, "fetch_model", fake_fetch)
    assert main(["fetch-model"]) == 0
    assert "Julia-1" in capsys.readouterr().out


def test_apply_accepts_nochown(tmp_path):
    schema, source, store = setup(tmp_path)
    main(["plan", "--schema", str(schema), "--source", str(source)], backend=FakeModel(), store=store)
    assert main(["apply", "--plan", "1", "--nochown"], store=store) == 0


def test_eval_command(tmp_path, capsys):
    import json

    schema = tmp_path / "schema.xml"
    schema.write_text(SCHEMA, encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        json.dumps(
            {
                "state": {"arquivo": "a.txt", "tipo": "texto", "resumo": "conta"},
                "target": "documentos/contas",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    code = main(
        ["eval", "--schema", str(schema), "--gold", str(gold)],
        backend=FakeModel(),
        store=PlanStore(tmp_path / "plans"),
    )
    assert code == 0
    assert "acurácia" in capsys.readouterr().out


def test_fetch_vision_command(tmp_path, monkeypatch, capsys):
    from core import fetch

    def fake_fetch(dest, model_id, revision, progress=None):
        path = tmp_path / "Florence-2-base"
        path.mkdir()
        return path

    monkeypatch.setattr(fetch, "fetch_vision_model", fake_fetch)
    assert main(["fetch-vision"]) == 0
    assert "Florence-2-base" in capsys.readouterr().out
