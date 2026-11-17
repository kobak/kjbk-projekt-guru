import Foundation

private var checks = 0
private func check(_ value: Bool, _ message: String) {
    checks += 1
    if !value { fatalError(message) }
}
private final class StubHTTP: URLProtocol {
    static var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))!
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        do {
            let (response, data) = try Self.handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch { client?.urlProtocol(self, didFailWithError: error) }
    }
    override func stopLoading() {}
}

@main
@MainActor
struct UpdateTests {
    static func main() async throws {
        let repo = UpdateRepository("kobak/kjbk-projekt-guru")!
        let version = "0.1.10"
        let releaseURL = "https://github.com/\(repo.name)/releases/tag/v99.0.0"
        let downloadURL = "https://github.com/\(repo.name)/releases/download/v99.0.0/kjbk-projekt-guru-mac-\(version).zip"
        func release(_ value: String, draft: Bool = false, prerelease: Bool = false, url: String? = nil, state: String = "uploaded") -> [String: Any] {
            ["draft": draft, "prerelease": prerelease, "html_url": releaseURL,
             "assets": [["name": "kjbk-projekt-guru-mac-\(value).zip", "state": state,
                         "browser_download_url": url ?? "https://github.com/\(repo.name)/releases/download/v99.0.0/kjbk-projekt-guru-mac-\(value).zip"]]]
        }
        let feed = try JSONSerialization.data(withJSONObject: [
            ["draft": false, "prerelease": false, "html_url": releaseURL, "assets": []],
            release("0.1.2"), release(version), release("0.2.0", draft: true), release("0.3.0", prerelease: true),
            release("0.4.0", url: "https://evil.example/payload.zip"), release("0.5.0", state: "new")])
        check(MacVersion("0.1.10")! > MacVersion("0.1.2")!, "numeric patch comparison")
        check(MacVersion("1.0.0")! > MacVersion("0.99.99")!, "numeric major comparison")
        for invalid in ["", "1.2", "1.2.3-beta", "1.2.3.4", "-1.2.3", "1.2.3\n", "999999999999.0.0"] {
            check(MacVersion(invalid) == nil, "reject invalid version: \(invalid)")
        }
        for invalid in ["../repo", "owner/..", "owner/repo/extra", "https://github.com/owner/repo", "owner/", "/repo"] {
            check(UpdateRepository(invalid) == nil, "reject untrusted repository: \(invalid)")
        }
        let newest = try repo.newest(in: feed)!
        check(newest.version == version, "choose latest stable Mac asset, ignore web version and invalid assets")
        check(newest.downloadURL.absoluteString == downloadURL, "retain exact validated asset URL")
        for invalid in [
            "http://github.com/\(repo.name)/releases/download/v99.0.0/kjbk-projekt-guru-mac-\(version).zip",
            "https://github.com.evil.example/\(repo.name)/releases/download/v99.0.0/kjbk-projekt-guru-mac-\(version).zip",
            "https://github.com/evil/repo/releases/download/v99.0.0/kjbk-projekt-guru-mac-\(version).zip",
            downloadURL + "?redirect=evil", downloadURL + "#fragment", downloadURL.replacingOccurrences(of: "github.com", with: "user@github.com"),
            downloadURL.replacingOccurrences(of: "github.com", with: "github.com:8443")
        ] {
            check(!repo.accepts(MacRelease(version: version, releaseURL: URL(string: releaseURL)!, downloadURL: URL(string: invalid)!)), "reject unsafe asset destination")
        }
        let namespace = "guru-update-tests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: namespace)!
        defer { defaults.removePersistentDomain(forName: namespace) }
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubHTTP.self]
        let session = URLSession(configuration: config)
        defer { session.invalidateAndCancel() }
        var requests = 0
        StubHTTP.handler = { request in
            requests += 1
            check(request.url == repo.apiURL, "read only the configured public GitHub API")
            check(request.value(forHTTPHeaderField: "Authorization") == nil && request.value(forHTTPHeaderField: "Cookie") == nil, "send no account credentials or cookies")
            return (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, feed)
        }
        let updater = MacUpdates(version: "0.1.2", repository: repo.name, defaults: defaults, session: session)
        let now = Date()
        check(await updater.check(now: now) == .available(newest), "automatic check detects upgrade")
        check(await updater.check(now: now.addingTimeInterval(3600)) == .skipped && requests == 1, "daily automatic cooldown")
        let restarted = MacUpdates(version: "0.1.2", repository: repo.name, defaults: defaults, session: session)
        check(restarted.available == newest, "validated available release persists through restart")
        check(await restarted.check(now: now) == .skipped, "daily cooldown persists through restart")
        updater.markAnnounced(version, channel: "dialog")
        check(restarted.wasAnnounced(version, channel: "dialog"), "dismissal persists for this version")
        check(!restarted.wasAnnounced("0.1.11", channel: "dialog"), "dismissal does not hide future versions")
        check(await updater.check(manual: true, now: now) == .available(newest) && requests == 2, "manual check bypasses daily cooldown")
        updater.setAutomatic(false)
        check(await updater.check(now: now.addingTimeInterval(90000)) == .skipped, "automatic checks can be disabled")
        check(await updater.check(manual: true, now: now) == .available(newest), "manual check works with automatic checks disabled")
        let installed = MacUpdates(version: version, repository: repo.name, defaults: defaults, session: session)
        check(installed.available == nil, "installing update clears cached upgrade indication")
        check(await installed.check(manual: true, now: now) == .current, "never offer equal version or downgrade")
        StubHTTP.handler = { _ in throw URLError(.notConnectedToInternet) }
        let failure = await updater.check(manual: true, now: now)
        if case .failed = failure { check(true, "offline is a controlled result") } else { fatalError("Expected offline failure") }
        check(updater.available == newest, "offline error preserves previously validated download")
        StubHTTP.handler = { request in
            (HTTPURLResponse(url: request.url!, statusCode: 429, httpVersion: nil, headerFields: ["Retry-After": "7200"])!, Data())
        }
        _ = await updater.check(manual: true, now: now)
        StubHTTP.handler = { _ in fatalError("Rate-limited check must not perform another request") }
        if case .failed = await updater.check(manual: true, now: now.addingTimeInterval(60)) { check(true, "manual retry respects GitHub rate limit") }
        else { fatalError("Expected rate limit response") }
        let disabled = MacUpdates(version: "0.1.2", repository: nil, defaults: defaults, session: session)
        let disabledResult = await disabled.check(manual: true)
        check(!disabled.isConfigured && disabledResult == .skipped, "custom server without explicit source never checks upstream")
        let startNamespace = namespace + ".startup"
        let startDefaults = UserDefaults(suiteName: startNamespace)!
        defer { startDefaults.removePersistentDomain(forName: startNamespace) }
        let olderFeed = try JSONSerialization.data(withJSONObject: [release("0.1.3")])
        StubHTTP.handler = { request in (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, olderFeed) }
        let previousRun = MacUpdates(version: "0.1.2", repository: repo.name, defaults: startDefaults, session: session)
        _ = await previousRun.check(now: now.addingTimeInterval(-172800))
        let startup = MacUpdates(version: "0.1.2", repository: repo.name, defaults: startDefaults, session: session)
        check(startup.available?.version == "0.1.3", "startup restores previous cached release")
        StubHTTP.handler = { request in (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, feed) }
        let announced: UpdateCheckResult = await withCheckedContinuation { continuation in
            startup.onResult = { result, _ in continuation.resume(returning: result) }
            startup.start()
        }
        check(announced == .available(newest), "startup refreshes a stale cache before announcing a release")
        print("Mac updates: \(checks) checks passed")
    }
}
