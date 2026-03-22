import pytest
from gliamispo.parsing.fountain_parser import FountainParser, FOUNTAIN_LINES_PER_PAGE


def test_parse_empty():
    parser = FountainParser()
    assert parser.parse("") == []


def test_parse_single_scene():
    text = "INT. CUCINA - GIORNO\n\nMario entra nella stanza."
    scenes = FountainParser().parse(text)
    assert len(scenes) == 1
    assert scenes[0].int_ext == "INT"
    assert scenes[0].location == "CUCINA"
    assert scenes[0].day_night == "GIORNO"


def test_normalize_night():
    text = "INT. BAR - NIGHT\n\nScene content"
    scenes = FountainParser().parse(text)
    assert scenes[0].day_night == "NOTTE"


def test_normalize_day():
    text = "EXT. STREET - DAY\n\nAction line"
    scenes = FountainParser().parse(text)
    assert scenes[0].day_night == "GIORNO"


def test_normalize_dawn():
    text = "EXT. CAMPO - DAWN\n\nContent"
    scenes = FountainParser().parse(text)
    assert scenes[0].day_night == "ALBA"


def test_normalize_dusk():
    text = "EXT. MARE - DUSK\n\nContent"
    scenes = FountainParser().parse(text)
    assert scenes[0].day_night == "TRAMONTO"


def test_ext_scene():
    text = "EXT. PIAZZA - ALBA\n\nScene content"
    scenes = FountainParser().parse(text)
    assert scenes[0].int_ext == "EXT"
    assert scenes[0].day_night == "ALBA"
    assert scenes[0].location == "PIAZZA"


def test_int_ext_scene():
    text = "INT/EXT. AUTO - GIORNO\n\nScene content"
    scenes = FountainParser().parse(text)
    assert scenes[0].int_ext == "INT/EXT"
    assert scenes[0].location == "AUTO"


def test_multiple_scenes():
    text = (
        "INT. CUCINA - GIORNO\n\nScene 1\n\n"
        "EXT. STRADA - NOTTE\n\nScene 2\n\n"
        "INT. UFFICIO - GIORNO\n\nScene 3"
    )
    scenes = FountainParser().parse(text)
    assert len(scenes) == 3


def test_scene_numbers():
    text = (
        "INT. CUCINA - GIORNO\n\nScene 1\n\n"
        "EXT. STRADA - NOTTE\n\nScene 2"
    )
    scenes = FountainParser().parse(text)
    assert scenes[0].scene_number == "1"
    assert scenes[1].scene_number == "2"


def test_character_detection():
    text = "INT. UFFICIO - GIORNO\n\nMARIO\nCome stai?\n\nLUCIA\nBene grazie."
    scenes = FountainParser().parse(text)
    assert "MARIO" in scenes[0].characters
    assert "LUCIA" in scenes[0].characters


def test_character_not_duplicated():
    text = "INT. STANZA - NOTTE\n\nMARIO\nDialogo.\n\nMARIO\nAltro dialogo."
    scenes = FountainParser().parse(text)
    assert scenes[0].characters.count("MARIO") == 1


def test_page_start_positive():
    text = "INT. CUCINA - GIORNO\n\nContent"
    scenes = FountainParser().parse(text)
    assert scenes[0].page_start > 0


def test_page_end_gte_page_start():
    text = "INT. CUCINA - GIORNO\n\nContent\nMore content"
    scenes = FountainParser().parse(text)
    assert scenes[0].page_end >= scenes[0].page_start


def test_fountain_lines_per_page():
    assert FOUNTAIN_LINES_PER_PAGE == 56


def test_synopsis_trimmed():
    text = "INT. CUCINA - GIORNO\n\nRiga uno.\nRiga due."
    scenes = FountainParser().parse(text)
    assert not scenes[0].synopsis.endswith(" ")


def test_location_stripped():
    text = "INT.  SALOTTO  - GIORNO\n\nContent"
    scenes = FountainParser().parse(text)
    assert scenes[0].location == "SALOTTO"


def test_continuo_preserved():
    text = "INT. UFFICIO - CONTINUO\n\nContent"
    scenes = FountainParser().parse(text)
    assert scenes[0].day_night == "CONTINUO"


def test_dialogue_in_synopsis_lowercase():
    text = "INT. CUCINA - GIORNO\n\nAzione visiva.\n\nMARIO\nVoglio un caffè!\n\nAltro azione."
    scenes = FountainParser().parse(text)
    assert "voglio un caffè!" in scenes[0].synopsis


def test_dialogue_not_uppercase_in_synopsis():
    text = "INT. STANZA - NOTTE\n\nMARIO\nParola MAIUSCOLA nel dialogo."
    scenes = FountainParser().parse(text)
    # il dialogo è in minuscolo → nessuna sequenza ALL CAPS visibile all'NER
    assert "MAIUSCOLA" not in scenes[0].synopsis
    assert "maiuscola" in scenes[0].synopsis


def test_action_uppercase_preserved_in_synopsis():
    text = "INT. GARAGE - GIORNO\n\nUna PISTOLA sul tavolo."
    scenes = FountainParser().parse(text)
    # le action lines NON sono dialogo → maiuscolo preservato
    assert "PISTOLA" in scenes[0].synopsis


def test_dialogue_and_action_both_in_synopsis():
    text = (
        "INT. BAR - SERA\n\n"
        "Un BICCHIERE cade.\n\n"
        "LUCIA\nNon è colpa mia.\n\n"
        "MARCO\nSicuro?\n\n"
        "Silenzio in sala."
    )
    scenes = FountainParser().parse(text)
    syn = scenes[0].synopsis
    assert "BICCHIERE" in syn          # action → maiuscolo
    assert "non è colpa mia." in syn   # dialogo → minuscolo
    assert "sicuro?" in syn            # dialogo → minuscolo
    assert "Silenzio in sala." in syn  # action → originale
