# Név és arculati elemek

A forráskód MIT-licence nem ad engedélyt a KJBK Infinity nevének, védjegyeinek és eredeti logóinak szabad felhasználására. Ezek a projekt eredeti megjelenésének dokumentálására maradtak a repóban. Egy fork létrehozásához nem kell őket törölni, de **saját telepítés és továbbadott alkalmazás előtt cseréld őket a saját arculatodra**. Ne keltsd azt a benyomást, hogy a változatot a KJBK üzemelteti vagy támogatja.

Az érintett eredeti és származtatott arculati fájlok:

- `frontend/public/brand/*.png`: teljes és önálló logó, világos és negatív változat.
- `frontend/public/icon.svg`, `icon-192.png`, `icon-512.png`, `icon-maskable.png`: az arculati jelet tartalmazó alkalmazásikonok.
- A dokumentáció képernyőképein látható KJBK-logók.

Átnevezés és csere:

1. Cseréld a négy logóképet, az ikonokat és a `frontend/public/manifest.webmanifest` nevét, leírását.
2. A `frontend/src/Brand.tsx`, `frontend/index.html`, `frontend/public/sw.js`, `templates/login.html`, `templates/oauth2_provider/base.html` és `templates/notifications/` fájlokban írd át a megjelenő nevet és képleírásokat. További helyek keresése: `rg -n 'kjbk|KJBK' frontend templates core`.
3. A `frontend/src/style.css` színváltozóit és a natív belépőoldal `templates/appearance.html` színeit a saját arculatodhoz igazíthatod. A `frontend/public/theme-init.js` téma-színeit is frissítsd.
4. A saját feladócímet és feladónevet a `.env` `DEFAULT_FROM_EMAIL` értékében add meg. Fordítsd újra a frontendet és gyűjtsd újra a statikus fájlokat.

A szolgáltatás-, adatbázis- és volume-nevekben lévő `kozos` technikai azonosítók átnevezése nem szükséges az arculat cseréjéhez.
