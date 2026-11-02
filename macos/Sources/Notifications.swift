import AppKit
import Combine
import UserNotifications
import WebKit

@MainActor
final class MacNotifications: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    @Published private(set) var enabled = UserDefaults.standard.bool(forKey: "notificationsEnabled")
    @Published private(set) var stateText = "Jelentkezz be a GURU-ba."
    @Published private(set) var permissionText = "Még nincs engedélyezve"
    @Published private(set) var unread = 0
    var changed: (() -> Void)?
    var openNotice: ((String?) -> Void)?
    weak var webView: WKWebView?
    let policy: ServerPolicy
    private var timer: Timer?
    private var tracker = FeedTracker()
    private var polling = false
    private var generation = 0
    private let center = UNUserNotificationCenter.current()
    private let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.httpCookieStorage = nil
        config.urlCache = nil
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 15
        return URLSession(configuration: config, delegate: NoRedirects(), delegateQueue: nil)
    }()
    init(policy: ServerPolicy) {
        self.policy = policy
        super.init()
        center.delegate = self
    }
    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.poll() }
        }
        Task { await updatePermission(); await poll() }
    }
    func updatePermission() async {
        let status = await center.notificationSettings().authorizationStatus
        switch status {
        case .authorized, .provisional: permissionText = "A macOS engedélyezte"
        case .denied: permissionText = "A macOS letiltotta"
        default: permissionText = "Még nincs engedélyezve"
        }
        publishWebState(authorized: status == .authorized || status == .provisional)
    }
    func toggle() {
        if enabled {
            enabled = false
            generation += 1
            UserDefaults.standard.set(false, forKey: "notificationsEnabled")
            center.removeAllPendingNotificationRequests()
            Task { await updatePermission() }
        } else {
            Task {
                do {
                    let granted = try await center.requestAuthorization(options: [.alert, .badge, .sound])
                    enabled = granted
                    UserDefaults.standard.set(granted, forKey: "notificationsEnabled")
                    await updatePermission()
                    if !granted { showPermissionHelp() }
                    await poll()
                } catch { stateText = "Az értesítési engedély nem kérhető. A Mac rendszerbeállításaiban ellenőrizd." }
            }
        }
        changed?()
    }
    private func showPermissionHelp() {
        let alert = NSAlert()
        alert.messageText = "Engedélyezd a Mac-értesítéseket"
        alert.informativeText = "Rendszerbeállítások → Értesítések → kjbk projekt guru. Ezután kapcsold be itt is az értesítéseket."
        alert.addButton(withTitle: "Rendben")
        alert.runModal()
    }
    func testNotification() {
        Task {
            guard enabled else { toggle(); return }
            let content = UNMutableNotificationContent()
            content.title = "kjbk projekt guru"
            content.body = "A Mac rendszerértesítései működnek."
            content.sound = .default
            do { try await center.add(UNNotificationRequest(identifier: "guru-local-test", content: content, trigger: nil)) }
            catch { stateText = "A próbaértesítés nem jeleníthető meg." }
        }
    }
    private func publishWebState(authorized: Bool) {
        let value = enabled && authorized ? "true" : "false"
        webView?.evaluateJavaScript("if(window.guruMac){window.guruMac.notificationsEnabled=\(value);window.dispatchEvent(new Event('guru-mac-notifications'));}", completionHandler: nil)
        changed?()
    }
    private func cursorKey(_ user: Int) -> String { "cursor.\(policy.base.absoluteString).\(user)" }
    private func cookies() async -> [HTTPCookie] {
        guard let store = webView?.configuration.websiteDataStore.httpCookieStore else { return [] }
        return await withCheckedContinuation { continuation in
            store.getAllCookies { values in
                continuation.resume(returning: values.filter {
                    $0.domain.trimmingCharacters(in: CharacterSet(charactersIn: ".")).lowercased() == self.policy.base.host?.lowercased()
                        && ($0.expiresDate == nil || $0.expiresDate! > Date())
                        && (!$0.isSecure || self.policy.base.scheme == "https")
                })
            }
        }
    }
    private func sessionFingerprint(_ cookies: [HTTPCookie]) -> String? {
        cookies.first(where: { $0.name == "sessionid" })?.value
    }
    func poll() async {
        guard !polling else { return }
        polling = true
        defer { polling = false; changed?() }
        guard let fingerprint = sessionFingerprint(await cookies()) else { signedOut(); return }
        do {
            // A baseline identifies the current account before any saved account cursor is used.
            if tracker.userID == nil {
                let feed = try await fetch(after: nil)
                guard sessionFingerprint(await cookies()) == fingerprint else { return }
                let saved = UserDefaults.standard.object(forKey: cursorKey(feed.userID)) as? Int
                tracker.baseline(feed, savedCursor: saved)
                UserDefaults.standard.set(tracker.cursor, forKey: cursorKey(feed.userID))
                unread = feed.unread
            }
            for _ in 0..<5 {
                let fetchGeneration = generation
                let feed = try await fetch(after: tracker.cursor)
                guard sessionFingerprint(await cookies()) == fingerprint else { return }
                guard tracker.accepts(feed) else {
                    signedOut()
                    return
                }
                unread = feed.unread
                if enabled && fetchGeneration == generation {
                    let status = await center.notificationSettings().authorizationStatus
                    if status == .authorized || status == .provisional {
                        for notice in feed.notifications {
                            guard enabled && fetchGeneration == generation,
                                  sessionFingerprint(await cookies()) == fingerprint else { return }
                            let content = UNMutableNotificationContent()
                            content.title = notice.title
                            content.body = notice.body
                            content.sound = .default
                            content.userInfo = ["user": feed.userID, "notice": notice.id, "task": notice.taskID ?? ""]
                            try await center.add(UNNotificationRequest(identifier: "guru-\(feed.userID)-\(notice.id)", content: content, trigger: nil))
                        }
                    }
                }
                tracker.acknowledge(feed)
                UserDefaults.standard.set(tracker.cursor, forKey: cursorKey(feed.userID))
                stateText = "Kapcsolódva · ellenőrizve: " + DateFormatter.localizedString(from: Date(), dateStyle: .none, timeStyle: .short)
                if !feed.hasMore { break }
            }
        } catch NetworkFailure.unauthorized { signedOut() }
        catch NetworkFailure.unsupported { stateText = "A szervert frissíteni kell a Mac-értesítésekhez." }
        catch { stateText = "A kapcsolat szünetel. Automatikusan újrapróbálom." }
    }
    private func signedOut() {
        if tracker.userID != nil {
            center.removeAllDeliveredNotifications()
            center.removeAllPendingNotificationRequests()
        }
        tracker.reset()
        unread = 0
        stateText = "Jelentkezz be a GURU-ba."
    }
    private enum NetworkFailure: Error { case unauthorized, unsupported, invalid }
    private func fetch(after: Int?) async throws -> NotificationFeed {
        let suffix = after.map { "?after=\($0)" } ?? ""
        var request = URLRequest(url: policy.localURL("/api/desktop/notifications/" + suffix)!)
        request.allHTTPHeaderFields = HTTPCookie.requestHeaderFields(with: await cookies())
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, let url = http.url, policy.isOwn(url) else { throw NetworkFailure.invalid }
        if http.statusCode == 401 || http.statusCode == 403 { throw NetworkFailure.unauthorized }
        if http.statusCode == 404 { throw NetworkFailure.unsupported }
        guard http.statusCode == 200, data.count < 1_000_000 else { throw NetworkFailure.invalid }
        return try JSONDecoder().decode(NotificationFeed.self, from: data)
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list, .sound])
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        let user = info["user"] as? Int
        let task = info["task"] as? String
        Task { @MainActor in
            await self.poll()
            if user == nil || user == self.tracker.userID { self.openNotice?(task?.isEmpty == false ? task : nil) }
            completionHandler()
        }
    }
}

private final class NoRedirects: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}
