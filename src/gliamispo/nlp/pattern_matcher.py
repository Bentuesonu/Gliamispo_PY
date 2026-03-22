"""
gliamispo.nlp.pattern_matcher
------------------------------
Pattern matcher a regex per le 21 categorie del breakdown cinematografico.

Copre terminologia italiana e inglese per:
  Props, Wardrobe, Vehicles, Set Dressing, Greenery, Music, Sound,
  Special FX, Mechanical FX, VFX, Stunts, Special Equipment,
  Makeup, Livestock, Animal Handlers, Extras, Security,
  Additional Labor, Intimacy, Notes.

(Cast viene gestito da NERExtractor con strategia dedicata.)

Confidence dei pattern: 0.78 (più alta della NER regex 0.65, più bassa
del vocabolario 0.85, perché un pattern cattura il termine ma non il
contesto semantico completo).
"""

import re
from gliamispo.models.scene_element import SceneElement

# ── Confidence default per i match da pattern ────────────────────────────────
_PATTERN_CONFIDENCE = 0.78

# ── Stopword per il filtraggio del contesto aggettivale ──────────────────────
_STOPWORDS = frozenset({
    # articoli e preposizioni italiane
    'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una',
    'di', 'a', 'da', 'in', 'con', 'su', 'per', 'tra', 'fra',
    'del', 'della', 'dei', 'degli', 'delle', 'al', 'allo', 'alla',
    'ai', 'agli', 'alle', 'dal', 'dallo', 'dalla', 'dai', 'dagli',
    'dalle', 'nel', 'nello', 'nella', 'nei', 'negli', 'nelle',
    'sul', 'sullo', 'sulla', 'sui', 'sugli', 'sulle',
    'col', 'coi', 'e', 'o', 'ma', 'che', 'non', 'si', 'è', 'ha', 'ho',
    # articoli e preposizioni inglesi
    'the', 'an', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
    'and', 'or', 'but', 'is', 'are', 'was', 'were', 'has', 'have',
    'his', 'her', 'its', 'my', 'your', 'their', 'our',
})

# Parola immediatamente dopo il match (solo spazi, niente punteggiatura)
_POST_WORD_RE = re.compile(r'^\s+(\w+)')
# Parola immediatamente prima del match
_PRE_WORD_RE = re.compile(r'(\w+)\s+$')

# ── Definizione categorie e pattern ─────────────────────────────────────────
#
# Struttura: lista di (pattern_regex, categoria, nome_elemento_normalizzato)
# Il nome_elemento è quello che viene salvato in DB; se None si usa il match.
#
# NOTA: i pattern usano \b per evitare match parziali.
# Ordine: pattern più specifici prima dei più generici.

