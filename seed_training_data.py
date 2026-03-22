"""
Popola il DB con ~250 esempi sintetici di scene + elementi verificati
così il primo training sklearn parte da una base solida.

Uso:  python seed_training_data.py [percorso_db]
      Default: ~/Library/Application Support/Gliamispo/gliamispo.db
"""
import os
import sys
import sqlite3


SEED_EXAMPLES = [
    # --- Cast (30) ---
    ("L'attore entra nella stanza buia", "attore", "Cast"),
    ("L'attrice si siede al tavolo", "attrice", "Cast"),
    ("Il protagonista corre nel vicolo", "protagonista", "Cast"),
    ("Il personaggio apre la porta e urla", "personaggio", "Cast"),
    ("L'interprete recita il monologo", "interprete", "Cast"),
    ("Maria saluta Giovanni dalla finestra", "Maria", "Cast"),
    ("Il detective interroga il sospettato", "detective", "Cast"),
    ("La dottoressa esamina il paziente", "dottoressa", "Cast"),
    ("Il commissario entra nell'ufficio", "commissario", "Cast"),
    ("La ragazza fugge dalla casa", "ragazza", "Cast"),
    ("Il padre abbraccia il figlio", "padre", "Cast"),
    ("La madre prepara la cena", "madre", "Cast"),
    ("Il prete benedice i presenti", "prete", "Cast"),
    ("L'avvocato presenta le prove", "avvocato", "Cast"),
    ("La giornalista intervista il testimone", "giornalista", "Cast"),
    ("Il soldato carica il fucile", "soldato", "Cast"),
    ("La barista serve il caffè al cliente", "barista", "Cast"),
    ("Il ragazzo guarda fuori dalla finestra", "ragazzo", "Cast"),
    ("La nonna racconta una storia ai nipoti", "nonna", "Cast"),
    ("Il professore scrive alla lavagna", "professore", "Cast"),
    ("Il pilota controlla gli strumenti di bordo", "pilota", "Cast"),
    ("La cantante sale sul palco illuminato", "cantante", "Cast"),
    ("L'infermiera controlla il monitor del paziente", "infermiera", "Cast"),
    ("Il bambino gioca con un pallone nel cortile", "bambino", "Cast"),
    ("La donna anziana passeggia nel parco", "donna anziana", "Cast"),
    ("Il cameriere porta i piatti al tavolo", "cameriere", "Cast"),
    ("Il guardiano chiude il cancello di notte", "guardiano", "Cast"),
    ("L'uomo misterioso osserva dalla collina", "uomo misterioso", "Cast"),
    ("La poliziotta ferma il sospetto all'angolo", "poliziotta", "Cast"),
    ("Il chirurgo si lava le mani prima dell'operazione", "chirurgo", "Cast"),

    # --- Extras (15) ---
    ("Folla di passanti attraversa la piazza", "passanti", "Extras"),
    ("Comparse in uniforme sfilano nella via", "comparse", "Extras"),
    ("I figuranti riempiono il ristorante", "figuranti", "Extras"),
    ("Gruppo di turisti fotografa il monumento", "turisti", "Extras"),
    ("Passeggeri salgono sull'autobus", "passeggeri", "Extras"),
    ("Studenti escono dalla scuola in massa", "studenti", "Extras"),
    ("Una folla protesta davanti al municipio", "folla", "Extras"),
    ("Operai lavorano nel cantiere sullo sfondo", "operai", "Extras"),
    ("I camerieri si muovono fra i tavoli affollati", "camerieri", "Extras"),
    ("Spettatori applaudono alla fine dello spettacolo", "spettatori", "Extras"),
    ("Pazienti attendono nella sala d'aspetto", "pazienti", "Extras"),
    ("Soldati marciano in formazione nella piazza", "soldati", "Extras"),
    ("Bambini giocano nel parco sullo sfondo", "bambini", "Extras"),
    ("I fedeli pregano nella chiesa gremita", "fedeli", "Extras"),
    ("Invitati danzano al ricevimento di nozze", "invitati", "Extras"),

    # --- Stunts (20) ---
    ("Lo stuntman salta dal tetto dell'edificio", "stuntman", "Stunts"),
    ("La controfigura esegue la caduta dal ponte", "controfigura", "Stunts"),
    ("Caduta rovinosa giù dalle scale", "caduta", "Stunts"),
    ("Rissa violenta nel vicolo buio", "rissa", "Stunts"),
    ("Combattimento corpo a corpo nel magazzino", "combattimento", "Stunts"),
    ("Inseguimento a piedi tra le strade della città", "inseguimento a piedi", "Stunts"),
    ("Il personaggio viene spinto contro il muro", "spinto", "Stunts"),
    ("Scazzottata tra due uomini nel bar", "scazzottata", "Stunts"),
    ("L'uomo si lancia dalla finestra del secondo piano", "lancio dalla finestra", "Stunts"),
    ("Lotta furiosa nel parcheggio sotterraneo", "lotta", "Stunts"),
    ("Il protagonista rotola giù per la collina", "rotola", "Stunts"),
    ("Scena di duello con spade nel castello", "duello con spade", "Stunts"),
    ("Il ladro cade dal muro di cinta", "cade dal muro", "Stunts"),
    ("Salto mortale sopra il cofano dell'auto", "salto mortale", "Stunts"),
    ("L'agente si appende al cornicione del palazzo", "appende al cornicione", "Stunts"),
    ("Calcio volante nell'arena di combattimento", "calcio volante", "Stunts"),
    ("Colluttazione in ascensore tra due guardie", "colluttazione", "Stunts"),
    ("L'uomo cade dalla motocicletta in corsa", "cade dalla moto", "Stunts"),
    ("Sparatoria nel corridoio con rotolamento a terra", "rotolamento a terra", "Stunts"),
    ("Precipizio da un dirupo nella foresta", "precipizio", "Stunts"),

    # --- Vehicles (20) ---
    ("L'auto sfreccia a tutta velocità", "auto", "Vehicles"),
    ("La macchina della polizia insegue il furgone", "macchina polizia", "Vehicles"),
    ("Il camion si ferma davanti al magazzino", "camion", "Vehicles"),
    ("L'elicottero sorvola il campo di battaglia", "elicottero", "Vehicles"),
    ("La motocicletta sfreccia tra le auto", "motocicletta", "Vehicles"),
    ("L'ambulanza arriva a sirene spiegate", "ambulanza", "Vehicles"),
    ("Il taxi si ferma all'angolo della strada", "taxi", "Vehicles"),
    ("L'autobus parte dalla stazione centrale", "autobus", "Vehicles"),
    ("La barca attraversa il lago nella nebbia", "barca", "Vehicles"),
    ("Il treno entra nella galleria buia", "treno", "Vehicles"),
    ("Lo yacht naviga al largo della costa", "yacht", "Vehicles"),
    ("La limousine si ferma davanti all'hotel", "limousine", "Vehicles"),
    ("Il furgone blindato trasporta il denaro", "furgone blindato", "Vehicles"),
    ("La bicicletta attraversa il parco di notte", "bicicletta", "Vehicles"),
    ("L'aereo atterra sulla pista deserta", "aereo", "Vehicles"),
    ("Il carrarmato avanza tra le macerie", "carrarmato", "Vehicles"),
    ("La jeep attraversa il guado nel torrente", "jeep", "Vehicles"),
    ("Lo scooter si infila nel traffico cittadino", "scooter", "Vehicles"),
    ("Il gommone si avvicina alla scogliera", "gommone", "Vehicles"),
    ("La berlina nera parcheggia nel vicolo", "berlina nera", "Vehicles"),

    # --- Props (25) ---
    ("Mario punta la pistola verso il nemico", "pistola", "Props"),
    ("Il coltello cade sul pavimento con un rumore", "coltello", "Props"),
    ("Il telefono squilla nella stanza vuota", "telefono", "Props"),
    ("La lettera è posata sul tavolo", "lettera", "Props"),
    ("La valigia contiene documenti segreti", "valigia", "Props"),
    ("Le chiavi cadono dalla tasca", "chiavi", "Props"),
    ("Il bicchiere si rompe a terra", "bicchiere", "Props"),
    ("La torcia illumina il corridoio buio", "torcia", "Props"),
    ("La fotografia mostra un volto sconosciuto", "fotografia", "Props"),
    ("Il fucile è appoggiato al muro", "fucile", "Props"),
    ("Il diario contiene annotazioni criptiche", "diario", "Props"),
    ("L'orologio segna la mezzanotte", "orologio", "Props"),
    ("La borsa è nascosta sotto il letto", "borsa", "Props"),
    ("Il giornale annuncia la notizia in prima pagina", "giornale", "Props"),
    ("La siringa è sul tavolo operatorio", "siringa", "Props"),
    ("Il computer portatile mostra il file rubato", "computer portatile", "Props"),
    ("La radio trasmette un messaggio in codice", "radio", "Props"),
    ("Il binocolo inquadra la casa dall'altra parte della valle", "binocolo", "Props"),
    ("La mappa è stesa sul cofano dell'auto", "mappa", "Props"),
    ("Il pacchetto arriva con un corriere sconosciuto", "pacchetto", "Props"),
    ("Il badge di sicurezza apre la porta blindata", "badge", "Props"),
    ("La valigetta è ammanettata al polso", "valigetta", "Props"),
    ("La bottiglia di vino è al centro del tavolo", "bottiglia di vino", "Props"),
    ("Il passaporto falso è nella tasca interna", "passaporto falso", "Props"),
    ("Il registratore nascosto cattura la conversazione", "registratore", "Props"),

    # --- Special FX (20) ---
    ("Esplosione nel corridoio dell'edificio", "esplosione", "Special FX"),
    ("Le fiamme avvolgono il capannone industriale", "fiamme", "Special FX"),
    ("Il fuoco divampa nella foresta di notte", "fuoco", "Special FX"),
    ("Fumo denso riempie la stanza dopo lo sparo", "fumo", "Special FX"),
    ("Pioggia torrenziale sulla scena del crimine", "pioggia artificiale", "Special FX"),
    ("Neve finta cade nel giardino della villa", "neve finta", "Special FX"),
    ("Lampi e tuoni durante il temporale", "lampi e tuoni", "Special FX"),
    ("Il sangue finto cola dalla ferita al braccio", "sangue finto", "Special FX"),
    ("Vetri esplodono verso l'interno della stanza", "vetri esplosione", "Special FX"),
    ("Effetti pirotecnici illuminano il cielo notturno", "pirotecnica", "Special FX"),
    ("La nebbia artificiale avvolge il cimitero", "nebbia artificiale", "Special FX"),
    ("Scintille volano dalla saldatrice nel garage", "scintille", "Special FX"),
    ("Colpo di proiettile con squib sulla giacca", "squib proiettile", "Special FX"),
    ("Fuoco controllato nel camino della villa", "fuoco controllato", "Special FX"),
    ("Polvere e detriti dopo il crollo del muro", "polvere e detriti", "Special FX"),
    ("Fiammate improvvise dal tubo del gas", "fiammate gas", "Special FX"),
    ("Schizzi di sangue sul muro dopo lo sparo", "schizzi sangue", "Special FX"),
    ("Vapore esce dal tombino nella strada buia", "vapore tombino", "Special FX"),
    ("Il tetto crolla con polvere e calcinacci", "crollo tetto", "Special FX"),
    ("Flash accecante nella stanza dell'interrogatorio", "flash accecante", "Special FX"),

    # --- Wardrobe (15) ---
    ("L'uomo indossa un abito elegante nero", "abito elegante", "Wardrobe"),
    ("La donna porta un vestito rosso lungo", "vestito rosso", "Wardrobe"),
    ("Il soldato indossa l'uniforme mimetica", "uniforme mimetica", "Wardrobe"),
    ("Il detective porta un impermeabile beige", "impermeabile", "Wardrobe"),
    ("La suora indossa un abito talare bianco", "abito talare", "Wardrobe"),
    ("Il chirurgo porta il camice verde da sala operatoria", "camice chirurgico", "Wardrobe"),
    ("L'uomo indossa un cappotto lungo grigio", "cappotto", "Wardrobe"),
    ("La sposa porta un abito bianco da cerimonia", "abito da sposa", "Wardrobe"),
    ("Il pompiere indossa la tuta ignifuga", "tuta ignifuga", "Wardrobe"),
    ("La cameriera porta un grembiule bianco", "grembiule", "Wardrobe"),
    ("Il ladro indossa un passamontagna nero", "passamontagna", "Wardrobe"),
    ("Il re porta una corona d'oro e un mantello", "corona e mantello", "Wardrobe"),
    ("L'infermiera indossa la divisa ospedaliera", "divisa ospedaliera", "Wardrobe"),
    ("Il cowboy porta stivali e un cappello Stetson", "stivali e cappello", "Wardrobe"),
    ("La ballerina indossa un tutù rosa", "tutù rosa", "Wardrobe"),

    # --- Makeup (15) ---
    ("La parrucca bionda copre i capelli dell'attrice", "parrucca", "Makeup"),
    ("Protesi facciale per invecchiare il personaggio", "protesi facciale", "Makeup"),
    ("Trucco teatrale con cicatrice sulla guancia", "trucco cicatrice", "Makeup"),
    ("Ferita finta sul braccio del soldato", "ferita finta", "Makeup"),
    ("Il volto del mostro richiede ore di trucco", "trucco mostro", "Makeup"),
    ("Lividi finti sulle braccia dopo la rissa", "lividi finti", "Makeup"),
    ("Tatuaggio temporaneo sul collo del detenuto", "tatuaggio temporaneo", "Makeup"),
    ("Trucco da zombie con decomposizione facciale", "trucco zombie", "Makeup"),
    ("Barba finta incollata sul mento dell'attore", "barba finta", "Makeup"),
    ("Invecchiamento prostetico del protagonista a 80 anni", "invecchiamento prostetico", "Makeup"),
    ("Sangue secco attorno alla ferita da taglio", "sangue secco makeup", "Makeup"),
    ("Ustione simulata sull'avambraccio sinistro", "ustione simulata", "Makeup"),
    ("Trucco da clown con naso rosso e parrucca", "trucco clown", "Makeup"),
    ("Occhiaie profonde dipinte sul viso del malato", "occhiaie dipinte", "Makeup"),
    ("Calotta per simulare la calvizie del personaggio", "calotta calvizie", "Makeup"),

    # --- Livestock (15) ---
    ("Il cavallo galoppa nella prateria all'alba", "cavallo", "Livestock"),
    ("Il cane abbaia nella notte al cancello", "cane", "Livestock"),
    ("Il gatto cammina sul davanzale della finestra", "gatto", "Livestock"),
    ("Le pecore pascolano nel campo sullo sfondo", "pecore", "Livestock"),
    ("Il corvo è posato sulla spalla del mago", "corvo", "Livestock"),
    ("I piccioni volano via dalla piazza al rumore", "piccioni", "Livestock"),
    ("Il serpente striscia sul pavimento del tempio", "serpente", "Livestock"),
    ("Il toro carica nell'arena sotto il sole", "toro", "Livestock"),
    ("L'aquila vola sopra la montagna innevata", "aquila", "Livestock"),
    ("Il pappagallo ripete le parole dal trespolo", "pappagallo", "Livestock"),
    ("I pesci nuotano nell'acquario del salotto", "pesci", "Livestock"),
    ("Il lupo ulula alla luna piena nel bosco", "lupo", "Livestock"),
    ("La colomba bianca viene liberata al matrimonio", "colomba", "Livestock"),
    ("Il falco si lancia in picchiata dal cielo", "falco", "Livestock"),
    ("I cani da slitta corrono nella tormenta", "cani da slitta", "Livestock"),

    # --- Sound (15) ---
    ("Playback musicale durante il concerto sul palco", "playback", "Sound"),
    ("Il microfono boom cattura i dialoghi nel vicolo", "microfono boom", "Sound"),
    ("Registrazione audio ambientale nella foresta", "registrazione ambientale", "Sound"),
    ("Musica live suonata dalla band nel locale", "musica live", "Sound"),
    ("Il pianoforte suona nella sala da ballo vuota", "pianoforte", "Sound"),
    ("La radio trasmette una canzone anni Cinquanta", "radio trasmette", "Sound"),
    ("Effetti sonori di spari in lontananza", "effetti sonori spari", "Sound"),
    ("La sirena dell'ambulanza risuona nelle strade", "sirena ambulanza", "Sound"),
    ("Coro gregoriano nella cattedrale gotica", "coro gregoriano", "Sound"),
    ("La chitarra acustica accompagna la scena al falò", "chitarra acustica", "Sound"),
    ("Il jukebox suona un vecchio brano nel diner", "jukebox", "Sound"),
    ("Colonna sonora dal vivo con orchestra in sala", "orchestra dal vivo", "Sound"),
    ("Un fischio acuto risuona nel silenzio del campo", "fischio", "Sound"),
    ("Il vinile gira sul giradischi nella penombra", "giradischi", "Sound"),
    ("Tamburi tribali nella scena della cerimonia", "tamburi tribali", "Sound"),

    # --- Special Equipment (15) ---
    ("Ripresa con drone sopra la città al tramonto", "drone", "Special Equipment"),
    ("La steadicam segue il personaggio nel corridoio", "steadicam", "Special Equipment"),
    ("Gru da ripresa per panoramica dall'alto", "gru da ripresa", "Special Equipment"),
    ("Dolly lungo il binario per il carrello laterale", "dolly", "Special Equipment"),
    ("Crane shot dal tetto dell'edificio", "crane", "Special Equipment"),
    ("Ripresa subacquea con custodia impermeabile", "custodia subacquea", "Special Equipment"),
    ("Camera car per l'inseguimento in autostrada", "camera car", "Special Equipment"),
    ("Gimbal stabilizzato per la corsa nel bosco", "gimbal", "Special Equipment"),
    ("Cablecam tesa tra i due palazzi del set", "cablecam", "Special Equipment"),
    ("Slider motorizzato per il primo piano del volto", "slider motorizzato", "Special Equipment"),
    ("Snorkel lens per la ripresa ravvicinata del cibo", "snorkel lens", "Special Equipment"),
    ("Jib arm per il movimento verticale sulla scogliera", "jib arm", "Special Equipment"),
    ("Motion control per il time-lapse nella piazza", "motion control", "Special Equipment"),
    ("Periscopio per ripresa sotto il tavolo", "periscopio", "Special Equipment"),
    ("Macchina da fumo industriale per nebbia sul set", "macchina fumo", "Special Equipment"),

    # --- VFX (15) ---
    ("Ripresa su green screen per compositing digitale", "green screen", "VFX"),
    ("Chroma key per lo sfondo della città futuristica", "chroma key", "VFX"),
    ("CGI per il drago nella scena della battaglia", "CGI drago", "VFX"),
    ("Rimozione digitale dei cavi dello stuntman", "rimozione cavi", "VFX"),
    ("Ambiente virtuale per il pianeta alieno", "ambiente virtuale", "VFX"),
    ("Estensione digitale del set del castello", "estensione set", "VFX"),
    ("Compositing per la pioggia di meteoriti", "compositing", "VFX"),
    ("Tracking markers sul volto per la motion capture", "tracking markers", "VFX"),
    ("Schermo blu per la scena di volo del supereroe", "schermo blu", "VFX"),
    ("De-aging digitale del protagonista da giovane", "de-aging digitale", "VFX"),
    ("Simulazione fluidi per l'alluvione nella valle", "simulazione fluidi", "VFX"),
    ("Matte painting per il panorama della montagna", "matte painting", "VFX"),
    ("Rotoscoping per isolare la figura dal fondo", "rotoscoping", "VFX"),
    ("Effetti particellari per la tempesta di sabbia", "effetti particellari", "VFX"),
    ("Wire removal dopo le acrobazie aeree", "wire removal", "VFX"),

    # --- Set Dressing (15) ---
    ("Mobili d'epoca nel salotto della contessa", "mobili d'epoca", "Set Dressing"),
    ("Scenografia del commissariato con scrivanie", "scenografia commissariato", "Set Dressing"),
    ("Quadri alle pareti dello studio dell'artista", "quadri pareti", "Set Dressing"),
    ("Libri antichi sugli scaffali della biblioteca", "libri antichi", "Set Dressing"),
    ("Arredamento moderno nel loft del protagonista", "arredamento loft", "Set Dressing"),
    ("Tappeti orientali nella sala del palazzo arabo", "tappeti orientali", "Set Dressing"),
    ("Candele accese sull'altare della chiesa", "candele altare", "Set Dressing"),
    ("Tavolo imbandito per la cena di Natale", "tavolo imbandito", "Set Dressing"),
    ("Poster e graffiti sulle pareti del garage", "poster e graffiti", "Set Dressing"),
    ("Tende pesanti alle finestre del castello", "tende castello", "Set Dressing"),
    ("Attrezzi da officina appesi al muro del garage", "attrezzi officina", "Set Dressing"),
    ("Bancarelle del mercato con frutta e verdura", "bancarelle mercato", "Set Dressing"),
    ("Bottiglie polverose sugli scaffali della cantina", "bottiglie cantina", "Set Dressing"),
    ("Giocattoli sparsi nella cameretta del bambino", "giocattoli cameretta", "Set Dressing"),
    ("Mappamondi e carte nautiche nello studio del capitano", "mappamondi e carte", "Set Dressing"),

    # --- Greenery (10) ---
    ("Piante tropicali nella serra del giardino botanico", "piante tropicali", "Greenery"),
    ("Alberi finti nel set dello studio cinematografico", "alberi finti", "Greenery"),
    ("Fiori freschi sul bancone della reception", "fiori freschi", "Greenery"),
    ("Siepe alta che nasconde il giardino segreto", "siepe alta", "Greenery"),
    ("Rampicanti sul muro della casa abbandonata", "rampicanti", "Greenery"),
    ("Vasi di fiori sul balcone dell'appartamento", "vasi di fiori", "Greenery"),
    ("Prato curato nel parco della villa nobiliare", "prato curato", "Greenery"),
    ("Muschio finto sulle rocce della grotta", "muschio finto", "Greenery"),
    ("Palme artificiali nella hall dell'hotel tropicale", "palme artificiali", "Greenery"),
    ("Cespugli potati all'ingresso del cimitero", "cespugli potati", "Greenery"),

    # --- Security (5) ---
    ("Scena di folla al concerto richiede sicurezza", "sicurezza folla", "Security"),
    ("Guardie armate per la scena della rapina in banca", "guardie armate", "Security"),
    ("Chiusura della strada per le riprese dell'inseguimento", "chiusura strada", "Security"),
    ("Controllo accessi al set nel centro storico", "controllo accessi", "Security"),
    ("Vigili del fuoco in standby per la scena dell'incendio", "vigili del fuoco standby", "Security"),

    # --- Intimacy (5) ---
    ("Scena romantica tra i due protagonisti a letto", "scena romantica", "Intimacy"),
    ("Il coordinatore di intimità prepara la scena d'amore", "coordinatore intimità", "Intimacy"),
    ("Bacio appassionato sotto la pioggia", "bacio appassionato", "Intimacy"),
    ("Scena di nudità parziale nella vasca da bagno", "nudità parziale", "Intimacy"),
    ("Abbraccio intimo nella camera d'albergo", "abbraccio intimo", "Intimacy"),

    # --- Mechanical FX (5) ---
    ("Porta che sbatte per effetto meccanico a filo", "porta a filo", "Mechanical FX"),
    ("Piattaforma mobile per il terremoto simulato", "piattaforma terremoto", "Mechanical FX"),
    ("Meccanismo di apertura per il passaggio segreto", "meccanismo segreto", "Mechanical FX"),
    ("Effetto vento forte con ventilatori industriali", "ventilatori vento", "Mechanical FX"),
    ("Ribaltamento auto con rampa pneumatica", "rampa pneumatica", "Mechanical FX"),
]


