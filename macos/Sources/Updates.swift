import Foundation
import Combine

enum UpdateCheckResult: Equatable {
    case skipped, current, available(MacRelease), failed(String)
}

@MainActor
final class MacUpdates: ObservableObject {
    @Published private(set) var available: MacRelease?
    @Published private(set) var checking = false
    @Published private(set) var stateText = "Még nem ellenőriztük."
    @Published private(set) var automatic: Bool
    let currentVersion: String
    let repository: UpdateRepository?
    var onResult: ((UpdateCheckResult, Bool) -> Void)?
    var changed: (() -> Void)?
    private let defaults: UserDefaults
    private let session: URLSession
    private let prefix: String
    private var timer: Timer?
    var isConfigured: Bool { repository != nil && MacVersion(currentVersion) != nil }

    init(version: String, repository: String?, defaults: UserDefaults = .standard, session: URLSession? = nil) {
        currentVersion = version
        self.repository = repository.flatMap(UpdateRepository.init)
        self.defaults = defaults
        prefix = "macUpdates.\(repository ?? "disabled")."
        automatic = defaults.object(forKey: prefix + "automatic") as? Bool ?? true
        if let session = session { self.session = session }
        else {
            let config = URLSessionConfiguration.ephemeral
            config.httpCookieStorage = nil
            config.httpShouldSetCookies = false
            config.urlCredentialStorage = nil
            config.urlCache = nil
            config.timeoutIntervalForRequest = 15
            config.timeoutIntervalForResource = 20
            self.session = URLSession(configuration: config, delegate: UpdateNoRedirects(), delegateQueue: nil)
        }
        if let repo = self.repository, let current = MacVersion(version),
           let data = defaults.data(forKey: prefix + "available"),
           let cached = try? JSONDecoder().decode(MacRelease.self, from: data), repo.accepts(cached),
           let newer = MacVersion(cached.version), newer > current {
            available = cached
            stateText = "Elérhető a Mac \(cached.version)."
        }
        if !isConfigured { stateText = "Ehhez a telepítéshez nincs frissítési forrás beállítva." }
    }
    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: 3600, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.check() }
        }
        Task {
            let result = await check()
            if result == .skipped, automatic, !checking, let cached = available {
                onResult?(.available(cached), false)
            }
        }
    }
    func setAutomatic(_ enabled: Bool) {
        automatic = enabled
        defaults.set(enabled, forKey: prefix + "automatic")
        if enabled { Task { await check() } }
    }
    func wasAnnounced(_ version: String, channel: String) -> Bool {
        defaults.string(forKey: prefix + channel) == version
    }
    func markAnnounced(_ version: String, channel: String) {
        defaults.set(version, forKey: prefix + channel)
    }
    @discardableResult
    func check(manual: Bool = false, now: Date = Date()) async -> UpdateCheckResult {
        guard let repo = repository, let current = MacVersion(currentVersion), !checking else { return .skipped }
        if !manual && (!automatic || now < (defaults.object(forKey: prefix + "nextCheck") as? Date ?? .distantPast)) { return .skipped }
        if let retry = defaults.object(forKey: prefix + "rateLimitUntil") as? Date, retry > now {
            let result = UpdateCheckResult.failed("A GitHub átmenetileg korlátozza az ellenőrzést. Próbáld újra később.")
            if manual { onResult?(result, true) }
            return result
        }
        checking = true
        stateText = "Frissítések keresése…"
        changed?()
        defer { checking = false; changed?() }
        var request = URLRequest(url: repo.apiURL, cachePolicy: .reloadIgnoringLocalCacheData)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("GURU-Mac/\(currentVersion)", forHTTPHeaderField: "User-Agent")
        let result: UpdateCheckResult
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse, http.url == repo.apiURL else { throw UpdateFailure.invalid }
            if http.statusCode == 429 || http.statusCode == 403 {
                let reset = http.value(forHTTPHeaderField: "X-RateLimit-Reset").flatMap(Double.init).map { Date(timeIntervalSince1970: $0) }
                let delay = http.value(forHTTPHeaderField: "Retry-After").flatMap(Double.init) ?? 3600
                let retry = max(now.addingTimeInterval(max(60, delay)), reset ?? now)
                defaults.set(retry, forKey: prefix + "rateLimitUntil")
                throw UpdateFailure.rateLimited
            }
            guard http.statusCode == 200, data.count <= 2_000_000,
                  let newest = try repo.newest(in: data) else { throw UpdateFailure.invalid }
            let newer = MacVersion(newest.version)! > current
            available = newer ? newest : nil
            if let available = available { defaults.set(try JSONEncoder().encode(available), forKey: prefix + "available") }
            else { defaults.removeObject(forKey: prefix + "available") }
            defaults.removeObject(forKey: prefix + "rateLimitUntil")
            defaults.set(now.addingTimeInterval(86400), forKey: prefix + "nextCheck")
            stateText = newer ? "Elérhető a Mac \(newest.version)." : "A Mac \(currentVersion) naprakész."
            result = newer ? .available(newest) : .current
        } catch {
            defaults.set(now.addingTimeInterval(3600), forKey: prefix + "nextCheck")
            stateText = "A frissítés most nem ellenőrizhető. Később újrapróbáljuk."
            result = .failed(error as? UpdateFailure == .rateLimited
                ? "A GitHub átmenetileg korlátozza az ellenőrzést. Próbáld újra később."
                : "A frissítés most nem ellenőrizhető. Ellenőrizd az internetkapcsolatot, és próbáld újra később.")
        }
        onResult?(result, manual)
        return result
    }
    private enum UpdateFailure: Error { case invalid, rateLimited }
}

private final class UpdateNoRedirects: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}
