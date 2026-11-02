# GURU Mac-alkalmazás

A Mac 0.1.0 a megszokott GURU-felületet natív AppKit-ablakban jeleníti meg. Natív eszköztár, menük, fájlválasztó, mentési ablak, rendszerértesítések, menüsoros elérés és Dock-jelvény egészíti ki. Ugyanazt a szervert és fiókot használja, mint a web; helyi feladat-adatbázist nem hoz létre.

## Első használat

1. Bontsd ki a Mac ZIP-et, és másold a `kjbk projekt guru.app` alkalmazást az Alkalmazások mappába.
2. Jelentkezz be a meglévő GURU e-mail-címeddel és jelszavaddal. A böngésző és az app külön bejelentkezést tárol.
3. **kjbk projekt guru → Mac-beállítások… → Natív Mac-értesítések**: az app kapcsolóját és a macOS engedélykérését is engedélyezni kell. A **Próbaértesítés** kizárólag helyi tesztjelzést jelenít meg.
4. Az eseményeket a GURU **Beállítások → Értesítések** oldalának **Push** oszlopában választhatod ki. Az e-mail-beállítások függetlenek.

Az Apple Developer-jóváhagyás előtti változat belső tesztelésre készült. Helyi ad hoc aláírást kap; Developer ID-aláírást és notarizációt még nem. Letöltés után a macOS külön jóváhagyást kérhet a megnyitáshoz, ezt a gép tulajdonosa végzi el. A rendszer biztonsági védelmét nem kell kikapcsolni. [Apple útmutató](https://support.apple.com/102445).

## Háttér és értesítések

A piros bezárógomb és **⌘W** bezárja az ablakot; az app a menüsorban tovább fut. Az új értesítéseket **15 másodpercenként** ellenőrzi. A Dock-ikon és a menüsoros **GURU megnyitása** visszahozza az ablakot. A **Kilépés / ⌘Q** teljesen leállítja az alkalmazást. Nem állít be automatikus indulást.

Alvó, kijelentkeztetett vagy internet nélküli Mac-en az új jelzések késnek; folytatáskor újra ellenőriz. A macOS Fókusz és értesítési beállításai is befolyásolják a megjelenést. Ez a háttérbeli ellenőrzés még nem APNs-push: azt, a Developer ID-aláírást és a notarizációt az Apple-jóváhagyás után külön kell bekötni.

Első bejelentkezéskor nem küldi ki az összes régi értesítést. Újraindításkor a saját fiók korábbi kurzorától folytat, legfeljebb az elmúlt hét még aktuális, olvasatlan eseményeit veszi figyelembe. A megjelenítés nem jelöl olvasottnak; a jelzéseket a GURU csengője alatt kezelheted. Fiókváltáskor eltávolítja az előző fiók helyi értesítéseit. Ha Safari és a Mac-app is jelez ugyanazon a gépen, két jelzést kaphatsz.

| Művelet | Elérés |
| --- | --- |
| Új feladat | ⌘N / eszköztár + |
| Keresés | ⌘K |
| Frissítés | ⌘R / körbeforduló nyíl |
| Mac-beállítások | ⌘, |
| Ablak bezárása, háttérben folytatás | ⌘W |
| Kilépés | ⌘Q |

A méretezés, teljes képernyő, ablakhelyzet, másolás/beillesztés és fájlválasztás a Mac szokásos vezérlőit használja. A GURU saját témája, betűmérete, sűrűsége és nézetbeállításai megmaradnak.

## Google-kapcsolatok

A Google korlátozza az OAuth-belépést fejlesztő által vezérelt beágyazott böngészőben. A naptár összekötése és a Drive-fájlválasztás ezért a rendszer böngészőjében nyílik meg, a megfelelő GURU-beállításnál vagy feladatnál. Ott szükség lehet külön GURU-belépésre. Visszatérés után a Mac-app **Frissítés** gombja betölti a változást. A már összekötött naptár feladatonkénti hozzáadása az appból is működik. A külső dokumentumok a rendszer böngészőjében nyílnak meg.

Az alkalmazás nem kerüli meg a Google korlátozásait, és nem másol Google-jelszót vagy -tokent más böngészőbe. [Google OAuth-szabályzat](https://developers.google.com/identity/protocols/oauth2/policies).

## Hozzáférés és értesítési API

A WebKit saját, tartós sütitárolója őrzi a bejelentkezést. A natív ellenőrzés csak a beállított GURU-eredet sütijeit használja, nem követ átirányítást és nem küld hitelesítést külső címre. A UserDefaults csak az értesítési kapcsolót és a szerver/fiók szerinti feldolgozási kurzort tárolja; jelszót vagy értesítésszöveget nem.

A `GET /api/desktop/notifications/` végpont bejelentkezést igényel, személyes és csak olvas. `after` nélkül alapkurzort ad, korábbi értesítések nélkül. `?after=<id>` legfeljebb 100 bejegyzést vizsgál; a nem releváns, olvasott, túl régi és a Push-oszlopban kikapcsolt értesítéseken is előrelépteti a kurzort. A `has_more` jelzi a következő lapot. Nem módosítja a webes push/e-mail küldési állapotát. API-frissítéshez nincs adatbázis-migráció.

## Fordítás

macOS 14+, Python 3 és Apple Command Line Tools szükséges. Teljes Xcode és külső Swift-csomag nem kell.

```sh
sh macos/test.sh
python3 macos/build.py
```

Eredmény: `macos/build/kjbk projekt guru.app`, univerzális `arm64` + `x86_64` bináris. A fordító AppKit, SwiftUI, WebKit és UserNotifications rendszerkeretrendszereket használ. A célmappában már létező appot nem írja felül.

Másik telepítéshez:

```sh
python3 macos/build.py --server-url https://projekt.sajatdomain.hu --output /tmp/guru-sajat-build
```

Elkülönített fejlesztői azonosítóval, kizárólag loopback HTTP-re:

```sh
python3 macos/build.py --development --server-url http://127.0.0.1:8000 --architecture arm64 --output /tmp/guru-qa
```

Legalább GURU **1.4.0** szerver szükséges. Saját telepítéshez a KJBK arculat a [BRANDING.md](../BRANDING.md) szerint cserélendő.