_RAW_PATTERNS = [

    # ════════════════════════════════════════════════════════════════════
    # PROPS — Oggetti di scena
    # ════════════════════════════════════════════════════════════════════

    # Armi
    (r'\bpistol[ae]?\b', 'Props', 'pistola'),
    (r'\bfucil[ei]?\b', 'Props', 'fucile'),
    (r'\bshotgun\b|\bfucile a pompa\b', 'Props', 'fucile a pompa'),
    (r'\bkalaschnikov\b|\bak-?47\b|\bmitra\b|\bsubmachine gun\b', 'Props', 'mitra'),
    (r'\bcoltell[oi]\b|\bknife\b|\bdagger\b|\bpugnale\b', 'Props', 'coltello'),
    (r'\bspada\b|\bsword\b|\bsciabola\b', 'Props', 'spada'),
    (r'\barco\b|\barrow\b|\bfrecca\b', 'Props', 'arco e frecce'),
    (r'\bbomba\b|\bgrenade\b|\bgranata\b', 'Props', 'bomba'),
    (r'\bdetonator[e]?\b', 'Props', 'detonatore'),
    (r'\bbastoni?\b|\bmanganell[oi]\b|\bclub\b|\bbastone\b', 'Props', 'bastone'),
    # Documenti e carta
    (r'\bdocument[oi]\b|\bdocuments?\b', 'Props', 'documento'),
    (r'\bpassaport[oi]\b|\bpassport\b', 'Props', 'passaporto'),
    (r'\bpatente\b|\bdriving licence\b', 'Props', 'patente'),
    (r'\blettera\b(?!tura)|\bletter\b', 'Props', 'lettera'),
    (r'\bbigliett[oi]\b|\bticket\b', 'Props', 'biglietto'),
    (r'\bcontratt[oi]\b|\bcontract\b', 'Props', 'contratto'),
    (r'\bgiornale\b|\bnewspaper\b', 'Props', 'giornale'),
    (r'\brivista\b|\bmagazine\b', 'Props', 'rivista'),
    (r'\blibroidi?\b|\bbook\b', 'Props', 'libro'),
    (r'\bbibbia\b|\bbible\b', 'Props', 'bibbia'),
    (r'\bbuste?\b|\benvelope\b', 'Props', 'busta'),
    (r'\bvaligetta\b|\bbriefcase\b', 'Props', 'valigetta'),
    (r'\bcartella\b|\bfolder\b', 'Props', 'cartella'),
    # Tecnologia / elettronica
    (r'\btelefon[oi]\b|\bphone\b|\bcellulare\b|\bsmartphone\b', 'Props', 'telefono'),
    (r'\bracchetta\b|\bracket\b', 'Props', 'racchetta'),
    (r'\bcomputer\b|\blaptop\b|\bnotebook\b', 'Props', 'computer'),
    (r'\btablet\b|\bipad\b', 'Props', 'tablet'),
    (r'\bmacchina fotografica\b|\bcamera\b|\bfotocamera\b', 'Props', 'macchina fotografica'),
    (r'\btelescopi[oo]\b|\btelescope\b|\bbinocol[oi]\b|\bbinoculars?\b', 'Props', 'binocolo'),
    (r'\bradio\b(?!\s+(?:base|stazione))', 'Props', 'radio'),
    (r'\bregistratore\b|\brecorder\b', 'Props', 'registratore'),
    (r'\bvideocamera\b|\bcamcorder\b', 'Props', 'videocamera'),
    (r'\bwalkie.?talkie\b', 'Props', 'walkie-talkie'),
    # Cibo e bevande (quando sono oggetti rilevanti)
    (r'\bbottigli[ae]?\b|\bbottle\b', 'Props', 'bottiglia'),
    (r'\bbicchier[ei]?\b|\bglass\b', 'Props', 'bicchiere'),
    (r'\btazz[ae]?\b|\bcup\b|\bmug\b', 'Props', 'tazza'),
    (r'\bpiatt[oi]\b|\bplate\b|\bdish\b', 'Props', 'piatto'),
    (r'\bsambuca\b', 'Props', 'sambuca'),
    (r'\bgratt[ao]\s+e\s+vinci\b|\bscratch\s+card\b', 'Props', 'gratta e vinci'),
    # Soldi e valori
    (r'\bsold[oi]\b|\bdenaro\b|\bcash\b|\bbanconot[ae]?\b|\bbills?\b', 'Props', 'denaro'),
    (r'\bvaligion[ei]?\b(?:\s+di\s+soldi)?\b', 'Props', 'valigione di soldi'),
    (r'\borologi[oo]\b|\bwatch\b|\bwristwatch\b', 'Props', 'orologio'),
    (r'\bchiv[ei]?\b|\bchiave\b|\bkey\b|\bkeys\b', 'Props', 'chiave'),
    # Strumenti e utensili
    (r'\bmartell[oo]\b|\bhammer\b', 'Props', 'martello'),
    (r'\bcacciavite\b|\bscrewdriver\b', 'Props', 'cacciavite'),
    (r'\bsega\b|\bsaw\b', 'Props', 'sega'),
    (r'\bpinz[ae]?\b|\bpliers?\b', 'Props', 'pinze'),
    (r'\bfiaccola\b|\btorch\b|\bflashlight\b|\blampadina tascabile\b', 'Props', 'torcia'),
    (r'\baccendino\b|\blighter\b|\bfiammiferi?\b|\bmatch(?:es)?\b', 'Props', 'accendino'),
    (r'\bsigarett[ae]?\b|\bcigarett?e?\b|\bsigaro\b|\bcigar\b', 'Props', 'sigaretta'),
    # Giocattoli / oggetti speciali
    (r'\bbambola\b|\bdoll\b', 'Props', 'bambola'),
    (r'\bmacchinin[ae]?\b(?!\s+(?:da\s+ripresa|fotografica))', 'Props', 'macchinina'),
    (r'\bfoto(?:grafia)?\b|\bphoto(?:graph)?\b', 'Props', 'fotografia'),
    (r'\bcornice\b|\bframe\b', 'Props', 'cornice'),
    (r'\bzaino\b|\bbackpack\b|\brucksack\b', 'Props', 'zaino'),
    (r'\bbors[ae]?\b|\bhandbag\b|\bpurse\b', 'Props', 'borsa'),
    (r'\bvaligia\b|\bsuitcase\b|\bluggage\b', 'Props', 'valigia'),
    (r'\bcassett[ae]?\b|\bsafe\b', 'Props', 'cassaforte'),
    (r'\benveloppe\b|\bbusta\s+(?:chiusa|sigillata)\b', 'Props', 'busta'),
    (r'\bfiori?\b|\brose?\b|\bbouquet\b(?!\s+di)', 'Props', 'fiori'),
    (r'\banello\b|\bring\b|\bdiamante\b', 'Props', 'anello'),
    (r'\bcollana\b|\bnecklace\b', 'Props', 'collana'),
    (r'\bbracciale\b|\bbracelet\b', 'Props', 'bracciale'),

    # ════════════════════════════════════════════════════════════════════
    # WARDROBE — Costumi e abbigliamento
    # ════════════════════════════════════════════════════════════════════

    (r'\bcostu[mn][eo]\b|\bcostume\b', 'Wardrobe', 'costume'),
    (r'\buniform[ei]?\b|\buniform\b', 'Wardrobe', 'uniforme'),
    (r'\babito\b|\bdress\b|\bgown\b', 'Wardrobe', 'abito'),
    (r'\bvestit[oi]\b|\boutfit\b', 'Wardrobe', 'vestito'),
    (r'\bgiacci[ae]?\b|\bjacket\b|\bjacket\b', 'Wardrobe', 'giacca'),
    (r'\bcappott[oi]\b|\bovercoat\b|\bcoat\b', 'Wardrobe', 'cappotto'),
    (r'\bimpermeabile\b|\braincoat\b|\braincoat\b', 'Wardrobe', 'impermeabile'),
    (r'\bcamicia\b|\bshirt\b', 'Wardrobe', 'camicia'),
    (r'\bpantaloni?\b|\btrousers?\b|\bpants?\b', 'Wardrobe', 'pantaloni'),
    (r'\bgonna\b|\bskirt\b', 'Wardrobe', 'gonna'),
    (r'\bmaglion[ei]?\b|\bsweater\b|\bjumper\b', 'Wardrobe', 'maglione'),
    (r'\bfelpa\b|\bhoodie\b|\bsweatshirt\b', 'Wardrobe', 'felpa'),
    (r'\bscarpe?\b|\bshoes?\b|\bboots?\b|\bstival[ei]?\b', 'Wardrobe', 'scarpe'),
    (r'\bcappell[oi]\b|\bhat\b|\bcap\b|\bberet\b|\bberretto\b', 'Wardrobe', 'cappello'),
    (r'\bcravatta\b|\btie\b|\bbowtie\b', 'Wardrobe', 'cravatta'),
    (r'\bguanti?\b|\bgloves?\b', 'Wardrobe', 'guanti'),
    (r'\bsciarpa\b|\bscarf\b', 'Wardrobe', 'sciarpa'),
    (r'\bocchiali\b(?!\s+(?:da\s+vista|da\s+sole\s+VR))\b|\bglasses?\b|\bsunglasses?\b', 'Wardrobe', 'occhiali'),
    (r'\bbiancheria\b|\bunderwear\b|\blingerie\b', 'Wardrobe', 'biancheria'),
    (r'\bpigiama\b|\bpajamas?\b', 'Wardrobe', 'pigiama'),
    (r'\btuta\b(?!\s+da\s+sub)|\boveralls?\b', 'Wardrobe', 'tuta'),
    (r'\btoga\b|\brobe\b|\btoga\b', 'Wardrobe', 'toga'),
    (r'\bmaschera(?!\s+(?:antigas|subacquea))\b|\bmask\b', 'Wardrobe', 'maschera'),
    (r'\bvelo\b|\bveil\b', 'Wardrobe', 'velo'),

    # ════════════════════════════════════════════════════════════════════
    # VEHICLES — Veicoli
    # ════════════════════════════════════════════════════════════════════

    (r'\bmacchin[ae]?\b|\bauto(?:mobile)?\b|\bcar\b', 'Vehicles', 'automobile'),
    (r'\bsport(?:iva)?\b(?=\s+(?:macchina|auto|car))', 'Vehicles', 'auto sportiva'),
    (r'\bmot[oo](?:cicletta)?\b|\bbike\b|\bmotorcycle\b', 'Vehicles', 'moto'),
    (r'\bcamion\b|\btruck\b|\bloading truck\b', 'Vehicles', 'camion'),
    (r'\bfurgon[ei]?\b|\bvan\b', 'Vehicles', 'furgone'),
    (r'\bus\b|\bautobus\b|\bcoach\b|\bpullman\b', 'Vehicles', 'autobus'),
    (r'\btaxi\b|\bcab\b', 'Vehicles', 'taxi'),
    (r'\btreno\b|\btrain\b|\bvagone\b|\bwagon\b', 'Vehicles', 'treno'),
    (r'\belicotter[oo]\b|\bhelicopter\b|\bhelipad\b', 'Vehicles', 'elicottero'),
    (r'\baere[oo]\b|\bairplane\b|\bjet\b|\bplane\b', 'Vehicles', 'aereo'),
    (r'\bbarca\b|\bboat\b|\bdingh(?:y|i)\b', 'Vehicles', 'barca'),
    (r'\bnave\b|\bship\b|\bferry\b|\btraghett[oo]\b', 'Vehicles', 'nave'),
    (r'\bsommergibi?le\b|\bsubmarine\b', 'Vehicles', 'sottomarino'),
    (r'\bambulanza\b|\bambulance\b', 'Vehicles', 'ambulanza'),
    (r'\bpolizia\s+(?:auto|macchina)\b|\bpoice\s+car\b', 'Vehicles', 'auto della polizia'),
    (r'\bjeep\b|\bsuv\b|\bfuoristrada\b', 'Vehicles', 'jeep'),
    (r'\btank\b|\bcarro\s+armato\b', 'Vehicles', 'carro armato'),
    (r'\bbicicletta\b|\bbike\b|\bcycle\b', 'Vehicles', 'bicicletta'),
    (r'\bscooter\b|\bvespa\b', 'Vehicles', 'scooter'),
    (r'\bquad\b|\batv\b', 'Vehicles', 'quad'),
    (r'\blimo(?:usine)?\b|\blimousine\b', 'Vehicles', 'limousine'),
    (r'\blettiga\b|\bstretcher\b', 'Vehicles', 'lettiga'),

    # ════════════════════════════════════════════════════════════════════
    # SET DRESSING — Arredamento e scenografia
    # ════════════════════════════════════════════════════════════════════

    (r'\btavol[oo]\b|\btable\b|\bdesk\b(?!\s+(?:top|computer))', 'Set Dressing', 'tavolo'),
    (r'\bsedia\b|\bchair\b|\barmchair\b', 'Set Dressing', 'sedia'),
    (r'\bdivan[oo]\b|\bsofa\b|\bcouch\b', 'Set Dressing', 'divano'),
    (r'\blett[oo]\b(?!\s+(?:legale|re))\b|\bbed\b', 'Set Dressing', 'letto'),
    (r'\barmadi[oo]\b|\bwardrobe\b|\bcloset\b', 'Set Dressing', 'armadio'),
    (r'\bscrivani[ae]?\b|\bwriting desk\b', 'Set Dressing', 'scrivania'),
    (r'\blibreri[ae]?\b|\bbookcase\b|\bshelf\b|\bshelves\b', 'Set Dressing', 'libreria'),
    (r'\btappet[oo]\b|\bcarpet\b|\brug\b', 'Set Dressing', 'tappeto'),
    (r'\btende?\b|\bcurtains?\b|\bdrapes?\b', 'Set Dressing', 'tende'),
    (r'\bspecchi[oo]\b|\bmirror\b', 'Set Dressing', 'specchio'),
    (r'\bquadr[oo]\b|\bpainting\b|\bpicture\b(?!\s+(?:perfect|show))', 'Set Dressing', 'quadro'),
    (r'\blampada\b|\bland lamp\b|\bfloor lamp\b|\blamp\b', 'Set Dressing', 'lampada'),
    (r'\bcandelabr[oo]\b|\bchandelier\b|\bcandelabra\b', 'Set Dressing', 'candelabro'),
    (r'\bstufa\b|\bfireplace\b|\bfocolar[ei]?\b|\bheater\b', 'Set Dressing', 'stufa'),
    (r'\btelevisore\b|\btv\b|\btelevision\b|\bscreen\b', 'Set Dressing', 'televisore'),
    (r'\bpianof(?:orte)?\b|\bgrand piano\b|\bupright piano\b', 'Set Dressing', 'pianoforte'),
    (r'\bcass?ettera\b|\bjukebox\b', 'Set Dressing', 'jukebox'),
    (r'\bbancone\b|\bbar counter\b|\bcounter\b', 'Set Dressing', 'bancone'),
    (r'\bbanch[ei]?\b|\bbench\b|\bpew\b', 'Set Dressing', 'panca'),
    (r'\bpalco\b|\bstage\b|\bplatform\b', 'Set Dressing', 'palco'),
    (r'\baltare\b|\baltar\b', 'Set Dressing', 'altare'),
    (r'\bfonte\b(?:\s+battesimale)?\b|\bfont\b', 'Set Dressing', 'fonte battesimale'),
    (r'\bcrocefisso\b|\bcrucifix\b|\bcross\b', 'Set Dressing', 'crocifisso'),
    (r'\bstatua\b|\bstatue\b|\bscultura\b|\bsculpture\b', 'Set Dressing', 'statua'),
    (r'\bfrigorifero\b|\bfridge\b|\brefrigerator\b', 'Set Dressing', 'frigorifero'),
    (r'\bcucin[ae]?\b(?!\s+(?:italiano|ristorante))\b|\bkitchen\b', 'Set Dressing', 'cucina'),
    (r'\bvasca\b(?:\s+da\s+bagno)?\b|\bbathtub\b|\bbath\b', 'Set Dressing', 'vasca da bagno'),
    (r'\btoilet\b|\bwc\b|\blavandino\b|\bsink\b', 'Set Dressing', 'sanitari'),
    (r'\bscrittoio\b|\bwriting table\b', 'Set Dressing', 'scrittoio'),
    (r'\bfax\b|\bphotocopier\b|\bfotocopiatrice\b', 'Set Dressing', 'fotocopiatrice'),
    (r'\btelefon[oo]\s+(?:fisso|da\s+tavolo)\b|\blandline\b', 'Set Dressing', 'telefono fisso'),
    (r'\bcoffee\s+table\b|\btavolino\b', 'Set Dressing', 'tavolino'),
    (r'\bpodi[oo]\b|\bpodium\b|\bleggio\b|\blectern\b', 'Set Dressing', 'podio'),
    (r'\bschermo\b|\bschermo\s+proiezione\b|\bprojection screen\b', 'Set Dressing', 'schermo'),
    (r'\bproiettore\b|\bprojector\b', 'Set Dressing', 'proiettore'),
    (r'\blavagna\b|\bblackboard\b|\bwhiteboard\b', 'Set Dressing', 'lavagna'),
    (r'\bmappe?\b|\bmap\b(?!\s+(?:address|route))\b|\bcarta\s+geografica\b', 'Set Dressing', 'mappa'),

    # ════════════════════════════════════════════════════════════════════
    # GREENERY — Piante e vegetazione scenografica
    # ════════════════════════════════════════════════════════════════════

    (r'\balberi?\b|\btrees?\b|\boak\b|\bpino\b|\bpine\b', 'Greenery', 'alberi'),
    (r'\bpiante?\b(?!\s+(?:industriale|bassa|piano))\b|\bplants?\b', 'Greenery', 'piante'),
    (r'\brosai?\b|\brose\s+bush\b', 'Greenery', 'rosai'),
    (r'\bsiepe\b|\bhedge\b', 'Greenery', 'siepe'),
    (r'\bpalm[ae]?\b|\bpalm\s+tree\b', 'Greenery', 'palma'),
    (r'\berba\b|\bgrass\b|\blawn\b|\bprato\b', 'Greenery', 'erba/prato'),
    (r'\bmuschio\b|\bmoss\b', 'Greenery', 'muschio'),
    (r'\bgiungla\b|\bjungle\b|\bforesta\b|\bforest\b', 'Greenery', 'vegetazione giungla'),
    (r'\bcespugli?\b|\bbush(?:es)?\b|\bshrubs?\b', 'Greenery', 'cespugli'),
    (r'\brami?\b|\bbranches?\b', 'Greenery', 'rami'),
    (r'\bfoglie?\b|\bleaves\b|\bfoliage\b', 'Greenery', 'foglie'),

    # ════════════════════════════════════════════════════════════════════
    # MUSIC — Musica e sound design creativo
    # ════════════════════════════════════════════════════════════════════

    (r'\bmusica\b(?!\s+(?:di\s+sottofondo))\b|\bmusic\b', 'Music', 'musica'),
    (r'\bcanzoni?\b|\bsong\b|\btune\b|\bhit\b', 'Music', 'canzone'),
    (r'\bmelodi[ae]?\b|\bmelody\b', 'Music', 'melodia'),
    (r'\banda\b(?:\s+(?:musicale|jazz|rock))?\b|\bband\b', 'Music', 'banda'),
    (r'\borchestr[ae]?\b|\borchestra\b|\bphilharmonic\b', 'Music', 'orchestra'),
    (r'\bcoro\b|\bchoir\b|\bchorus\b', 'Music', 'coro'),
    (r'\bchitarr[ae]?\b|\bguitar\b', 'Music', 'chitarra'),
    (r'\bviolino\b|\bviolin\b|\bfiddle\b', 'Music', 'violino'),
    (r'\bvioloncell[oo]\b|\bcello\b', 'Music', 'violoncello'),
    (r'\bsassofo(?:no)?\b|\bsaxophone\b|\bsax\b', 'Music', 'sassofono'),
    (r'\btromb[ae]?\b|\btrumpet\b|\btrombone\b', 'Music', 'tromba'),
    (r'\bbatter[iie]?\b(?!\s+(?:AA|auto))\b|\bdrums?\b|\bdrum\s+kit\b', 'Music', 'batteria'),
    (r'\bjukebox\b', 'Music', 'jukebox'),
    (r'\bstereo\b|\bhi-?fi\b|\bimpianto\s+audio\b', 'Music', 'impianto stereo'),
    (r'\bmicrofono\b(?!\s+boom)\b|\bmicrophone\b(?!\s+boom)', 'Music', 'microfono'),
    (r'\bgiradischi\b|\bturntable\b|\bvinile\b|\bvinyl\b', 'Music', 'giradischi'),
    (r'\bconcert[oo]\b|\bconcert\b|\bperformance\b', 'Music', 'concerto'),

    # ════════════════════════════════════════════════════════════════════
    # SOUND — Sound design tecnico (diverso da Music)
    # ════════════════════════════════════════════════════════════════════

    (r'\bplayback\b', 'Sound', 'playback'),
    (r'\bmicrofono\s+boom\b|\bboom\s+mic\b|\bboom\s+pole\b', 'Sound', 'microfono boom'),
    (r'\bregistrazione\s+(?:audio|sonora)\b|\baudio\s+recording\b', 'Sound', 'registrazione audio'),
    (r'\beffetti\s+sonori\b|\bsound\s+effects\b|\bsfx\b(?!\s+(?:makeup|special))', 'Sound', 'effetti sonori'),
    (r'\bfoley\b', 'Sound', 'foley'),

    # ════════════════════════════════════════════════════════════════════
    # SPECIAL FX — Effetti speciali fisici
    # ════════════════════════════════════════════════════════════════════

    (r'\bfuoco\b|\bfiamme?\b|\bfire\b|\bflames?\b', 'Special FX', 'fuoco/fiamme'),
    (r'\besplosion[ei]?\b|\bexplosion\b|\bblast\b', 'Special FX', 'esplosione'),
    (r'\bpirotech(?:nia|nico)\b|\bpyrotechnics?\b', 'Special FX', 'pirotecnica'),
    (r'\bfumo\b(?!\s+(?:di\s+sigaretta|passivo))\b|\bsmoke\b(?!\s+screen)', 'Special FX', 'fumo speciale'),
    (r'\bghiacci[oo]\b(?!\s+(?:nel\s+bicchiere))\b|\bice\s+effect\b', 'Special FX', 'effetto ghiaccio'),
    (r'\bpolvere\b(?:\s+da\s+sparo)\b|\bgunpowder\b|\bpowder\s+effect\b', 'Special FX', 'polvere da sparo'),
    (r'\bsangue\b(?:\s+(?:finto|artificiale))?\b|\bblood\s+effect\b|\bfake\s+blood\b', 'Special FX', 'sangue finto'),
    (r'\bpioggia\s+artificiale\b|\brain\s+machine\b|\brain\s+effect\b', 'Special FX', 'pioggia artificiale'),
    (r'\bneve\s+artificiale\b|\bsnow\s+machine\b|\bfake\s+snow\b', 'Special FX', 'neve artificiale'),
    (r'\bvento\b(?:\s+artificiale)\b|\bwind\s+machine\b', 'Special FX', 'vento artificiale'),

    # ════════════════════════════════════════════════════════════════════
    # MECHANICAL FX — Effetti meccanici e scenotecnica
    # ════════════════════════════════════════════════════════════════════

    (r'\btrapdoor\b|\bbotola\b', 'Mechanical FX', 'botola'),
    (r'\brig\b(?:\s+(?:di\s+caduta|per\s+stunt))?\b|\bfall\s+rig\b', 'Mechanical FX', 'rig caduta'),
    (r'\bwire\b(?:\s+work)?\b|\bwire\s+stunt\b|\bcavi\s+per\s+volo\b', 'Mechanical FX', 'wire work'),
    (r'\bcatapulta\b|\bcatapult\b', 'Mechanical FX', 'catapulta'),
    (r'\bspruzzatore\b|\bwater\s+jet\b|\bsprinkler\b', 'Mechanical FX', 'spruzzatore'),
    (r'\bscenografia\s+mobile\b|\bmoving\s+set\b', 'Mechanical FX', 'scenografia mobile'),
    (r'\bporta\s+(?:a\s+scatto|blindata|segreta)\b|\bsecret\s+door\b', 'Mechanical FX', 'porta meccanica'),

    # ════════════════════════════════════════════════════════════════════
    # VFX — Visual Effects / CGI
    # ════════════════════════════════════════════════════════════════════

    (r'\bgreen\s*screen\b|\bchroma\s*key\b|\bchromakey\b', 'VFX', 'green screen'),
    (r'\bcgi\b|\bcomputer\s*generated\b', 'VFX', 'CGI'),
    (r'\bblue\s*screen\b', 'VFX', 'blue screen'),
    (r'\bvfx\b|\bvisual\s+effects?\b', 'VFX', 'VFX'),
    (r'\bcompositing\b|\bcomp(?:osit)?\b', 'VFX', 'compositing'),
    (r'\brotoscopio\b|\brotoscoping\b|\brotoscope\b', 'VFX', 'rotoscoping'),
    (r'\bde-?aging\b|\bde.?aged\b', 'VFX', 'de-aging digitale'),
    (r'\bde-?hazing\b|\bcielo\s+artificiale\b', 'VFX', 'cielo digitale'),

    # ════════════════════════════════════════════════════════════════════
    # STUNTS — Cascate e acrobazie
    # ════════════════════════════════════════════════════════════════════

    (r'\bstunt\b|\bcascad[eou]\b|\bcontrofigura\b|\bstunt\s+double\b', 'Stunts', 'stunt'),
    (r'\bcombattimento\b|\bfight\b(?!\s+(?:scene|sequence))', 'Stunts', 'combattimento'),
    (r'\brissa\b|\bbrawl\b|\bfistfight\b', 'Stunts', 'rissa'),
    (r'\bpugni?\b|\bpunch(?:es)?\b', 'Stunts', 'pugni'),
    (r'\bschiaffi?\b|\bslap\b', 'Stunts', 'schiaffi'),
    (r'\bpicchia\b|\bpicchiano\b|\beats?\s+up\b', 'Stunts', 'picchia'),
    (r'\baggredisce\b|\bassaults?\b|\battacks?\b', 'Stunts', 'aggressione'),
    (r'\binseguimento\b|\bcar\s+chase\b|\bchase\s+scene\b', 'Stunts', 'inseguimento'),
    (r'\bcaduta\b(?!\s+(?:di\s+prezzi|dei\s+capelli))\b|\bfall\b(?!\s+(?:season|semester))', 'Stunts', 'caduta'),
    (r'\btuffo\b|\bjump\b|\bleap\b', 'Stunts', 'salto/tuffo'),
    (r'\bcolpo\s+di\s+testa\b|\bheadbutt\b', 'Stunts', 'colpo di testa'),

    # ════════════════════════════════════════════════════════════════════
    # SPECIAL EQUIPMENT — Attrezzatura tecnica di ripresa speciale
    # ════════════════════════════════════════════════════════════════════

    (r'\bdrone\b|\buav\b|\bquadcoptore\b', 'Special Equipment', 'drone'),
    (r'\bsteadicam\b|\bstabilizzatore\b|\bgimbal\b', 'Special Equipment', 'steadicam'),
    (r'\bgru\b(?:\s+(?:da\s+ripresa|telescopica|cinematografica))?\b|\bcrane\b(?!\s+shot)', 'Special Equipment', 'gru da ripresa'),
    (r'\bcarrellata\b|\bdolly\b|\btracking\s+shot\b', 'Special Equipment', 'carrellata/dolly'),
    (r'\bjib\b|\bjib\s+arm\b', 'Special Equipment', 'jib arm'),
    (r'\bslider\b(?:\s+(?:video|camera))?\b', 'Special Equipment', 'slider'),
    (r'\bunderwater\s+(?:camera|housing)\b|\briprese\s+subacquee\b', 'Special Equipment', 'attrezzatura subacquea'),
    (r'\bteleobjettivo\b|\btelephoto\b|\bzoom\s+lens\b', 'Special Equipment', 'teleobiettivo'),

    # ════════════════════════════════════════════════════════════════════
    # MAKEUP — Trucco e parrucco
    # ════════════════════════════════════════════════════════════════════

    (r'\bparrucca\b|\bwig\b', 'Makeup', 'parrucca'),
    (r'\bprotesi\b(?!\s+(?:arto|ortopedica))\b|\bprosthetic\b|\bprosthetics\b', 'Makeup', 'protesi'),
    (r'\bteatrale\b(?:\s+trucco)?\b|\bstage\s+makeup\b', 'Makeup', 'trucco teatrale'),
    (r'\btrucc(?:o|atore)\b(?!\s+(?:di\s+luce|cine))\b|\bmakeup\b|\bmake-?up\b', 'Makeup', 'trucco'),
    (r'\beffetto\s+(?:invecchiamento|aging)\b|\baging\s+makeup\b', 'Makeup', 'trucco invecchiamento'),
    (r'\bferite?\s+(?:finte|artificiali)\b|\bwound\s+makeup\b|\bfake\s+wounds?\b', 'Makeup', 'ferite finte'),
    (r'\btatuaggi?\b|\btattoos?\b(?:\s+finti)?\b', 'Makeup', 'tatuaggi'),
    (r'\bbaffi\b|\bbarbetta\b|\bbeard\b|\bmoustache\b', 'Makeup', 'barba/baffi posticci'),

    # ════════════════════════════════════════════════════════════════════
    # LIVESTOCK — Animali
    # ════════════════════════════════════════════════════════════════════

    (r'\bcavallos?\b|\bhorse\b|\bhorse(?:s)?\b|\bmare\b', 'Livestock', 'cavallo'),
    (r'\bcane\b(?!\s+(?:finto|da\s+guardia\s+robotico))\b|\bdog\b|\bpuppy\b|\bcucciolo\b', 'Livestock', 'cane'),
    (r'\bgatt(?:o|i|ino|ina|ini|ine)\b|\bcat\b|\bkitten\b', 'Livestock', 'gatto'),
    (r'\banim[ae]l[ie]?\b|\banimals?\b', 'Livestock', 'animale'),
    (r'\buccell[oi]\b(?!\s+(?:di\s+ferro))\b|\bbird\b|\bdove\b|\bcolomb[ae]?\b', 'Livestock', 'uccello'),
    (r'\bconiglio\b|\brabbit\b', 'Livestock', 'coniglio'),
    (r'\bserp[ei]\b|\bsnake\b|\bboa\b', 'Livestock', 'serpente'),
    (r'\btoro\b|\bbull\b|\bbue\b|\box\b', 'Livestock', 'toro'),
    (r'\bvacca\b|\bmucca\b|\bcow\b', 'Livestock', 'mucca'),
    (r'\bpecora\b|\bsheep\b|\blamb\b|\bagnello\b', 'Livestock', 'pecora'),
    (r'\bmaiale\b|\bpig\b|\bswine\b|\bporco\b', 'Livestock', 'maiale'),
    (r'\bgallin[ae]?\b|\bchicken\b|\bhens?\b', 'Livestock', 'gallina'),
    (r'\bgallo\b(?!\s+(?:da\s+combattimento\s+reale|del\s+campione))\b|\brooster\b', 'Livestock', 'gallo'),
    (r'\bcapra\b|\bgoat\b', 'Livestock', 'capra'),

    # ════════════════════════════════════════════════════════════════════
    # ANIMAL HANDLERS — Addestratori animali
    # ════════════════════════════════════════════════════════════════════

    (r'\baddestrator[ei]?\b|\btrainer\b(?:\s+(?:animale|animal))?\b', 'Animal Handlers', 'addestratore'),
    (r'\banimal\s+handler\b|\bgestori?\s+animali\b', 'Animal Handlers', 'animal handler'),
    (r'\bdomatori?\b|\btamer\b', 'Animal Handlers', 'domatore'),
    (r'\bfalconieri?\b|\bfalconer\b', 'Animal Handlers', 'falconiere'),

    # ════════════════════════════════════════════════════════════════════
    # EXTRAS — Comparse e figuranti
    # ════════════════════════════════════════════════════════════════════

    (r'\bfigurant[ei]\b|\bextra\b', 'Extras', 'figurante'),
    (r'\bcomparsa\b|\bcomparse\b', 'Extras', 'comparsa'),
    (r'\bfolla\b|\bcrowd\b|\bmassa\b', 'Extras', 'folla'),
    (r'\bpassant[ie]\b|\bpassersby\b|\bpedestrians?\b', 'Extras', 'passanti'),
    (r'\banzian[io]\b|\belderly\b', 'Extras', 'anziani'),
    (r'\bturisti?\b|\btourists?\b', 'Extras', 'turisti'),

    # ════════════════════════════════════════════════════════════════════
    # SECURITY — Sicurezza sul set
    # ════════════════════════════════════════════════════════════════════

    (r'\bguardia\s+(?:del\s+corpo|di\s+sicurezza)\b|\bbodyguard\b|\bsecurity\s+guard\b', 'Security', 'guardia di sicurezza'),
    (r'\bcoordinator[ei]?\s+(?:di\s+sicurezza|sicurezza)\b|\bsafety\s+coordinator\b', 'Security', 'coordinatore sicurezza'),
    (r'\bmedico\s+(?:di\s+set|sul\s+set)\b|\bset\s+medic\b|\bparamedic\b', 'Security', 'medico di set'),
    (r'\bvigili?\s+(?:del\s+fuoco|fuoco)\b|\bfirefighter\b|\bfire\s+crew\b', 'Security', 'vigili del fuoco'),
    (r'\bpolizia\b(?!\s+(?:auto|macchina|car))\b|\bpolice\b(?!\s+(?:car|station))', 'Security', 'polizia'),
    (r'\bmetal\s+detector\b', 'Security', 'metal detector'),

    # ════════════════════════════════════════════════════════════════════
    # ADDITIONAL LABOR — Manodopera aggiuntiva
    # ════════════════════════════════════════════════════════════════════

    (r'\boperai?\b(?!\s+(?:portuali|stagione))\b|\bworkers?\b|\blaborers?\b', 'Additional Labor', 'operai'),
    (r'\belettrici(?:sti)?\b|\belectricians?\b|\bgaffer\b', 'Additional Labor', 'elettricisti'),
    (r'\bfalegname\b|\bcarpenter\b|\bjoiner\b', 'Additional Labor', 'falegname'),
    (r'\bscenografi\b|\bset\s+builders?\b|\bset\s+designer\b', 'Additional Labor', 'scenografi'),
    (r'\bpit\s+crew\b|\bequipe\s+meccanica\b', 'Additional Labor', 'pit crew'),
    (r'\bportantini?\b|\bporter\b|\bstretcher\s+bearer\b', 'Additional Labor', 'portantini'),
    (r'\bsubacquei?\b|\bdivers?\b|\bscuba\b', 'Additional Labor', 'sommozzatori'),
    (r'\bpilot[ai]?\s+(?:professionista|acrobatico)\b|\bstunt\s+pilot\b', 'Additional Labor', 'pilota acrobatico'),

    # ════════════════════════════════════════════════════════════════════
    # INTIMACY — Scene di intimità
    # ════════════════════════════════════════════════════════════════════

    (r'\bintimacy\s+coordinator\b|\bcoordinatore\s+di\s+intimità\b', 'Intimacy', 'intimacy coordinator'),
    (r'\bscena\s+di\s+sesso\b|\bsex\s+scene\b', 'Intimacy', 'scena di sesso'),
    (r'\bnudo\b|\bnudità\b|\bnudity\b|\bnude\b', 'Intimacy', 'nudità'),
    (r'\bscena\s+d\'amore\b|\blove\s+scene\b|\bscena\s+romantica\b', 'Intimacy', 'scena d\'amore'),
    (r'\bintimità\b|\bintimacy\b', 'Intimacy', 'intimità'),
    (r'\bset\s+chiuso\b|\bclosed\s+set\b', 'Intimacy', 'set chiuso'),
    (r'\bmodesty\s+(?:garment|patch)\b|\bprotettore\s+di\s+modestia\b', 'Intimacy', 'modesty garment'),
]


