class ContextEngine:
    # FIX 5: aggiunto Livestock in _EXT_BOOST (gli animali sono più probabili
    # nelle scene esterne) e rimosso da _INT_BOOST le categorie meno pertinenti.
    _INT_BOOST   = {"Set Dressing", "Makeup", "Special Equipment", "Sound", "Props"}
    _EXT_BOOST   = {"Vehicles", "Special FX", "Stunts", "VFX", "Greenery", "Livestock"}
    _NIGHT_BOOST = {"Special Equipment", "VFX", "Special FX", "Sound"}
    _BOOST_AMOUNT = 0.08

    # FIX 5: parole chiave nella location che indicano una scena su/in un veicolo.
    # In questi casi Vehicles deve essere boostato anche se INT.
    _VEHICLE_LOCATION_KEYWORDS = (
        "MACCHINA", "AUTO", "AUTOMOBILE",
        "CAMION", "BUS", "PULLMAN",
        "TRENO", "VAGONE",
        "MOTO", "MOTOCICLETTA",
        "ELICOTTERO", "AEREO",
        "BARCA", "NAVE",
        "FURGONE", "VAN",
    )

    async def enhance(self, elements, scene_context):
        # Retrocompatibile: accetta sia stringa (test legacy) che dict
        if isinstance(scene_context, dict):
            int_ext   = scene_context.get("int_ext",  "").upper()
            day_night = scene_context.get("day_night", "").upper()
            location  = scene_context.get("location", "").upper()
        else:
            # Vecchio comportamento: nessun boost
            return elements

        boosted_cats = set()

        if int_ext == "INT":
            boosted_cats |= self._INT_BOOST
        elif int_ext == "EXT":
            boosted_cats |= self._EXT_BOOST

        if "NOTTE" in day_night:
            boosted_cats |= self._NIGHT_BOOST

        # FIX 5: boost Vehicles anche per scene INT ambientate in/su un veicolo.
        # Es: "INT. MACCHINA", "INT. AUTO", "INT. TRENO" ecc.
        if int_ext == "INT" and any(
            kw in location for kw in self._VEHICLE_LOCATION_KEYWORDS
        ):
            boosted_cats.add("Vehicles")

        if not boosted_cats:
            return elements

        for e in elements:
            if e.category in boosted_cats and e.ai_confidence is not None:
                e.ai_confidence = min(1.0, e.ai_confidence + self._BOOST_AMOUNT)

        return elements