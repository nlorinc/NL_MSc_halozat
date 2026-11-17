# Ábragyűjtemény – Debreceni Egyetem (2015–2024)

A repozitórium e mappája a diplomamunka **48 SVG-ábráját** tartalmazza. A képek az eredeti fájlnevekkel és mappaszerkezettel szerepelnek; a nyers Scopus/SciVal-adatok és a Gephi-projektfájlok nincsenek itt.

Az ábrák a hálózatok és az elemzési eredmények szemléltetésére szolgálnak. A hálózati gráfok **publikációs együttműködési hálók**, nem hivatkozási/idézési hálók.

## Áttekintés

| Csoport | Ábrák száma |
| --- | ---: |
| Python, 25. fejezet | 11 |
| Gephi, teljes egyetemi szerzőháló | 3 |
| Gephi, karok közötti háló | 2 |
| Gephi, karon belüli hálók (6 kar × 5 színezés) | 30 |
| Gephi, külső intézményi hálók | 2 |
| **Összesen** | **48** |

## Python – 25. fejezet (11 SVG)

| Azonosító | Ábra | Fájl |
| --- | --- | --- |
| 25/01 | Kari hálózati ujjlenyomat (hőtérkép) | [SVG megnyitása](python/svg/fig_25_01_kari_halozati_ujjlenyomat_heatmap.svg) |
| 25/02 | K-magok szignatúragörbéi | [SVG megnyitása](python/svg/fig_25_02_kmag_szignaturagorbek.svg) |
| 25/03 | Integráció és medián h-index | [SVG megnyitása](python/svg/fig_25_03_integracio_median_hindex.svg) |
| 25/04 | Karok publikációszáma | [SVG megnyitása](python/svg/fig_25_04_karok_publikacioszama.svg) |
| 25/05 | Karok medián h-indexe | [SVG megnyitása](python/svg/fig_25_05_karok_median_hindex.svg) |
| 25/06 | Karok medián strength értéke | [SVG megnyitása](python/svg/fig_25_06_karok_median_strength.svg) |
| 25/07 | Publikációszám és h-index – mintakarok | [SVG megnyitása](python/svg/fig_25_07_pubcount_hindex_mintakarok.svg) |
| 25/08 | Strength és FWCI – mintakarok | [SVG megnyitása](python/svg/fig_25_08_strength_fwci_mintakarok_log.svg) |
| 25/09 | A DE legfontosabb nemzetközi országpartnerei | [SVG megnyitása](python/svg/fig_25_09_de_top_nemzetkozi_orszagpartnerek.svg) |
| 25/10 | Nem magyar országpartnerek karonként | [SVG megnyitása](python/svg/fig_25_10_nemmagyar_orszagpartnerek_karonkent.svg) |
| 25/11 | Karok súlyozott PageRank-értékei | [SVG megnyitása](python/svg/fig_25_11_karok_weighted_pagerank.svg) |

## Gephi – egyetemi szerzőháló (3 SVG)

| Színezés | Fájl |
| --- | --- |
| Egyetemi szerzőháló – karok szerint | [SVG megnyitása](gephi/Egyetem_osszes/svg/DE_szerzo-szerzo_karSzin.svg) |
| Egyetemi szerzőháló – KAT-besorolás | [SVG megnyitása](gephi/Egyetem_osszes/svg/DE_szerzo-szerzo_katSzin.svg) |
| Egyetemi szerzőháló – modularitás | [SVG megnyitása](gephi/Egyetem_osszes/svg/DE_szerzo-szerzo_modularitySzin.svg) |

## Gephi – kari együttműködési hálózat (2 SVG)

| Súlyozás | Fájl |
| --- | --- |
| Kari háló – tört súlyozás | [SVG megnyitása](gephi/Egyetem_kar-kar/svg/kar-kar_fract_midSlope.svg) |
| Kari háló – publikációszám | [SVG megnyitása](gephi/Egyetem_kar-kar/svg/kar-kar_pubcount_midSlope.svg) |

## Gephi – külső partnerintézmények (2 SVG)

| Nézet | Fájl |
| --- | --- |
| Hazai partnerintézményi hálózat | [SVG megnyitása](gephi/Egyetem-kulso_intezmenyek/DE-hazaiIntezmenyek.svg) |
| Országcsoportos külföldi partnerintézmények | [SVG megnyitása](gephi/Egyetem-kulso_intezmenyek/DE-orszag-kulfoldiIntezmenyek.svg) |

## Gephi – karon belüli szerzőhálók (30 SVG)

