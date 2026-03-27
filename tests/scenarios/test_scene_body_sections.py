from modules.scenarios.widgets.scene_body_sections import _build_hero_text


def test_build_hero_text_keeps_full_intro_without_truncation():
    long_intro = (
        "Le shérif de Millfield, stupéfait par les révélations concernant la société secrète Eon, "
        "décide immédiatement de mettre en place une enquête. "
        "Il rassemble ses hommes les plus compétents et prépare une stratégie complète pour infiltrer le quartier souterrain."
    )

    assert _build_hero_text(long_intro, []) == long_intro
