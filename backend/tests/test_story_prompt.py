from klara.llm.prompts import build_story_user_prompt


def test_target_lemmas_inject_objetivo_block():
    prompt = build_story_user_prompt(
        topic="t",
        target_label="alemán",
        recent_vocab="(ninguno)",
        target_lemmas=["Haus", "laufen"],
    )
    assert "PALABRAS OBJETIVO DE HOY" in prompt
    assert "Haus, laufen" in prompt
    assert "target_words" in prompt
    # El tema y el vocabulario reciente siguen presentes.
    assert "Tema: t" in prompt
    assert "(ninguno)" in prompt


def test_no_target_lemmas_omits_objetivo_block():
    prompt = build_story_user_prompt(
        topic="t",
        target_label="alemán",
        recent_vocab="(ninguno)",
        target_lemmas=[],
    )
    assert "PALABRAS OBJETIVO DE HOY" not in prompt
    # Sigue siendo un prompt válido y completo.
    assert "Genera el JSON ahora." in prompt


def test_user_prompt_includes_module_objective_when_present():
    out = build_story_user_prompt(
        topic="café",
        target_label="alemán",
        recent_vocab="(ninguno)",
        target_lemmas=["Kaffee"],
        module_objective="OBJETIVO DEL MÓDULO: puedo pedir algo en un café. Foco: género de comida.",
    )
    assert "OBJETIVO DEL MÓDULO" in out
    assert "Kaffee" in out  # target block still present


def test_user_prompt_omits_objective_block_when_none():
    out = build_story_user_prompt(
        topic="café",
        target_label="alemán",
        recent_vocab="(ninguno)",
        target_lemmas=[],
        module_objective=None,
    )
    assert "OBJETIVO DEL MÓDULO" not in out
