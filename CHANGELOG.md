# Változásnapló

## 1.0.1 — 2026-10-30

- Az admin a Beállítások → Csapat fülön, a tag melletti ceruzával javíthatja az e-mail-címet. A belépési cím is frissül, a jelszó, feladatok és beállítások megmaradnak.
- Duplikált cím és párhuzamos szerkesztés ellenőrzése; a régi/új címhez tartozó fel nem használt meghívók visszavonása, adminnaplózás.
- A profil mentése és a tag letiltása nem írhatja vissza egy közben javított e-mail korábbi értékét.
- A sorban álló értesítések küldéskor az aktuális címzettet használják. A már elküldött leveleket a címcsere nem küldi újra.

## 1.0.0 — 2026-10-29

Az első nyilvános, saját szerveren futtatható kiadás.

- Közös projektek, feladatok, Kanban/lista/naptár és mobilnézet.
- Meghívásos belépés, felelősök, határidők, címkék, részfeladatok, hozzászólások és fájlok.
- Személyes Google Naptár-integráció; OAuth nélküli Google-eseménylink és `.ics` letöltés.
- OAuth + PKCE hitelesítésű MCP, olvasási/szerkesztési hatókörök, tokenrotáció és visszavonás.
- Egységes OAuth issuer a metaadatokban és az engedélyezési válaszokban, a Claude kompatibilitásához.
- Személyes értesítési beállítások: öt eseménytípushoz külön e-mail és push; SMTP újrapróbálás és elavult küldések kihagyása.
- Világos, sötét és rendszer szerinti megjelenés, fiókonkénti mentéssel.
- Telepítési, integrációs, mentési és visszaállítási útmutató; GitHub Actions tesztfolyamat.
- A saját kód MIT-licencű; a mellékelt KJBK-logók saját telepítéshez cserélendők.

Az aktuális korlátok és a még hiányzó funkciók a [README-ben](README.md#jelenlegi-határok) szerepelnek. Az Asana/Notion/Trello-import, az ismétlődés és az egyéni projektek nem részei ennek a kiadásnak.
