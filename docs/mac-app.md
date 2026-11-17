# GURU Mac-alkalmazás

A Mac 0.1.2 a megszokott GURU-felületet natív AppKit-ablakban jeleníti meg. Natív eszköztár, menük, fájlválasztó, mentési ablak, rendszerértesítések, menüsoros elérés és Dock-jelvény egészíti ki. Ugyanazt a szervert és fiókot használja, mint a web; helyi feladat-adatbázist nem hoz létre.

[Mac 0.1.2 letöltése](https://github.com/kobak/kjbk-projekt-guru/releases/download/v1.6.2/kjbk-projekt-guru-mac-0.1.2.zip) · Intel és Apple Silicon, macOS 14+

A 0.1.2 az új Mac-kiadásokat is jelzi, és tartalmazza a 0.1.1 melléklet- és naptárletöltési javítását. **A 0.1.1 és korábbi appok még nem tudnak frissítést jelezni:** ezt a változatot egyszer kézzel kell telepíteni. Frissítéshez lépj ki az appból (⌘Q), majd az új példánnyal cseréld le a régit az Alkalmazások mappában. A bejelentkezés és a Mac-beállítások megmaradnak.

## Frissítésjelzés

- Alapból automatikusan ellenőriz, induláskor, majd naponta; a sikeres ellenőrzések között legalább 24 óra telik el. A háttérben futó app is ellenőriz, alvás után folytatja. Kikapcsolt app nem tud jelezni.
- Az új verziót natív ablak jelzi **Letöltés / Újdonságok / Később** gombokkal. Egy adott verzió automatikus ablakát egyszer mutatja; a menüben és a Mac-beállításokban a frissítés utána is elérhető.
- Ha az app háttérben van, és a natív Mac-értesítések engedélyezettek, rendszerértesítést is küld. Engedély nélkül a következő megnyitáskor az alkalmazáson belül jelez. Az appablakhoz nem kell értesítési engedély.
- A **kjbk projekt guru → Frissítések keresése…**, a menüsoros GURU-menü és a **Mac-beállítások** bármikor indíthat kézi ellenőrzést. Az automatikus ellenőrzés itt külön kikapcsolható.
- A letöltést és a telepítést a felhasználó indítja. Nincs automatikus csere vagy újraindítás; a folyamatban levő munka megmarad.
- Hálózati hiba csendes automatikus újrapróbálást jelent, nem GURU-kapcsolati hibát. Kézi ellenőrzésnél érthető hibaüzenet jelenik meg. A GitHub korlátozása esetén megvárja az újrapróbálási időt.

A nyilvános GitHub-kiadások Mac ZIP-csomagjait ellenőrzi, a webes kiadás verziószámától függetlenül. Előzetes, vázlatos vagy feltöltés alatt álló csomagot nem ajánl fel, és régebbi verzióra nem irányít. A GitHub-kérés nem használ GURU-sütit, jelszót vagy GitHub-tokent. Az elérhető verzió és a jelzés állapota helyi Mac-beállításként tárolódik.

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
python3 macos/build.py --server-url https://projekt.sajatdomain.hu --output macos/build-sajat
```

Elkülönített fejlesztői azonosítóval, kizárólag loopback HTTP-re:

```sh
python3 macos/build.py --development --server-url http://127.0.0.1:8000 --architecture arm64 --output macos/build-qa
```

Az értesítési próbaappot se `/tmp` vagy `/var/folders` alól indítsd: a macOS ott megtagadhatja az értesítési kliens azonosítását. Használj a saját mappádban levő buildkönyvtárat vagy az Alkalmazások mappát.

Legalább GURU **1.4.0** szerver szükséges. Saját telepítéshez a KJBK arculat a [BRANDING.md](../BRANDING.md) szerint cserélendő.

## Új Mac-kiadás közzététele

1. Emeld a `version` és a `CFBundleVersion` értékét a `macos/build.py` fájlban. A Mac-verzió három számból álljon, például `0.1.3`. A webes kiadás ettől eltérő számot kaphat.
2. Futtasd a `sh macos/test.sh` ellenőrzést és az univerzális `python3 macos/build.py` fordítást. A ZIP-ben a kész `.app`, a licenc és a márkajelzési szabály legyen; ellenőrizd a kicsomagolt app aláírását is.
3. Készíts nyilvános GitHub-kiadást, először vázlatként. A Mac-csomag neve pontosan `kjbk-projekt-guru-mac-<Mac-verzió>.zip` legyen. Mellékeld a SHA-256 ellenőrzőösszeget és a telepítési leírást.
4. A sikeres CI és ellenőrzött csomag után publikáld a kiadást **előzetes kiadás jelölés nélkül**. A következő automatikus vagy kézi ellenőrzés felismeri. Egy csak webes kiadás nem számít új Mac-verziónak.

Saját szerverre fordítva alapból nincs kapcsolat a KJBK kiadásaival, így a felhasználó nem kaphat a saját szervere helyett a KJBK-szerverre irányító appot. Saját nyilvános kiadásokhoz:

```sh
python3 macos/build.py --server-url https://projekt.sajatdomain.hu --update-repository sajatnev/sajatrepo --output macos/build-sajat
```

A `--update-repository none` a hivatalos szerverhez is letiltja a forrást. A saját kiadásban is a fenti Mac ZIP-névminta szükséges. A forrás csak `owner/repo` alakú lehet, a hivatkozások pedig ugyanannak a GitHub-repónak a HTTPS-oldalára mutathatnak.

Elkülönített ellenőrzéshez a fejlesztői fordítás szimulálhat egy korábbi verziót; a `--test-version` kizárólag `--development` mellett használható:

```sh
python3 macos/build.py --development --server-url http://127.0.0.1:8000 --update-repository kobak/kjbk-projekt-guru --test-version 0.1.0 --architecture arm64 --output macos/build-update-qa
```
