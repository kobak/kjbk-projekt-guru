import Foundation

struct DesktopNotice: Decodable {
    let id: Int
    let title: String
    let body: String
    let taskID: String?
    enum CodingKeys: String, CodingKey { case id, title, body; case taskID = "task_id" }
}

struct NotificationFeed: Decodable {
    let userID: Int
    let cursor: Int
    let unread: Int
    let hasMore: Bool
    let notifications: [DesktopNotice]
    enum CodingKeys: String, CodingKey {
        case cursor, unread, notifications
        case userID = "user_id", hasMore = "has_more"
    }
}

struct FeedTracker {
    private(set) var userID: Int?
    private(set) var cursor: Int?
    mutating func reset() { userID = nil; cursor = nil }
    mutating func baseline(_ feed: NotificationFeed, savedCursor: Int?) {
        userID = feed.userID
        cursor = savedCursor.map { max(0, min($0, feed.cursor)) } ?? feed.cursor
    }
    func accepts(_ feed: NotificationFeed) -> Bool {
        feed.userID == userID && feed.cursor >= (cursor ?? 0)
    }
    mutating func acknowledge(_ feed: NotificationFeed) {
        if accepts(feed) { cursor = feed.cursor }
    }
}

struct ServerPolicy {
    let base: URL
    init?(url: URL, development: Bool = false) {
        guard let c = URLComponents(url: url, resolvingAgainstBaseURL: false),
              c.user == nil, c.password == nil, c.query == nil, c.fragment == nil,
              c.path.isEmpty || c.path == "/", c.host != nil else { return nil }
        let local = ["localhost", "127.0.0.1", "::1"].contains(c.host!.lowercased())
        guard c.scheme == "https" || (development && local && c.scheme == "http") else { return nil }
        base = url
    }
    func isOwn(_ url: URL) -> Bool {
        url.scheme == base.scheme && url.host?.lowercased() == base.host?.lowercased()
            && effectivePort(url) == effectivePort(base) && url.user == nil && url.password == nil
    }
    func localURL(_ path: String) -> URL? {
        guard path.hasPrefix("/"), !path.hasPrefix("//"), !path.contains("\\"), !path.contains("\r"), !path.contains("\n"),
              let url = URL(string: path, relativeTo: base)?.absoluteURL,
              isOwn(url) else { return nil }
        return url
    }
    private func effectivePort(_ url: URL) -> Int { url.port ?? (url.scheme == "https" ? 443 : 80) }
}
