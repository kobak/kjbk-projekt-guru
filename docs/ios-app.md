# GURU iPhone-on és iPaden

Az első csapatpróba egy közös iOS- és iPadOS-alkalmazás. A GURU mobilos munkaterét jeleníti meg. A menü, a rendszerengedélyek, az értesítések és a letöltött fájlok megosztása natív. Az app a saját GURU-fiókoddal használható. A támogatott minimum iOS és iPadOS 18.

[iPhone-képernyőkép](images/guru-iphone-workspace.png) · [iPad-képernyőkép](images/guru-ipad-workspace.png)

## Kipróbálás a jóváhagyás előtt

Nyisd meg az `ios/Guru.xcodeproj` projektet Xcode-ban. Válaszd a **Guru** sémát, majd egy iPhone- vagy iPad-szimulátort, és nyomj ⌘R-t. Az alapértelmezett munkatér az a.kjbk.hu. Saját telepítéshez a `Guru.xcconfig` fájlban add meg a HTTPS-kiszolgálót és a saját bundle ID-t.

A felső **GURU menü → Helyi próbaértesítés** ponttal kérhetsz értesítést. Engedélyezd a rendszerkérdésben. A készülék két másodperc múlva jeleníti meg. Az éles feladatértesítésekhez külön szerverkapcsolat szükséges.

A közös felület és az értesítés megnyitásának szimulátortesztje eldobható adatbázist, demófelhasználót és kizárólag helyi címeket használ. A repó Python-környezetének és a lefordított frontendnek rendelkezésre kell állnia. Ha a gépen a Command Line Tools az aktív fejlesztői könyvtár, ugyanebben a terminálban futtasd az első sort is.

```sh
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
npm --prefix frontend run build
xcrun simctl list devices available
sh ios/test-simulator.sh SZIMULÁTOR-UUID
```

## Valódi feladatértesítések és TestFlight

1. Az Apple Developer-tagság aktiválása után regisztráld az app azonosítóját (az eredeti projektben `com.kjbkinfinity.guru.ios`), engedélyezd a **Push Notifications** képességet, és válaszd ki a szervezetet Xcode-ban a **Signing & Capabilities → Team** alatt.
2. Hozz létre az adott apphoz és környezethez használható APNs-kulcsot. A letöltött `.p8` a worker által olvasható, védett fájlba kerüljön. A kulcsot a vállalati titkokkal együtt mentsd. A forrásmentés a kulcs elérési útját tartalmazza.
3. A szerverre a mobilos változathoz tartozó frontendet és backendet is telepítsd a zárolt Python-függőségekkel. Futtasd a migrációkat. Az `.env.example` alapján add meg az `APNS_TEAM_ID`, `APNS_KEY_ID`, `APNS_KEY_FILE`, `APNS_TOPIC` és `APNS_ENVIRONMENT` értékét. Dockerben a kulcsot csak olvasható fájlként csatold a workerhez. Azonos környezetet és topicot állíts be a web- és worker-folyamatban, majd indítsd újra őket.
4. A Debug eszközbuildhez `sandbox`, a TestFlight Release buildhez `production` kell. Az első eszközpróbát fejlesztői környezetben végezd, majd Archive és az App Store Connect feltöltés után hívd meg a csapatot a TestFlightba.
5. Mindegyik készüléken külön jelentkezz be, és a GURU **Beállítások → Kapcsolatok** részén engedélyezd a push-t. Az egyes eseménytípusokat az **Értesítések → Push** oszlopban választhatod ki. Teszthez egy másik csapattag osszon rád feladatot, miközben a GURU a háttérben van. Az értesítésre koppintva a feladat nyílik meg.

A worker eszközönként követi a kézbesítést. Küldés előtt ellenőrzi a munkamenet érvényességét, a címzettet, az aktuális értesítési beállításokat és a feladat hozzáférhetőségét. A lezárt képernyőre az esemény rövid megnevezése kerül. Kijelentkezéskor az adott készülék regisztrációja megszűnik. Újbóli belépés után ismét engedélyezhető.

[Apple dokumentáció az APNs-regisztrációról](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns) · [Értesítések küldése](https://developer.apple.com/documentation/usernotifications/sending-notification-requests-to-apns)