class DynamicPatternMatcher:

    _BUILTIN_COMPILED = None  # cache class-level

    def __init__(self, extra_patterns=None):
        if DynamicPatternMatcher._BUILTIN_COMPILED is None:
            DynamicPatternMatcher._BUILTIN_COMPILED = [
                (re.compile(pat, re.IGNORECASE), cat, name)
                for pat, cat, name in _RAW_PATTERNS
            ]

        self._extra = []
        for pattern_str, category in (extra_patterns or []):
            self._extra.append((
                re.compile(pattern_str, re.IGNORECASE),
                category,
                None
            ))

    def load_patterns(self, patterns):
        self._extra = []
        for pattern_str, category in patterns:
            self._extra.append((
                re.compile(pattern_str, re.IGNORECASE),
                category,
                None
            ))

    def _name_with_context(self, text, match, canonical_name):
        base = canonical_name if canonical_name else match.group(0).strip()
        if not base:
            return None

        pre_qualifier = None
        post_qualifier = None

        before = text[:match.start()]
        pre_m = _PRE_WORD_RE.search(before)
        if pre_m:
            w = pre_m.group(1)
            if w.lower() not in _STOPWORDS and len(w) > 2 and w.islower():
                pre_qualifier = w

        after = text[match.end():]
        post_m = _POST_WORD_RE.match(after)
        if post_m:
            w = post_m.group(1)
            if w.lower() not in _STOPWORDS and len(w) > 2 and w.islower():
                post_qualifier = w

        parts = []
        if pre_qualifier:
            parts.append(pre_qualifier)
        parts.append(base)
        if post_qualifier:
            parts.append(post_qualifier)
        return ' '.join(parts)

    async def find(self, text):
        if not text:
            return []

        results = []
        seen = set()

        all_patterns = DynamicPatternMatcher._BUILTIN_COMPILED + self._extra

        for regex, category, canonical_name in all_patterns:
            for m in regex.finditer(text):
                name = self._name_with_context(text, m, canonical_name)
                if not name:
                    continue
                key = (category, name.lower())
                if key in seen:
                    continue
                seen.add(key)

                e = SceneElement()
                e.element_name = name
                e.category = category
                e.ai_suggested = 1
                e.ai_confidence = _PATTERN_CONFIDENCE
                e.detection_method = "pattern"
                results.append(e)

        return results
