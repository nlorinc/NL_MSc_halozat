# Debreceni Egyetem – tudományos együttműködési hálózatok (2015–2024)

**NL_MSc_halozat – MSc adattudományi diplomamunka · Python / NetworkX / Jupyter / Gephi**

*English summary:* This repository contains the Python analysis workflow for a master's thesis investigating publication-based co-authorship, faculty collaboration, and external institutional/country collaboration networks of the University of Debrecen, Hungary (2015–2024). The underlying Scopus/SciVal-derived source exports are not publicly redistributed.

## A projekt célja

A Debreceni Egyetem 2015–2024 közötti, kari adatforrásokkal lefedett publikációi alapján:

- szerző–szerző és kar–kar **együttműködési hálózatok** előállítása;
- külső partnerintézmények és a nemzetközi országkapcsolatok vizsgálata;
- hálózati mutatók számítása a NetworkX segítségével;
- a szerzők karon belüli, hálózati beágyazottságot és h-indexet kombináló KAT-besorolása;
- a számítások eredményeinek exportja Gephi-vizualizációhoz, illetve összehasonlító statisztikai ábrák készítése.

**Fontos:** az itt épített gráfok publikációs együttműködéseket vagy társszerzőségi kapcsolatokat írnak le; nem idézési hálózatok. A kari adatforrásokból összeállított vizsgálati minta nem azonos a Debreceni Egyetem teljes publikációs állományával.

## Hivatkozási adatállomány és módszertani keretek

A diplomamunkában használt, rögzített adatállomány ellenőrzési értékei:

| Mutató | Érték |
| --- | ---: |
| Kari forrásokból deduplikált publikációk | 8 223 |
| Végleges szerzői entitások | 7 288 |
| Több Scopus-profilt egyesítő szerzői entitások | 22 |
| Azonosított külső partnerintézmények | 5 180 |
| Külföldi országok/területek a közvetlen publikáció–ország adatokban | 145 |
| Legalább egy külföldi országot tartalmazó vizsgált publikációk | 3 808 |

Ezek a számok **az eredeti vizsgálati adatállomány referenciaeredményei**, nem a nyilvánosan letölthető repóból önmagukban előállítható eredmények.

A publikációs törzs az **EID-t részesíti előnyben**, hiánya esetén DOI-t, végső esetben sorazonosítót használ. A szerzők azonosítása és összevonása konzervatív. A szerzői szcientometriai mutatókat többprofilos összevonásnál egy kiválasztott forrásprofil képviseli, a különböző profilok mutatóit nem összegezzük.

Az országaggregációk közvetlenül a Scopus publikáció–ország mezőiből készülnek. Az intézmény–ország hozzárendelés ettől eltérő, ROR-elsődleges eljárás, publikációs konzisztenciaellenőrzéssel és konzervatív másodlagos becsléssel. A megmaradt feloldatlan/ellentmondásos intézmények módszertani korlátot jelentenek.

## A repozitórium szerkezete

```text
.
├── NL_MSc_halozat_GitHub.ipynb          # A publikálható, mentett kimenetektől megtisztított notebook
├── requirements.txt         # A szükséges Python-csomagok rögzített verziókkal
├── README.md
├── .gitignore
├── utils/
│   ├── __init__.py          # Üres inicializáló fájl (ajánlott)
│   ├── io_utils.py
│   ├── parse_utils.py
│   ├── affiliation_utils.py
│   ├── author_merge_utils.py
│   ├── network_utils.py
│   └── analysis_utils.py
└── public_figures/          # Kizárólag külön ellenőrzött és jóváhagyott végleges ábrák
```

Az alábbi könyvtárak **helyi futtatáskor szükségesek/keletkeznek, de nem részei a nyilvános repónak**:

```text
source_data/
├── DE_confirmed_authors*.xlsx
└── kari/
    └── Publications_of*.xlsx

data_out/
├── interim/                 # Köztes táblák, joblib-cache, ROR-cache, RAM-naplók
├── processed/               # Feldolgozott táblák, Gephi-CSV-k, GEXF-ek, statisztikai ábrák
└── export/                  # Egyes exporttáblák

figures/                     # Egyéb helyi ábrák
```

