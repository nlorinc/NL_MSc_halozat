# Licencelés / Licensing

A repozitórium **eltérő jogállású** elemeket tartalmaz. Az itt megadott engedélyek kizárólag azokra az anyagokra terjednek ki, amelyekhez a szerzőnek megfelelő felhasználási és továbbengedélyezési joga van.

## 1. Saját elemzőkód – MIT

A következő, saját fejlesztésű forráskódok és a hozzájuk tartozó szoftverdokumentáció a gyökérkönyvtárban található [MIT-licenc](LICENSE) alatt érhetők el:

- `NL_MSc_halozat_GitHub.ipynb` – kód és saját módszertani jegyzetek;
- `utils/*.py` – segédmodulok;
- `prepublish_check.py` – közzététel előtti ellenőrző;
- az ezekhez tartozó saját technikai dokumentációk és konfigurációs állományok.

A licence csak a szerző saját, licencelhető hozzájárulásaira vonatkozik. Nem ad jogot harmadik fél kódjának, adatkészleteinek, márkajelzéseinek vagy a `public_figures/` SVG-fájljainak az MIT feltételei szerinti továbbterjesztésére. A szerzői jog jogosultja: **Nagy Lőrinc (2026)**, feltéve hogy az egyes fájlok tekintetében nem áll fenn más jogosult vagy külön szerződéses korlátozás.

## 2. Szöveges dokumentáció

A projekt eredeti, saját szöveges dokumentációja a fent megjelölt MIT-licenc szerint felhasználható; **alternatívaként** a szövegrészekre a [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) feltételei is alkalmazhatók, az eredeti szerző és forrás feltüntetésével. A más forrásból idézett szövegek, hivatkozások és harmadik felek anyagai nem kerülnek újralicencelésre.

## 3. SVG-ábrák – külön jogállás

**A `public_figures/` alatt található SVG-kre jelenleg nincs általános nyílt újrafelhasználási licenc megadva.** Nem vonatkozik rájuk a gyökérben található MIT-licenc vagy a dokumentáció CC BY 4.0 lehetősége.

A cél az önállóan létrehozott ábrák **CC BY 4.0** alatti közzététele, **de csak az adatforrások és az intézményi hozzáférési szerződés jogainak tisztázása után**. A részleteket a [`public_figures/LICENSE.md`](public_figures/LICENSE.md) tartalmazza.

A nyilvános megtekinthetőség, a tudományos dolgozatban történő közlés és a harmadik személyek részére kiadott, kereskedelmi felhasználást is megengedő CC BY 4.0 engedély **nem azonos jogi kérdés**.

## 4. Forrásadatok – kizárva

A Scopus- és SciVal-alapú nyers exportok, valamint a belőlük származó részletes szerzői, publikációs, intézményi és gráfadatok **nem részei a repozitóriumnak**, és nem vonatkozik rájuk az MIT vagy a CC BY 4.0 engedély. A tényleges felhasználási feltételeket az Elsevier és az adatokat biztosító intézmény közötti szerződés szabja meg. Lásd: [`DATA_ACCESS.md`](DATA_ACCESS.md).

A ROR-azonosítók és -metaadatok a ROR saját szabályai szerint **CC0 1.0** közkincs-felajánlás alatt érhetők el; a ROR webhely szövegeire más feltételek vonatkoznak. Bizonyos földrajzi mezők GeoNames-eredetűek, amelyekhez forrásmegjelölési kötelezettség kapcsolódhat.

## 5. Felhasznált szoftverek és eszközök

A projektben használt Python, NetworkX és más csomagok, továbbá a Gephi és a JetBrains PyCharm **saját licencekkel** rendelkeznek. A repozitórium nem tartalmazza ezek teljes forráskódját, és a fenti engedélyek nem módosítják a külső függőségek jogállását.

A Gephi GPLv3/CDDL licence nem teszi automatikusan GPL-licencűvé az önálló, Gephivel készített SVG-ket. A PyCharm fejlesztőkörnyezete szintén nem írja elő a saját kód PyCharm-licenc alatti közzétételét.

## 6. Hivatkozás / Attribution

Ajánlott projektmegjelölés: **Nagy Lőrinc (2026), NL_MSc_halozat – University of Debrecen publication collaboration networks (2015–2024), GitHub**.

Adatforrásként szükség szerint jelölendő: **Scopus / SciVal (Elsevier)**, valamint **Research Organization Registry (ROR)**. A hivatkozás nem jelent licencet vagy újrafelhasználási jogot az adatforrásokra.

## 7. A nyilvános kiadás előtti feltételek

1. Az MIT alkalmazása előtt ellenőrizendő, hogy a szerző jogosult-e a saját kód nyílt licencelésére, és nincs-e közreműködői/intézményi jogosultság.
2. A 48 SVG adatforrás-jogainak és nyilvános terjeszthetőségének írásos tisztázása szükséges; a cél a CC BY 4.0.
3. A felhasznált Scopus/SciVal források pontos exportálási idejét és az adatszolgáltató által előírt forrásmegjelölést a végleges kiadáshoz dokumentálni kell.

---

*This repository uses an MIT license for the author's original code and associated software documentation. The SVG visualizations are excluded from that grant pending verification of the Scopus/SciVal data-use rights. Third-party datasets and dependencies retain their own terms.*