A hat feltöltött kari részgráf különböző csúcsszínezései. A rövidítések: **BC** = közvetítési centralitás; **WD** = súlyozott fokszám; **KAT** = összetett kategóriabesorolás.

| Kar | BC | h-index | KAT | Modularitás | WD |
| --- | --- | --- | --- | --- | --- |
| ÁOK | [SVG](gephi/Karon_beluli/%C3%81OK/%C3%81OK_BC.svg) | [SVG](gephi/Karon_beluli/%C3%81OK/%C3%81OK_H-ind.svg) | [SVG](gephi/Karon_beluli/%C3%81OK/%C3%81OK_kat.svg) | [SVG](gephi/Karon_beluli/%C3%81OK/%C3%81OK_modularity.svg) | [SVG](gephi/Karon_beluli/%C3%81OK/%C3%81OK_WD.svg) |
| TTK | [SVG](gephi/Karon_beluli/TTK/TTK_BC.svg) | [SVG](gephi/Karon_beluli/TTK/TTK_H-ind.svg) | [SVG](gephi/Karon_beluli/TTK/TTK_kat.svg) | [SVG](gephi/Karon_beluli/TTK/TTK_modularity.svg) | [SVG](gephi/Karon_beluli/TTK/TTK_WD.svg) |
| IK | [SVG](gephi/Karon_beluli/IK/IK_BC.svg) | [SVG](gephi/Karon_beluli/IK/IK_H-ind.svg) | [SVG](gephi/Karon_beluli/IK/IK_kat.svg) | [SVG](gephi/Karon_beluli/IK/IK_modularity.svg) | [SVG](gephi/Karon_beluli/IK/IK_WD.svg) |
| MK | [SVG](gephi/Karon_beluli/MK/MK_BC.svg) | [SVG](gephi/Karon_beluli/MK/MK_H-ind.svg) | [SVG](gephi/Karon_beluli/MK/MK_kat.svg) | [SVG](gephi/Karon_beluli/MK/MK_modularity.svg) | [SVG](gephi/Karon_beluli/MK/MK_WD.svg) |
| MÉKK | [SVG](gephi/Karon_beluli/M%C3%89KK/M%C3%89KK_BC.svg) | [SVG](gephi/Karon_beluli/M%C3%89KK/M%C3%89KK_H-ind.svg) | [SVG](gephi/Karon_beluli/M%C3%89KK/M%C3%89KK_kat.svg) | [SVG](gephi/Karon_beluli/M%C3%89KK/M%C3%89KK_modularity.svg) | [SVG](gephi/Karon_beluli/M%C3%89KK/M%C3%89KK_WD.svg) |
| GTK | [SVG](gephi/Karon_beluli/GTK/GTK_BC.svg) | [SVG](gephi/Karon_beluli/GTK/GTK_H-ind.svg) | [SVG](gephi/Karon_beluli/GTK/GTK_kat.svg) | [SVG](gephi/Karon_beluli/GTK/GTK_modularity.svg) | [SVG](gephi/Karon_beluli/GTK/GTK_WD.svg) |

## Fájlformátum és felhasználás

- **Csak SVG**: a nagy méretű eredeti PNG-exportokat nem mellékeltük. Az SVG-k vektoros formátumúak, de a 25/1-es hőtérkép két beágyazott raszteres képelemet tartalmaz.
- A teljes egyetemi szerzőháló három változata nagy (egyenként kb. 23,3 MiB), ezért szándékosan **nem ágyazzuk be mindhárom képet** ebbe a README-be. A fájlhivatkozások közvetlenül megnyithatók.
- A Gephi-ben kialakított elrendezés és színezés nem reprodukálható automatikusan kizárólag a Jupyter-notebookból; a különböző színezések ugyanazon hálózat nézetei.
- Az állományok eredetijét változatlanul megőriztük. A gépi feldolgozáshoz és az ellenőrzéshez lásd: [`figures_manifest.json`](figures_manifest.json).
- A nyilvános közzététel előtt a Scopus/SciVal-ból származtatott vizualizációk adatközlési feltételeit, valamint a választott ábralicencet külön ellenőrizni kell.

## Ellenőrzés és ismert feladat

- A 48 SVG XML-formátuma érvényes; a fájlokban nincs futtatható `<script>` vagy külső hivatkozás.
- A 25/3-as ábra „aktív szerző” tengelyfeliratának pontosítása még módszertani/szerkesztési ellenőrzést igényel; ha új SVG készül, a manifestet is frissíteni kell.