A kari Excel-fájlokból a notebook a `Publications_of*.xlsx` mintára keres, a szerzőlista esetében pedig a `DE_confirmed_authors*.xlsx` mintát használja.

## Szoftverkörnyezet és telepítés

A projekt dokumentált referencia-környezete **Python 3.14.0**; a csomagverziókat a `requirements.txt` rögzíti. A fejlesztés Windows/PyCharm környezetben történt.

A repó klónozása után a **projekt gyökeréből**, virtuális környezetben:

**Windows (PowerShell):**

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Linux/macOS (telepített Python 3.14 esetén):**

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

A rögzített verziók telepíthetőségét és a teljes futást új, tiszta környezetben még külön ellenőrizni kell; a jelen dokumentum **nem állítja**, hogy a nyilvános repó önmagában teljesen reprodukálható.

## A notebook futtatása

1. Szerezd be az eredeti, megfelelő hozzáférési jogosultsággal felhasználható kari Scopus-exportokat és a DE-s szerzőlistát.
2. Helyezd el őket a fenti `source_data/` könyvtárban, a notebook által elvárt fájlnevekkel.
3. Indítsd a futtatást **a projekt gyökérkönyvtárából** (a notebook `ROOT = Path(".").resolve()` beállítást használja).

A következő parancs a teljes notebookot végrehajtja, és a futtatott változatot külön fájlba menti:

```powershell
python -m jupyter nbconvert --to notebook --execute "NL_MSc_halozat_GitHub.ipynb" --output "NL_MSc_halozat_GitHub_lefutott.ipynb" --ExecutePreprocessor.timeout=-1
```

A `timeout=-1` a cellafuttatási időkorlátot kapcsolja ki; **nem** oldja meg az esetleges memóriahiányt. A futtatáshoz a Python-környezetnek és az adatoknak rendelkezésre kell állniuk. A notebook időszakosan RAM-naplót is ír.

## ROR-gyorsítótár és ismételhetőség

A 9. fejezet a ROR v2 API segítségével próbálja azonosítani a külső intézményeket. A lekérdezések eredményeit itt tárolja:

`data_out/interim/ror_match_cache.csv`

A cache létezése nem kötelező az első lekérdezéshez: ha hiányzik, a 9/C cella hálózati lekérdezésekkel próbálja feltölteni. A 9/D **teljes intézményi lefedettséget** ellenőriz, ezért hiányos cache esetén nem folytatható a végső feldolgozás.

Az eredeti elemzés változatlan megismétléséhez a teljes, eredeti ROR-cache archiválása ajánlott. A nyilvános repó jelenleg nem tartalmazza ezt; új API-lekérdezésnél a ROR-adatbázis későbbi változásai befolyásolhatják az eredményeket. A lekérdezési dátumot és az archivált cache változatát a végső reprodukciós csomagban külön dokumentálni kell.

## Fő kimenetek

A notebook a következő állománycsoportokat állítja elő:

| Könyvtár | Tartalom |
| --- | --- |
| `data_out/processed/` | Publikáció-, szerző-, kari, intézményi és országaggregációs táblák |
| `data_out/processed/gephi/` | Gephi-kompatibilis csúcs- és éltáblák; külön KAT-szerzői csúcstábla |
| `data_out/processed/gephi/intezmenyi_nezetek/` | Hazai partnerintézményi és nemzetközi ország–intézmény GEXF 1.3 nézet |
| `data_out/processed/meta/` | Kari összehasonlító összesítések és szerzői metaadatok |
| `data_out/processed/figures/ch25_meta/` | **11 statisztikai ábra**, PNG (300 DPI) és SVG formátumban |
| `data_out/interim/` | Köztes feldolgozási adatok és ellenőrzési naplók |

A `data_out/` mappában keletkező adatok **alapértelmezésben nem kerülnek GitHubra**. A Gephi-ben kézzel véglegesített vizualizációk nem feltétlenül állíthatók elő csupán a notebook futtatásával: azokhoz külön Gephi-layout- és megjelenítési döntések tartoznak.

## Nagy felbontású ábrák