def seed(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Progetto seed dedicato
    cur = conn.execute(
        "INSERT INTO projects (title, director) VALUES (?, ?)",
        ("__SEED_TRAINING__", "system"),
    )
    project_id = cur.lastrowid

    inserted = 0
    for i, (synopsis, element_name, category) in enumerate(SEED_EXAMPLES):
        scene_num = f"SEED-{i+1:03d}"
        cur = conn.execute(
            "INSERT INTO scenes (project_id, scene_number, location, "
            "int_ext, day_night, page_start_whole, page_start_eighths, "
            "page_end_whole, page_end_eighths, synopsis) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (project_id, scene_num, "STUDIO", "INT", "GIORNO",
             1, 0, 1, 1, synopsis),
        )
        scene_id = cur.lastrowid

        cur = conn.execute(
            "INSERT INTO scene_elements (scene_id, category, element_name, "
            "ai_suggested, ai_confidence, detection_method, user_verified) "
            "VALUES (?,?,?,1,0.95,?,1)",
            (scene_id, category, element_name, "seed_training"),
        )
        element_id = cur.lastrowid

        # Marca come VERIFY così FeedbackLoopService lo raccoglie
        conn.execute(
            "INSERT INTO user_corrections "
            "(element_id, scene_id, action, before_category, after_category, "
            "before_name, after_name, original_confidence) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (element_id, scene_id, "VERIFY", category, category,
             element_name, element_name, 0.95),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Seed completato: {inserted} esempi in {len(set(c for _,_,c in SEED_EXAMPLES))} categorie")


if __name__ == "__main__":
    default = os.path.expanduser(
        "~/Library/Application Support/Gliamispo/gliamispo.db"
    )
    path = sys.argv[1] if len(sys.argv) > 1 else default
    if not os.path.exists(path):
        print(f"DB non trovato: {path}")
        sys.exit(1)
    seed(path)