A [`public_figures/`](public_figures/README.md) mappa **48 SVG-ábrát** tartalmaz: a notebook 25. fejezetének 11 statisztikai ábráját és 37 Gephi-hálózatvizualizációt. Az ábrák külön hivatkozásokkal és csoportonkénti jegyzékkel érhetők el. Az eredeti PNG-exportokat nagy méretük miatt nem publikáljuk.

A teljes egyetemi szerzőháló egyes SVG-fájljai nagyok; a README nem jeleníti meg automatikusan az összes hálózatot. Az ábrákat a végleges szakdolgozatba **a megfelelő képfájlra mutató, kiadáshoz kötött hivatkozással** lehet megadni.

A nyilvános publikálás előtt a vizualizációk adatközlési és újrafelhasználási feltételeit külön ellenőrizni kell. Az ábrajegyzékben egy ismert feliratpontosítás is szerepel (25/3. ábra).

## Adatforrások és hozzáférési korlátozások

- **Scopus / SciVal:** intézményi hozzáférésből származó publikációs, szerzői és bibliometriai exportok. A nyers állományokat, részletes szerzői metrikákat és a belőlük előállított sor- vagy él-szintű táblákat ez a repó **nem terjeszti**.
- **Kari exportok:** a vizsgálati minta kialakításának bemenetei, nem részei a nyilvános csomagnak.
- **ROR:** az intézményazonosítás külső referenciaforrása; a lekérdezések a notebookból indíthatók.

A közzétételi jogosultságokat az alkalmazandó Scopus/SciVal-szerződés, az intézményi szabályok és a konkrét ábrákra vagy aggregátumokra vonatkozó feltételek szerint kell ellenőrizni. **A kód nyilvánossága nem jelent automatikus engedélyt a bemeneti adatok vagy minden származtatott adat továbbadására.** A reprodukcióhoz szükséges eredeti adatokat arra jogosult felhasználóknak saját hozzáférésükön keresztül kell beszerezniük.

## A módszer fő korlátai

- A kari forrásfájlok lefedettsége **nem egyenletes az évek között**; a minta nem tekinthető a teljes DE-kibocsátás véletlen vagy teljes körű mintájának.
- A szerzőazonosítás és -összevonás konzervatív; bizonytalan azonosítások maradnak.
- A szerzőháló betweenness-mutatóinak egy része mintavételes közelítés, rögzített random seeddel; a kari mutatók ettől eltérően teljes gráfon számolódnak.
- Az intézményi országfeloldás nem minden partner esetén sikeres, és az intézményországokból nem szabad a közvetlen publikáció–ország hálózatot visszakövetkeztetni.
- A KAT-kategóriák karon belüli kvartilishatárokra épülnek, holtverseny-kezeléssel; nem abszolút, karok között közvetlenül összevethető teljesítménymutatók.

## Publikálás előtti helyi ellenőrzés

A projekt gyökerében futtatható, csak szabványos Python-könyvtárakat használó ellenőrző:

```powershell
python prepublish_check.py
```

Az ellenőrző a forrásfájlok jelenlétét, a notebook tiszta kimenetét, a 25. fejezet ismert izoláltcsomópont-problémáját, a helyben előállított referenciaexportokat és a Git által már követett fájlokat vizsgálja. Nem tölt fel adatokat. A futtatási siker önmagában nem helyettesíti az eredményszintű ellenőrzést.

## Verziózás, idézés és licenc

A diplomamunkához tartozó végső, ellenőrzött kódállapotot később külön **GitHub release/tag** azonosítja. DOI-t (például Zenodo-archiválással) csak a végleges publikálás után érdemes hozzárendelni.

**Licenc:** a forráskódra vonatkozó licenc és a publikálható ábrák újrafelhasználási feltételei még nincsenek meghatározva; ezekről a nyilvános közzététel előtt külön kell dönteni. A korlátozott forrásadatok nem válnak a kódra választott licenc hatálya alatt szabadon újrahasznosíthatóvá.

---

*Állapot: GitHubra előkészített dokumentáció; a teljes, tiszta környezetű reprodukció, az adatterjesztési engedélyek és a publikálandó ábrák végső ellenőrzése még hátravan.*
